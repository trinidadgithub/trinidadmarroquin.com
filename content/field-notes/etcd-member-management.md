+++
title = 'etcd Member Management And Cluster Health'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for etcd member lifecycle: adding and removing members, quorum safety, endpoint health, alarm management, and common failure modes in RKE2 clusters.'
tags = ['etcd', 'kubernetes', 'rke2', 'operations']
categories = ['field-notes']
+++

## Check Cluster Health

```bash
# Endpoint health (all members)
etcdctl endpoint health -w table --cluster

# Endpoint status with version and DB size
etcdctl endpoint status -w table --cluster

# Member list
etcdctl member list -w table

# Leader and term
etcdctl endpoint status --cluster -w table | awk '{print $1, $4, $5}'
```

## Member Lifecycle

### Add A New Member

```bash
# On an existing member, add the new peer
etcdctl member add <node-name> --peer-urls=https://<new-peer-ip>:2380

# On the new node, start etcd with the initial cluster state set to "existing"
# Then verify
etcdctl member list -w table
etcdctl endpoint health -w table --cluster
```

### Remove A Member

```bash
etcdctl member remove <member-id>
```

After removal, verify quorum and health. The removed member's data directory can be cleaned up.

### Replace An Unhealthy Member

```bash
# 1. Remove the unhealthy member
etcdctl member remove <unhealthy-member-id>

# 2. Add the replacement (same name, new peer URL)
etcdctl member add <node-name> --peer-urls=https://<new-peer-ip>:2380

# 3. Start etcd on the replacement node with initial cluster state "existing"
```

## Quorum Safety

| Members | Quorum | Tolerated Failures |
|---|---|---|
| 1 | 1 | 0 |
| 3 | 2 | 1 |
| 5 | 3 | 2 |
| 7 | 4 | 3 |

Never operate a cluster with 2 members (quorum is 2, failure tolerance is 0). When replacing a member in a 3-node cluster, do not remove and add simultaneously — one node at a time, verifying quorum after each step.

## Alarm Management

```bash
# List alarms
etcdctl alarm list

# Disarm (if resolved)
etcdctl alarm disarm
```

Common alarms:

- `NOSPACE` — DB size exceeded the quota. Compact and defragment, then disarm.
- `CORRUPT` — Data corruption detected. Restore from snapshot.

## DB Size And Compaction

```bash
# Current DB size per member
etcdctl endpoint status -w table --cluster | awk '{print $1, $6}'

# Compact all historical revisions up to N
etcdctl compact <revision>

# Defragment (run per member, one at a time)
etcdctl defrag --cluster
```

Compaction only frees storage for future writes. Defragmentation reorganizes the DB file to reclaim space. Run defrag during maintenance windows and one member at a time.

## Common Failure Modes

- **Member removed but process still running.** The process will repeatedly log connection errors. Stop and remove the data directory on the evicted node.
- **Clock skew.** etcd is sensitive to clock drift. Validate NTP sync across all members.
- **Network partition.** A minority partition will not accept writes. It will rejoin and catch up when the partition heals.
- **Slow disk.** A member with high fsync latency will degrade the entire cluster. Check disk latency if the leader is stable but followers cannot keep up.
