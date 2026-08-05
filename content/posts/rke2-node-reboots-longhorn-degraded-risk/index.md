+++
title = 'RKE2 Node Reboots When Longhorn Is Already Degraded'
date = 2026-07-21T00:00:00-05:00
draft = false
description = 'A practical RKE2 maintenance pattern for rebooting control-plane and worker nodes while Longhorn storage is already degraded, including batching, drain rules, boot-ID checks, and stop criteria.'
tags = ['rke2', 'kubernetes', 'longhorn', 'rancher', 'maintenance', 'operations']
categories = ['posts']
+++

Node reboots are easy to underestimate in Kubernetes. They look smaller than upgrades because the target version does not change, but the risk profile can be just as high when storage is already unhealthy.

In one RKE2 maintenance window, the cluster needed operating-system reboots while Longhorn was not fully healthy. That changed the plan. The work could not be treated as a generic rolling reboot across every node. It needed role-based batches, explicit health gates, and a hard boundary around storage nodes until the Longhorn state was understood. It also needed retained evidence; see [Kubernetes Maintenance Evidence Bundles Need A Redaction Plan](/field-notes/kubernetes-maintenance-evidence-bundles/) for the artifact-handling side of this procedure.

The useful lesson was simple: when Longhorn is degraded, the reboot plan is a storage-risk plan first and a node-maintenance plan second.

## Start With The Storage State

Before touching nodes, capture enough state to know whether a reboot will move the cluster closer to recovery or further away from it:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running
kubectl -n longhorn-system get pods -o wide
kubectl -n longhorn-system get volumes.longhorn.io
kubectl -n longhorn-system get engines.longhorn.io,replicas.longhorn.io
```

For Longhorn, do not stop at `kubectl get pods`. A namespace full of `Running` pods does not prove volume health. Look for degraded volumes, detached volumes, failed replicas, rebuilding replicas, missing engines, and instance-manager churn.

Also identify which Kubernetes nodes are storage-bearing nodes. In a simple worker pool, that may be obvious. In a real cluster, confirm it from Longhorn placement and replica state instead of assuming every worker has the same blast radius.

## Split Nodes By Failure Domain

For RKE2 maintenance, avoid a single list of hosts named `all_nodes`. Split the work by role and risk:

```text
control-plane / etcd nodes
regular workers
storage-bearing workers
```

That split matters because each group has different stop criteria.

Control-plane and etcd nodes should be rebooted in small batches, usually one at a time unless the cluster design and quorum math explicitly allow more. Regular workers can be drained and rebooted in controlled batches if workload disruption budgets allow it. Storage-bearing workers should be excluded when Longhorn is degraded unless the recovery plan specifically requires touching one.

The dangerous shortcut is to treat a successful first batch as proof that the next batch is safe. The first batch only proves that the first failure domain survived.

## Gate Every Batch

Use boring checks between every batch. The point is not to collect impressive output. The point is to decide whether the next reboot is allowed.

Control-plane and etcd gates:

```bash
kubectl get nodes -o wide
kubectl -n kube-system get pods -l component=etcd -o wide
sudo rke2 etcd-snapshot ls
sudo ETCDCTL_API=3 etcdctl endpoint health \
  --cacert=/var/lib/rancher/rke2/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/rke2/server/tls/etcd/client.crt \
  --key=/var/lib/rancher/rke2/server/tls/etcd/client.key \
  --endpoints=https://127.0.0.1:2379
```

Cluster gates:

```bash
kubectl get nodes
kubectl get pods -A --field-selector=status.phase!=Running
kubectl get events -A --sort-by=.lastTimestamp
```

Longhorn gates:

```bash
kubectl -n longhorn-system get pods -o wide
kubectl -n longhorn-system get volumes.longhorn.io
kubectl -n longhorn-system get replicas.longhorn.io
```

For a reusable version of the Longhorn storage checks, see the public [`ops-toolbox` Longhorn utilities](https://github.com/trinidadgithub/ops-toolbox/tree/main/kubernetes/longhorn). The scheduler pressure report is especially useful before deciding whether a storage-bearing node is safe to reboot. If `longhornctl` is part of the operator workstation, keep its role explicit; see [Longhornctl Workstation Install And Operations Boundary](/field-notes/longhornctl-workstation-install-operations-boundary/).

Continue only when the previous batch has returned to the expected baseline. If the baseline already includes degraded storage, write down that accepted condition. Do not let a known pre-existing degraded state hide a new regression.

## Verify The Host Actually Rebooted

Automation can report success while a host never restarted. SSH sessions can reconnect to the same boot. A reboot command can be skipped by sudo policy, shell behavior, or a wrapper script.

Check the boot ID before and after maintenance:

```bash
cat /proc/sys/kernel/random/boot_id
uptime -s
```

Record the pre-reboot boot ID, issue the reboot, wait for SSH and Kubernetes readiness, then confirm the boot ID changed. This is a small check, but it prevents a false sense of completion during a long maintenance window.

## Drain Regular Workers, Not Storage Blindly

For regular workers, use the normal Kubernetes maintenance shape:

```bash
kubectl cordon worker-1
kubectl drain worker-1 --ignore-daemonsets --delete-emptydir-data
sudo reboot
kubectl uncordon worker-1
```

Then confirm the node and pods recovered:

```bash
kubectl get node worker-1 -o wide
kubectl get pods -A -o wide --field-selector spec.nodeName=worker-1
```

Do not apply that same pattern blindly to storage-bearing workers while Longhorn is degraded. Draining can move workload pods, but it does not magically make storage safe. A reboot can interrupt the only healthy replica path for a volume that is already degraded.

Storage nodes need their own decision point:

```text
Is the affected volume healthy enough to lose this node temporarily?
Are replicas placed on other healthy nodes?
Is a rebuild in progress?
Is the engine attached to this host?
Is this node carrying the only remaining good replica for any volume?
```

If those answers are unknown, the safe action is to skip the storage node and continue with lower-risk nodes only.

## Keep Temporary Access Temporary

Maintenance windows often require short-lived access helpers: temporary sudo rules, one-time SSH keys, a jump-host allowance, or an emergency operator account. Those changes should be part of the runbook, not a forgotten side effect. If Kubernetes is used to deliver host access, treat that as a host mutation; see [Temporary Privileged DaemonSets Are Host Access Changes](/field-notes/temporary-privileged-daemonset-maintenance-access/).

Track them explicitly:

```text
create temporary access
perform maintenance
verify cluster health
remove temporary access
verify access was removed
```

Cleanup is not administrative polish. It is part of returning the platform to its normal security baseline.

## Stop Criteria

For this kind of work, stop criteria should be written before the first reboot.

Stop if:

- etcd health fails after a control-plane reboot.
- a control-plane node does not return `Ready` within the expected window.
- new Longhorn volumes become degraded or faulted.
- replica rebuilds begin unexpectedly on nodes still scheduled for reboot.
- workload disruption exceeds the approved maintenance impact.
- the next node is storage-bearing and Longhorn placement is not understood.

The stop decision is easier when the plan has already said what evidence matters.

## The Pattern

The safest shape from this maintenance window was:

1. Capture Kubernetes, etcd, and Longhorn state.
2. Group nodes by role and storage risk.
3. Reboot control-plane and etcd nodes in small batches with quorum checks.
4. Reboot regular workers through cordon, drain, reboot, uncordon.
5. Exclude storage-bearing workers while Longhorn is degraded unless a specific recovery plan requires them.
6. Verify each host with boot IDs, not just SSH availability.
7. Gate every batch on Kubernetes, etcd, and Longhorn health.
8. Remove temporary maintenance access before closing the window.

A reboot runbook is successful when it makes the next action obvious: continue, pause, or stop. Longhorn degradation removes the margin for vague sequencing. Treat every reboot as a storage-aware change, and the maintenance window becomes much easier to control.
