+++
title = 'Longhorn Free Space Is Not Schedulable Capacity'
date = 2026-09-18T00:00:00-05:00
draft = false
description = 'Field note for diagnosing Longhorn replica scheduling failures where disks still show physical available capacity but scheduled capacity accounting prevents placement.'
tags = ['longhorn', 'kubernetes', 'storage', 'rke2', 'operations', 'troubleshooting']
categories = ['field-notes']
+++

The disk had space. Longhorn still could not place the replicas.

That was the useful part of the incident. The first read looked like an attached volume that had not finished rebuilding. The evidence pointed somewhere else: physical free space was not the same as capacity available to the Longhorn scheduler.

## Incident Shape

The affected Longhorn volume was attached and degraded:

```text
volume: pvc-35d1949c-4a61-448d-88b9-59b30c823c81
state: attached
robustness: degraded
current node: worker-4
size: 53687091200
```

Its scheduled condition was false:

```json
{
  "type": "Scheduled",
  "status": "False",
  "reason": "ReplicaSchedulingFailure",
  "message": "disks are unavailable"
}
```

The replica state made the risk concrete:

```text
replica-a  state=running  desired=running  node=storage-2  rebuildRetries=0
replica-b  state=stopped  desired=stopped  node=           rebuildRetries=5
replica-c  state=stopped  desired=stopped  node=           rebuildRetries=5
```

There was one running replica. Two replacement replicas were stopped and unplaced.

## The First Contradiction

The storage nodes themselves did not look obviously closed to scheduling.

The investigation checked Longhorn node scheduling and the volume condition together:

```bash
date -u; kubectl --context cluster-prod -n longhorn-system get nodes.longhorn.io -o wide; kubectl --context cluster-prod -n longhorn-system get volumes.longhorn.io pvc-35d1949c-4a61-448d-88b9-59b30c823c81 -o jsonpath='{.status.conditions}'
```

The intended Longhorn storage nodes were schedulable:

```text
NAME        READY  ALLOWSCHEDULING  SCHEDULABLE
storage-1   True   true             True
storage-2   True   true             True
storage-3   True   true             True
```

Worker nodes were not intended Longhorn replica targets:

```text
worker-1    True   false            True
worker-2    True   false            True
worker-3    True   false            True
worker-4    True   false            True
worker-5    True   false            True
```

So the placement pool was effectively the three storage nodes. Longhorn reported those nodes as schedulable, but the volume still reported `ReplicaSchedulingFailure` with `disks are unavailable`.

That combination is the stop sign. `SCHEDULABLE=True` on a node does not mean every new replica can fit there.

## Capacity Evidence

The next check looked at Longhorn node disk accounting:

```bash
date -u; kubectl --context cluster-prod -n longhorn-system get nodes.longhorn.io -o yaml \
  | rg -n 'name:|allowScheduling|conditions:|Ready|Schedulable|storageAvailable|storageScheduled|storageMaximum|diskUUID|evictionRequested|tags|region|zone'
```

The data disks still had substantial `storageAvailable`:

```text
storage-1 data disk:
  storageAvailable: 313943654400
  storageMaximum:   368766750720
  storageScheduled: 418759311360

storage-2 data disk:
  storageAvailable: 209086054400
  storageMaximum:   368765448192
  storageScheduled: 365072220160

storage-3 data disk:
  storageAvailable: 313524224000
  storageMaximum:   368765448192
  storageScheduled: 418759311360
```

Read those fields separately:

```text
storageAvailable  physical capacity Longhorn sees as available on the disk
storageMaximum    Longhorn's usable disk capacity boundary for scheduling accounting
storageScheduled  declared replica capacity already scheduled to that disk
```

The important observation was not simply that free bytes existed. They did. The important observation was that Longhorn's scheduling ledger was already heavy:

```text
storage-1: storageScheduled > storageMaximum
storage-2: storageScheduled was close to storageMaximum
storage-3: storageScheduled > storageMaximum
```

That made the earlier contradiction less surprising. The scheduler was not deciding from filesystem free space alone. It was also accounting for declared replica capacity already assigned to eligible disks.

## Interpretation During The Investigation

At first, the degraded volume could have been mistaken for a rebuild that just needed time. The evidence did not support that as the full explanation.

The investigation moved to this interpretation:

```text
This looks less like an active rebuild and more like a scheduling/capacity constraint.
```

That interpretation came from three observed facts together:

```text
1. The degraded volume had only one running replica.
2. Two replacement replicas were stopped, unplaced, and had rebuildRetries=5.
3. Eligible storage disks still had storageAvailable, but scheduled capacity was already at or above the scheduling boundary on key disks.
```

No single field was enough by itself.

`storageAvailable` did not prove the scheduler could place another replica. `storageScheduled > storageMaximum` did not become a universal explanation for every `ReplicaSchedulingFailure`. In this incident, the fields together showed why “the disk has space” was an incomplete model.

## What The Evidence Supported

Observed evidence:

```text
volume attached/degraded
Scheduled=False
ReplicaSchedulingFailure
message="disks are unavailable"
one running replica
two stopped, unplaced replacement replicas
worker disks excluded from replica scheduling
storage nodes marked schedulable
data disks still had large storageAvailable values
two storage data disks had storageScheduled greater than storageMaximum
```

Interpretation during the investigation:

```text
This was less likely to be only an active rebuild delay.
It looked like Longhorn replica placement was constrained by scheduling/capacity accounting on the eligible storage nodes.
```

Conclusion supported by the evidence:

```text
Physical available capacity and Longhorn schedulable capacity were not equivalent in this incident.
```

Other Longhorn scheduling constraints can also matter: node and disk `allowScheduling`, disk selectors, node selectors, anti-affinity settings, tags, zones, reserved capacity, minimum free percentage, and existing replica placement. The point here is narrower: do not stop at filesystem free space when the failure is a scheduler failure.

## Operationalizing The Check

This is the kind of incident that should become a repeatable diagnostic, not a one-off memory.

The corresponding ops-toolbox diagnostic is:

```text
kubernetes/longhorn/longhorn-scheduler-pressure-report.sh
```

The useful report shape is not just “disk free.” It should put these values next to each other for every Longhorn disk:

```text
node
disk
node allowScheduling
disk schedulable condition
storageMaximum
storageAvailable
storageScheduled
scheduled percentage
scheduled-over-maximum amount
scheduled replica count
```

This incident is also a strong candidate for sanitized fixture coverage. The fixture should represent:

```text
physically available storage
scheduling pressure
degraded volume
ReplicaSchedulingFailure
unplaced replicas
```

That fixture should let the diagnostic behavior be tested without access to the original cluster or its identifiers.

## Operating Rule

For Longhorn replica placement, this mental model is wrong:

```text
disk has free space -> replica can schedule
```

Use this instead:

```text
filesystem free space
!=
capacity available to the Longhorn scheduler
```

When a degraded volume reports `ReplicaSchedulingFailure`, check the scheduler's view of the eligible disks. If `storageAvailable`, `storageMaximum`, and `storageScheduled` point in different directions, the disk may have free bytes while Longhorn has no safe place to account for another replica.

For maintenance workflows that stop before storage-node disruption, see [Kubernetes OS Maintenance Needs Storage Safety Gates](/field-notes/kubernetes-os-maintenance-storage-safety/). For broader Longhorn disk-pressure triage, see [Longhorn No Scheduled Replicas Under Disk Pressure](/field-notes/longhorn-no-scheduled-replicas-disk-pressure/).
