+++
title = 'Longhorn To Enterprise Storage Migration Patterns'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for migrating Kubernetes storage from Longhorn to enterprise storage platforms: volume migration strategies, application downtime expectations, PVC rebinding, and validation checks before and after migration.'
tags = ['storage', 'kubernetes', 'migration', 'longhorn', 'operations']
categories = ['field-notes']
+++

## Migration Strategies

### Attach-And-Clone (Lowest Downtime)

For platforms that support concurrent attachment:

```text
1. Deploy new StorageClass targeting enterprise storage.
2. Create a clone of the existing PVC on the new StorageClass.
3. Attach the clone to a verification pod and validate data integrity.
4. Scale down the workload, detach old PVC, attach new PVC.
5. Scale up the workload.
```

Downtime is limited to the time between scale-down and attach. Data integrity is verified before the cutover.

### Backup-And-Restore (Highest Safety)

```text
1. Take a backup of the Longhorn volume (Velero or native snapshot).
2. Restore the backup to a new PVC on the enterprise StorageClass.
3. Verify the restored data in a separate pod.
4. Scale down the workload, delete old PVC, update PVC claim to new name.
5. Scale up the workload.
```

Longhorn backups can be exported to S3-compatible storage and restored elsewhere. This is the safest pattern but requires the most time and storage overhead.

### In-Place Migration (StatefulSet Only)

For StatefulSets, the PVC template can be updated and pods recreated one at a time:

```text
1. Create new StorageClass for enterprise storage.
2. Update StatefulSet volumeClaimTemplates to reference new StorageClass.
3. Delete each pod one at a time (start from N-1 down to 0).
4. Each recreated pod gets a new PVC on the new StorageClass.
5. Data migration per pod is handled by the application (if replicas exist).
```

This only works if the application replicates data between replicas (Kafka, Cassandra, Elasticsearch). Do not use this for single-replica databases.

## Pre-Migration Validation

```bash
# List all PVCs on the Longhorn StorageClass
kubectl get pvc --all-namespaces -o json | \
  jq -r '.items[] | select(.spec.storageClassName=="longhorn") | .metadata.namespace + "/" + .metadata.name'

# Check which workloads use them
kubectl get pods --all-namespaces -o json | \
  jq -r '.items[] | select(.spec.volumes[].persistentVolumeClaim?) | .metadata.namespace + "/" + .metadata.name + " -> " + (.spec.volumes[] | select(.persistentVolumeClaim?) | .persistentVolumeClaim.claimName)'

# Validate enterprise StorageClass exists and is functional
kubectl describe sc enterprise-storage
kubectl get pvc -n default test-enterprise-pvc
```

## Volume Size And Access Mode

Longhorn supports `ReadWriteOnce` and `ReadWriteMany`. Enterprise storage may have different access mode support. Verify before migration:

```bash
kubectl get pvc <pvc-name> -o json | jq '.spec.accessModes'
```

If the target StorageClass does not support the required access mode, the PVC will not bind.

## Post-Migration Validation

```bash
# PVC is Bound
kubectl get pvc <pvc-name> -o json | jq '.status.phase'

# Data is accessible
kubectl exec <pod> -- ls -la /data

# Performance meets expectations
kubectl exec <pod> -- dd if=/dev/zero of=/data/test bs=1M count=100 conv=fdatasync

# Clean up test file
kubectl exec <pod> -- rm /data/test
```

## Rollback Plan

```text
1. Keep the original Longhorn PVC (do not delete).
2. If the new PVC fails, scale down the workload.
3. Delete the new PVC.
4. Recreate the original PVC claim if needed.
5. Scale up the workload using the original PVC.
```

Retain Longhorn volumes and snapshots for at least one full retention cycle after migration completes successfully.
