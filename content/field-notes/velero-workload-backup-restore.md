+++
title = 'Velero Workload Backup And Restore For Kubernetes'
date = 2026-06-18T00:00:00-05:00
draft = false
description = 'Field note for Velero-based workload backup and restore in Kubernetes: backup schedules, restore validation, restic integration, common failure modes, and recovery patterns.'
tags = ['kubernetes', 'velero', 'backup', 'recovery', 'storage']
categories = ['field-notes']
+++

## Prerequisites

Velero backs up Kubernetes resources and, with the restic/kopia integration, persistent volume data. The backup target must be an S3-compatible object store.

```bash
# Install Velero CLI (Linux)
curl -LO https://github.com/vmware-tanzu/velero/releases/latest/download/velero-v1.15.0-linux-amd64.tar.gz
tar xzf velero-*-linux-amd64.tar.gz
sudo mv velero-*/velero /usr/local/bin/

# Install server with restic for PV backup
velero install \
  --provider aws \
  --bucket <bucket-name> \
  --prefix <optional-prefix> \
  --backup-location-config region=<region>,s3ForcePathStyle=true,s3Url=<endpoint> \
  --snapshot-location-config region=<region> \
  --secret-file ./credentials-velero \
  --use-node-agent \
  --wait

# Verify
velero version
velero client config set --namespace velero
```

## Backup

### Ad-Hoc Backup

```bash
# Backup all resources in a namespace
velero backup create <name> --include-namespaces <ns>

# Backup with PV data (requires node-agent)
velero backup create <name> \
  --include-namespaces <ns> \
  --default-volumes-to-fs-backup

# Backup specific resource types
velero backup create <name> \
  --include-namespaces <ns> \
  --include-resources deployments,configmaps,secrets,pvc

# Exclude specific resources
velero backup create <name> \
  --include-namespaces <ns> \
  --exclude-resources events,events.events.k8s.io

# Backup entire cluster (use with caution in large clusters)
velero backup create <name> --exclude-namespaces velero,kube-system
```

### Label-Based Backup

```bash
# Backup resources matching label
velero backup create <name> \
  --selector app=<app-name> \
  --include-namespaces <ns>

# Or use a label selector for opt-in backup
velero backup create <name> \
  --include-namespaces <ns> \
  --selector velero-backup=true
```

## Schedule

```bash
# Daily backup with 7-day retention
velero schedule create daily \
  --schedule "0 2 * * *" \
  --include-namespaces <ns> \
  --default-volumes-to-fs-backup \
  --ttl 168h

# Hourly backup for critical namespaces
velero schedule create hourly-critical \
  --schedule "0 * * * *" \
  --include-namespaces critical-ns \
  --default-volumes-to-fs-backup \
  --ttl 24h

# Pause/resume schedule
velero schedule pause daily
velero schedule unpause daily
```

## Restore

### Basic Restore

```bash
# Restore from latest backup
velero restore create --from-backup <backup-name>

# Restore to a different namespace
velero restore create \
  --from-backup <backup-name> \
  --namespace-mappings original-ns:new-ns

# Restore specific items
velero restore create \
  --from-backup <backup-name> \
  --include-resources deployments,configmaps
```

### Restore With Options

```bash
# Restore without restoring PV data
velero restore create \
  --from-backup <backup-name> \
  --exclude-resources persistentvolumeclaims

# Restore and skip existing resources
velero restore create \
  --from-backup <backup-name> \
  --existing-resource-policy none

# Restore to a cluster with different storage class
velero restore create \
  --from-backup <backup-name> \
  --storage-class-mappings standard:fast-ssd
```

## Validation

```bash
# List backups and check status
velero backup get
velero backup describe <backup-name> --details

# List restores
velero restore get
velero restore describe <restore-name> --details

# Check backup logs for warnings/errors
velero backup logs <backup-name> | grep -E "warning|error|fail"

# Verify backup integrity (comparison of actual restore)
velero restore create \
  --from-backup <backup-name> \
  --dry-run \
  --namespace-mappings source-ns:verify-ns
```

## Common Failure Modes

### Backup Fails With "AccessDenied"

The IAM credentials or S3 endpoint configuration is wrong. Verify the bucket exists and the credentials file is current.

```bash
# Test S3 access directly
aws s3 --endpoint-url <s3-endpoint> ls s3://<bucket>/ --profile velero
```

### Volume Backup Hangs Or Never Completes

The node-agent pod may be resource-constrained or the PVC is not mounted on a schedulable node.

```bash
# Check node-agent pod status
kubectl -n velero get pods -l component=node-agent

# Check if the PVC is mounted on a reachable node
kubectl get pod -n <ns> -o wide | grep <pvc-name>
# If the pod is stuck in Pending or the node is cordoned, PV backup stalls
```

### Restore Creates Resources But PVCs Stay Pending

The storage class does not exist or the CSI driver is not installed on the target cluster.

```bash
# Check storage class mapping
velero restore describe <restore-name> | grep -A 5 "Storage Class Mapping"

# Verify storage class exists on the target
kubectl get storageclass
```

### Backup Succeeds But Restore Is Incomplete

Resources with dependencies (e.g., a Deployment that depends on a ConfigMap) may fail if ordering is not preserved. Velero handles most ordering but custom resources may need manual ordering.

```bash
# Check which resources failed
velero restore describe <restore-name> | grep -A 10 "Warnings:"
```

### Namespace Already Exists On Target

Velero will not overwrite existing namespaces. Use `--existing-resource-policy update` carefully or restore into a different namespace with `--namespace-mappings`.

## Retention Strategy

| Environment | Schedule | Retention | PV Backup |
|---|---|---|---|
| Production | Every 4 hours | 14 days | Yes |
| UAT/Staging | Every 12 hours | 7 days | Recommended |
| Development | Daily | 3 days | Optional |

Backups are only useful when:

- The restore process is rehearsed quarterly with a documented runbook.
- The object store credentials are rotated and stored outside Velero's namespace.
- Cross-region replication is tested by performing a full restore.
- The backup schedule covers all namespaces with persistent data.
- The `ttl` on the backup schedule aligns with the recovery point objective.
- Node-agent resource requests are sized to handle the largest PVC.
