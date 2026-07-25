+++
title = 'Longhorn No Scheduled Replicas Under Disk Pressure'
date = 2026-07-24T00:00:00-05:00
draft = false
description = 'Field note for troubleshooting Longhorn replica scheduling failures caused by disk pressure, scheduled-capacity overcommitment, orphaned replica data, and unused PVCs.'
tags = ['longhorn', 'kubernetes', 'storage', 'rke2', 'rancher', 'prometheus', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

Longhorn can report `no scheduled replicas` even when the Kubernetes PVC is still `Bound` and the data has not obviously disappeared. The message is easy to misread as a corrupt or missing volume. In practice, it often means Longhorn cannot place a replica on any eligible disk because scheduling rules, reservation, or nominal volume size have made the storage pool unschedulable.

The important distinction is this:

```text
actual filesystem usage != Longhorn scheduled capacity
```

A Longhorn node can have free disk blocks while still refusing new replicas because the declared size of scheduled replicas exceeds the safe scheduling limit.

## First Checks

Start with the affected volume in the Longhorn UI.

Check the volume detail page and the `Replicas` tab:

- If there are no replicas, treat it as a restore or manual recovery case.
- If replicas exist but show `Stopped`, `N/A`, or `Replica Scheduling Failure`, continue with node and disk scheduling checks.
- If replicas are `Failed` or `Unknown`, consider Longhorn salvage only after confirming which replica data is trustworthy.

Then check the Longhorn node and disk state:

```bash
kubectl -n longhorn-system get nodes.longhorn.io
kubectl -n longhorn-system get volumes.longhorn.io,replicas.longhorn.io -o wide
```

For the affected Longhorn node:

```bash
node='<longhorn-node-name>'

kubectl -n longhorn-system get nodes.longhorn.io "$node" -o yaml
```

Look for these fields under the relevant disk in `status.diskStatus`:

```text
storageAvailable
storageMaximum
storageScheduled
conditions[type=Schedulable]
scheduledReplica
```

If `storageScheduled` is greater than `storageMaximum`, or greater than the practical scheduling ceiling after reservation and minimum free space, deleting random stopped replicas will not fix the design problem.

## Do Not Delete Stopped Replicas Blindly

A stopped replica is not automatically unused. It can be stopped because the workload is not running, the volume is detached, the node is under scheduling pressure, or the replica was replaced during a rebuild.

Do not delete replicas from the Longhorn Node page just because their status is `Stopped`.

Before deleting anything, identify what the replica belongs to:

```bash
pvc_fragment='<pvc-uuid-fragment>'

kubectl get pv | grep "$pvc_fragment" || true
kubectl -n longhorn-system get volumes.longhorn.io | grep "$pvc_fragment" || true
kubectl -n longhorn-system get replicas.longhorn.io | grep "$pvc_fragment" || true
```

If the PV, Longhorn volume, or Replica CR still exists, the data may still be managed and meaningful.

## Scheduled Capacity Versus Used Capacity

Longhorn schedules replicas against the declared volume size, not just current physical usage. A mostly empty 150 GiB PVC with three replicas can still consume 450 GiB of scheduled capacity across the cluster.

Inventory declared volume size and replica count:

```bash
kubectl -n longhorn-system get volumes.longhorn.io \
  -o custom-columns=NAME:.metadata.name,REPLICAS:.spec.numberOfReplicas,SIZE:.spec.size,STATE:.status.state,ROBUSTNESS:.status.robustness
```

For a node under pressure, inspect scheduled replicas:

```bash
node='<longhorn-node-name>'
disk='<longhorn-disk-name>'

kubectl -n longhorn-system get nodes.longhorn.io "$node" \
  -o json \
  | jq --arg disk "$disk" '.status.diskStatus[$disk].scheduledReplica'
```

Large observability volumes such as Prometheus, Loki, MinIO, and log stores can dominate scheduled capacity. They may also have different recoverability requirements than customer databases. Do not assume every volume needs the same Longhorn replica count.

## Check Real Disk Usage

On the Longhorn storage node, compare filesystem usage with Longhorn's scheduled view:

```bash
df -h /mnt/data
sudo du -sh /mnt/data/*
sudo du -sh /mnt/data/replicas/* | sort -hr | head -30
```

This separates two problems:

- High physical usage: the disk is actually full or close to full.
- High scheduled usage: Longhorn has committed more nominal capacity than the disk can safely schedule.

Both matter, but they require different fixes.

## Orphaned Replica Data

Longhorn creates Orphan CRs for replica data it sees on disk but no longer manages through current Longhorn objects.

List orphans:

```bash
kubectl -n longhorn-system get orphans.longhorn.io
```

Capture evidence before cleanup:

```bash
kubectl -n longhorn-system get orphans.longhorn.io -o yaml \
  > longhorn-orphans-before-cleanup.yaml
```

Use the correct field for orphan type:

```bash
kubectl -n longhorn-system get orphans.longhorn.io \
  -o jsonpath='{range .items[*]}{"ORPHAN: "}{.metadata.name}{"\nNODE: "}{.spec.nodeID}{"\nTYPE: "}{.spec.orphanType}{"\nDATA: "}{.spec.parameters.DataName}{"\nCLEAN: "}{range .status.conditions[?(@.type=="DataCleanable")]}{.status}{end}{"\nERROR: "}{range .status.conditions[?(@.type=="Error")]}{.status}{end}{"\n\n"}{end}'
```

Only consider orphan cleanup when the evidence supports it:

- `orphanType` is `replica`.
- `DataCleanable` is `True`.
- `Error` is `False`.
- The exact orphan `DataName` does not match a current `replicas.longhorn.io` object.
- Any parent volume that still exists is healthy before and after cleanup.

Cross-check orphan data names against managed replicas:

```bash
kubectl -n longhorn-system get replicas.longhorn.io \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' \
  | sort > /tmp/managed-longhorn-replicas.txt

kubectl -n longhorn-system get orphans.longhorn.io \
  -o jsonpath='{range .items[*]}{.spec.parameters.DataName}{"\n"}{end}' \
  | sort > /tmp/orphan-longhorn-replicas.txt

comm -12 /tmp/managed-longhorn-replicas.txt /tmp/orphan-longhorn-replicas.txt
```

Expected output is empty.

## If Orphan CR Deletion Does Not Free Space

Deleting an Orphan CR should remove the associated orphaned replica data. If the CR disappears but disk usage does not change, verify whether the directories still exist on disk.

Search for known orphan suffixes:

```bash
sudo find /mnt/data/replicas -maxdepth 1 -type d -name '<orphan-data-name>'
sudo du -sh /mnt/data/replicas/<orphan-data-name>
```

Before touching the filesystem manually, confirm all of the following:

- The exact name returns `NotFound` from `replicas.longhorn.io`.
- A broad replica search finds no managed CR with that suffix.
- Parent volumes are still healthy.
- Longhorn manager logs do not show an active cleanup error that needs controller attention first.

Example exact-name check:

```bash
for dir in \
  pvc-example-volume-aaaaaaaa \
  pvc-example-volume-bbbbbbbb
do
  echo "=== $dir ==="
  kubectl -n longhorn-system get replicas.longhorn.io "$dir" 2>&1
done
```

Check Longhorn manager logs:

```bash
kubectl -n longhorn-system logs \
  -l app=longhorn-manager \
  --since=2h \
  --prefix \
  | grep -Ei 'orphan|<replica-suffix-1>|<replica-suffix-2>'
```

If manual cleanup is required, quarantine first. Move within the same filesystem so rollback is possible, then wait and recheck Longhorn health:

```bash
sudo mkdir -p /mnt/data/orphan-quarantine-$(date +%Y%m%d)

sudo mv /mnt/data/replicas/<orphan-data-name> \
  /mnt/data/orphan-quarantine-$(date +%Y%m%d)/

kubectl -n longhorn-system get volumes.longhorn.io \
  -o custom-columns=NAME:.metadata.name,STATE:.status.state,ROBUSTNESS:.status.robustness
```

Moving a directory inside the same filesystem does not free space. It only creates a rollback window. After the cluster remains healthy, remove the quarantine:

```bash
sudo rm -rf --one-file-system /mnt/data/orphan-quarantine-YYYYMMDD
sync
df -h /mnt/data
sudo du -sh /mnt/data/replicas
```

If `du` drops but `df` does not, check for deleted files still held open:

```bash
sudo lsof +L1 /mnt/data
```

## Unused PVC Review

When Longhorn remains unschedulable because `storageScheduled` is too high, reduce managed scheduled capacity. The safest path is to find PVCs that are genuinely unused and delete the PVC, not the PV first.

Build an inventory:

```bash
kubectl get pvc -A \
  -o custom-columns=NAMESPACE:.metadata.namespace,PVC:.metadata.name,STATUS:.status.phase,VOLUME:.spec.volumeName,STORAGECLASS:.spec.storageClassName,CAPACITY:.status.capacity.storage,CREATED:.metadata.creationTimestamp

kubectl get pv \
  -o custom-columns=PV:.metadata.name,STATUS:.status.phase,CLAIM_NAMESPACE:.spec.claimRef.namespace,CLAIM:.spec.claimRef.name,STORAGECLASS:.spec.storageClassName,RECLAIM:.spec.persistentVolumeReclaimPolicy,CAPACITY:.spec.capacity.storage,CSI_HANDLE:.spec.csi.volumeHandle
```

Find current Pod references:

```bash
kubectl get pods -A -o json \
  | jq -r '.items[] | .metadata.namespace as $ns | .metadata.name as $pod | .spec.volumes[]? | select(.persistentVolumeClaim != null) | [$ns, .persistentVolumeClaim.claimName, $pod] | @tsv' \
  | sort
```

Also check StatefulSet `volumeClaimTemplates`. A StatefulSet PVC may not appear as a fixed `claimName` reference:

```bash
kubectl get statefulsets -A -o json \
  | jq -r '.items[] | .metadata.namespace as $ns | .metadata.name as $sts | .spec.volumeClaimTemplates[]? | [$ns, .metadata.name, "statefulset-template", $sts] | @tsv' \
  | sort
```

Do not treat "not mounted by a running Pod" as proof that a PVC is disposable. It may belong to a scaled-down StatefulSet, retained customer data, suspended workload, or application recovery path.

## Ownership Search Before Deletion

For large detached PVCs, search beyond normal workload kinds. Operators and custom resources may own storage indirectly.

At minimum, check:

```bash
namespace='<namespace>'
pvc='<pvc-name>'
pv='<pv-name>'

kubectl -n "$namespace" get all,pvc
kubectl -n "$namespace" get secrets -l owner=helm

kubectl api-resources --verbs=list --namespaced -o name \
  | sort -u \
  | while read -r resource; do
      kubectl -n "$namespace" get "$resource" -o yaml --request-timeout=10s 2>/dev/null \
        | grep -qE "$pvc|$pv" && echo "MATCH: $resource"
    done
```

Before deleting, export evidence:

```bash
mkdir -p pvc-cleanup-backup/<namespace>

kubectl -n "$namespace" get pvc "$pvc" -o yaml \
  > pvc-cleanup-backup/<namespace>/<pvc>-pvc.yaml

kubectl get pv "$pv" -o yaml \
  > pvc-cleanup-backup/<namespace>/<pvc>-pv.yaml

volume_handle=$(kubectl get pv "$pv" -o jsonpath='{.spec.csi.volumeHandle}')

kubectl -n longhorn-system get volumes.longhorn.io "$volume_handle" -o yaml \
  > pvc-cleanup-backup/<namespace>/<pvc>-longhorn-volume.yaml
```

This preserves object configuration, not application data. Get application-owner confirmation before deleting anything with possible customer or business value.

Delete one PVC at a time:

```bash
kubectl -n "$namespace" delete pvc "$pvc"
```

With reclaim policy `Delete`, Kubernetes and Longhorn should remove the PVC, PV, and Longhorn volume. Verify all three disappear before deleting another large claim.

## Monitoring And Alerting

Longhorn disk pressure should page the team before customers find failed PVC attaches.

Watch effective disk usage including reservation:

```promql
(
  longhorn_disk_usage_bytes
  + longhorn_disk_reservation_bytes
)
/
longhorn_disk_capacity_bytes
```

Suggested alert shape:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: longhorn-storage-capacity
  namespace: cattle-monitoring-system
spec:
  groups:
    - name: longhorn-storage.rules
      rules:
        - alert: LonghornDiskUsageHigh
          expr: |
            (
              longhorn_disk_usage_bytes
              + longhorn_disk_reservation_bytes
            )
            /
            longhorn_disk_capacity_bytes
            > 0.80
          for: 15m
          labels:
            severity: warning
            component: longhorn
          annotations:
            summary: "Longhorn disk {{ $labels.disk }} on node {{ $labels.node }} is above 80% used"
            description: "Longhorn disk usage including reservation is high. Replica scheduling failures may follow."
        - alert: LonghornDiskUsageCritical
          expr: |
            (
              longhorn_disk_usage_bytes
              + longhorn_disk_reservation_bytes
            )
            /
            longhorn_disk_capacity_bytes
            > 0.90
          for: 5m
          labels:
            severity: critical
            component: longhorn
          annotations:
            summary: "Longhorn disk {{ $labels.disk }} on node {{ $labels.node }} is above 90% used"
            description: "Longhorn replica scheduling and volume attaches may fail due to disk pressure."
```

Useful dashboard panels:

- Longhorn disk usage by node and disk.
- Longhorn node storage usage versus capacity.
- Top volumes by declared size and actual size.
- Volumes by `state` and `robustness`.
- Orphan count by node.

For reactive detection, alert on Longhorn manager logs that contain `Replica Scheduling Failure`, `Replica scheduling failed`, or `insufficient storage`.

## Practical Recovery Order

Use this order during an incident:

1. Confirm whether replicas exist for the affected volume.
2. Check Longhorn node and disk schedulability.
3. Compare physical usage with `storageScheduled`.
4. Do not delete stopped replicas unless they are proven orphaned and unmanaged.
5. Clean reviewed Longhorn orphan resources first.
6. If orphan CR cleanup fails to remove disk data, quarantine exact unmanaged directories before deletion.
7. Identify genuinely unused PVCs through ownership search.
8. Delete unused PVCs one at a time and verify PVC, PV, and Longhorn volume removal.
9. Recheck `storageScheduled`, `storageAvailable`, and the disk `Schedulable` condition.
10. Address the durable cause: add capacity, reduce replica count for appropriate workloads, move large observability data, or right-size retained PVCs through migration.

## References

- [Longhorn Documentation](https://longhorn.io/docs/)
- [Longhorn Orphaned Data Cleanup](https://longhorn.io/docs/latest/advanced-resources/orphaned-data-cleanup/)
- [Longhorn Metrics](https://longhorn.io/docs/latest/monitoring/metrics/)
- [Longhorn To Enterprise Storage Migration Patterns](/field-notes/longhorn-enterprise-storage-migration/)
