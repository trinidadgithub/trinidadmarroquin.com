+++
title = 'etcd Backup, Restore, And Disaster Recovery'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for etcd snapshot and restore procedures in Kubernetes clusters: automated backups, restore validation, cluster rebuild from snapshot, and recovery patterns for RKE2.'
tags = ['etcd', 'kubernetes', 'rke2', 'backup', 'recovery']
categories = ['field-notes']
+++

## Snapshot

### Manual Snapshot

```bash
ETCDCTL_ENDPOINTS=https://127.0.0.1:2379 \
ETCDCTL_CACERT=/etc/kubernetes/pki/etcd/ca.crt \
ETCDCTL_CERT=/etc/kubernetes/pki/etcd/server.crt \
ETCDCTL_KEY=/etc/kubernetes/pki/etcd/server.key \
etcdctl snapshot save /backup/etcd-snapshot-$(date +%Y%m%d-%H%M%S).db
```

### Automated Snapshot (RKE2)

RKE2 includes `etcd-snapshot` as a subcommand:

```bash
rke2 etcd-snapshot save \
  --node-name <node-name> \
  --s3 \
  --s3-bucket=<bucket> \
  --s3-region=<region> \
  --s3-access-key=<key> \
  --s3-secret-key=<secret>
```

Automated snapshots can be configured via the RKE2 config file with `etcd-snapshot-schedule-cron` and `etcd-snapshot-retention`.

### Verify Snapshot

```bash
ETCDCTL_ENDPOINTS=https://127.0.0.1:2379 \
etcdctl snapshot status /backup/etcd-snapshot-<date>.db -w table
```

Verify the snapshot is not corrupt and check the revision and hash. A snapshot with zero revisions or a mismatched hash indicates corruption.

## Restore

### Restore To A New Cluster

```bash
# Stop etcd on all members
systemctl stop rke2-server

# Restore the snapshot (creates a new data directory)
ETCDCTL_ENDPOINTS=https://127.0.0.1:2379 \
etcdctl snapshot restore /backup/etcd-snapshot-<date>.db \
  --name=<node-name> \
  --initial-cluster=<node-name>=https://<peer-ip>:2380 \
  --initial-advertise-peer-urls=https://<peer-ip>:2380 \
  --data-dir=/var/lib/rancher/rke2/server/db/etcd
```

The restore command creates a new cluster with a new cluster ID. All members must restore from the same snapshot to form the new cluster.

### Restore A Single Member

If one member's data is corrupt but the cluster is still healthy, remove the member and re-add it. The new member will stream data from the existing leader. No snapshot restore is needed.

If the entire cluster is lost, restore each member from the same snapshot.

## Validation After Restore

```bash
# Cluster health
etcdctl endpoint health -w table --cluster

# Verify known keys
etcdctl get /registry/namespaces/default -w json | jq .metadata.name

# Verify cluster ID matches across all members
etcdctl endpoint status --cluster -w table
```

All members must report the same cluster ID.

## Retention Strategy

| Environment | Snapshot Frequency | Retention | Storage |
|---|---|---|---|
| Production | Every 4 hours | 14 days | S3-compatible bucket |
| UAT/Staging | Every 12 hours | 7 days | S3-compatible bucket |
| DR site | Cross-region replication | 30 days | Separate bucket |

Snapshots are only useful if:

- They are stored off the member node (single node loss takes the snapshots with it).
- The restore process is rehearsed at least quarterly.
- The S3 credentials used for snapshot upload are rotated and monitored.
- Cross-region replication is tested, not just configured.

## Disaster Recovery Procedure

### Total Cluster Loss

1. Provision new nodes with the same IPs or update DNS.
2. Restore the most recent snapshot on the first member.
3. Start the first member and verify health.
4. Add remaining members via `member add` and start them with `initial-cluster-state=existing`.
5. Verify all members are healthy with the same cluster ID.
6. Validate Kubernetes resources are accessible.
7. Restart any workloads that depend on API server availability.

### Partial Failure (Minority Lost)

1. Remove failed members.
2. Add replacement members.
3. Replacements sync from the existing majority.
4. No snapshot needed.

### Quorum Loss

1. Identify the member with the most recent data (highest revision).
2. Force-remove the other members from that member's perspective.
3. Restart the lone member as a single-node cluster.
4. Add new members to restore quorum.
5. Accept that any writes accepted by the lost members after the last sync are gone.
