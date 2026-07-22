+++
title = 'Kubernetes Upgrade Sequencing'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Upgrade sequencing model for Rancher-managed Kubernetes clusters, including readiness checks, maintenance windows, node drains, PodDisruptionBudgets, rollback planning, and post-upgrade validation.'
tags = ['kubernetes', 'rancher', 'upgrades', 'operations']
categories = ['projects']
+++

Kubernetes upgrades should be treated as controlled production changes, not package updates. The same applies to node operating-system patching when automatic updates can restart services, touch device handling, or trigger storage churn. See [Ubuntu Unattended Upgrades Are Kubernetes Node Changes](/posts/ubuntu-unattended-upgrades-kubernetes-node-risk/) for the node patching failure pattern.

The hard part is rarely clicking upgrade. The hard part is sequencing the change so operators know what can fail, what is safe to continue, and when to stop.

Related incident pattern: [When A Latent Rancher Worker Upgrade Becomes An Outage](/posts/rancher-system-upgrade-controller-latent-worker-risk/) shows how an unfinished worker `system-upgrade-controller` Plan can become disruptive when worker capacity collapses and GitOps keeps restoring the Plan. For management-cluster upgrade preparation, see [Rancher Management Cluster Upgrades Need More Than A Version Target](/posts/rancher-management-cluster-upgrade-preflight/). For post-preflight execution, see [Rancher RKE2 Minor Hops When UI Metadata And GitOps Plans Disagree](/posts/rancher-rke2-minor-hop-gitops-suc/). For node reboot sequencing under storage pressure, see [RKE2 Node Reboots When Longhorn Is Already Degraded](/posts/rke2-node-reboots-longhorn-degraded-risk/).

## Upgrade Principles

Use a conservative model:

- upgrade non-production first.
- upgrade one minor version at a time unless the vendor path explicitly supports otherwise.
- keep control-plane, etcd, and worker sequencing explicit.
- drain nodes intentionally rather than relying on surprise evictions.
- validate platform add-ons before application teams validate workloads.
- define rollback and stop criteria before the maintenance window starts.

For Rancher-managed clusters, also validate Rancher support for the target Kubernetes/RKE2/K3s version before scheduling the work.

## Pre-Upgrade Readiness

Before the window, capture the current state:

```bash
kubectl version
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running
kubectl get events -A --sort-by=.lastTimestamp
kubectl get pdb -A
kubectl get storageclass
kubectl get pv,pvc -A
```

Check the platform add-ons:

```bash
kubectl get pods -n cattle-system
kubectl get pods -n fleet-system
kubectl get pods -n kube-system
kubectl get pods -n cert-manager
kubectl get pods -n vmware-system-csi
```

The cluster should not enter an upgrade with unresolved node pressure, broken CSI, pending system controllers, expired certificates, or a backlog of failed platform pods.

## Workload Disruption Review

Node upgrades eventually become workload movement.

Before draining nodes, check which workloads can tolerate voluntary disruption:

```bash
kubectl get pdb -A
kubectl get deployments,statefulsets,daemonsets -A
```

PodDisruptionBudgets are important because `kubectl drain` respects the eviction API. That is useful protection, but it can also block maintenance if budgets are too strict or replicas are already unhealthy.

Review for:

- singleton workloads with no maintenance plan.
- StatefulSets with storage that cannot move cleanly.
- PDBs requiring more available replicas than currently exist.
- workloads pinned to a single worker.
- DaemonSets that are expected to remain during drain.

If the workload cannot move during an upgrade, the maintenance plan should say that explicitly.

## Suggested Sequence

For a highly available Rancher-managed cluster, use this general order:

1. Validate backups and restore expectations.
2. Confirm Rancher supports the target cluster version.
3. Upgrade a non-production cluster first.
4. Pause or hold unrelated GitOps changes.
5. Upgrade control-plane and etcd components according to the Rancher/RKE2 plan.
6. Upgrade worker pools one node or one controlled batch at a time.
7. Validate platform services.
8. Validate application workloads.
9. Re-enable normal GitOps flow.
10. Capture post-upgrade notes and follow-ups.

The exact implementation depends on Rancher, RKE2, K3s, or managed Kubernetes provider behavior. The operational point is that each stage has a checkpoint.

## Node Drain Pattern

For manual or assisted worker maintenance, the safe pattern is:

```bash
kubectl cordon <node>
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
```

Then perform the node upgrade or VM maintenance.

After the node returns:

```bash
kubectl uncordon <node>
kubectl get node <node> -o wide
kubectl describe node <node>
```

Validate that the node is `Ready`, has no unexpected taints, and that DaemonSets returned.

## Maintenance Window Rules

A maintenance window should include:

- target clusters and versions.
- expected order of operations.
- named operator and reviewer.
- communication channel.
- stop criteria.
- rollback or restore decision point.
- validation commands.
- known workloads with disruption risk.

Avoid combining an upgrade with unrelated changes. If GitOps, storage, ingress, and node image changes are all moving at the same time, troubleshooting becomes guesswork.

## Stop Criteria

Stop the upgrade if any of these appear:

- etcd health is uncertain.
- more than one control-plane node is unhealthy in an HA cluster.
- Rancher agents stop reporting correctly.
- CSI attach or mount behavior fails after a worker upgrade.
- CNI or DNS fails cluster-wide.
- platform controllers are crashlooping.
- application disruption exceeds the agreed window.

Stopping is not failure. Continuing without a stable checkpoint is the failure.

## Post-Upgrade Validation

After the upgrade, validate from the platform outward:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running
kubectl get events -A --sort-by=.lastTimestamp
kubectl get deployments,statefulsets,daemonsets -A
kubectl get pdb -A
kubectl get volumeattachments -A 2>/dev/null || kubectl get volumeattachments
```

For Rancher and Fleet:

```bash
kubectl get pods -n cattle-system
kubectl get pods -n fleet-system
kubectl get gitrepos -A
kubectl get bundles -A
kubectl get bundledeployments -A
```

Also verify functional paths:

- Rancher UI login through AD.
- local break-glass login still works if tested as part of the runbook.
- workload ingress responds.
- DNS resolves service names.
- CSI can attach and mount a test volume.
- monitoring receives fresh samples after the window.

## Rollback Planning

Rollback for Kubernetes upgrades is often constrained. That is why pre-upgrade backups and stop points matter.

The plan should define:

- etcd snapshot location and restore owner.
- Rancher backup location and restore owner.
- node image or VM snapshot policy, if used.
- whether workload rollback means cluster rollback, application rollback, or both.
- who can approve restore.

Do not rely on a generic "rollback if needed" line. Write the actual decision tree.

## Acceptance Criteria

An upgrade is complete when:

- all nodes are `Ready` and schedulable unless intentionally cordoned.
- control-plane and worker versions match the target plan.
- Rancher and Fleet controllers are healthy.
- platform add-ons are healthy.
- no new cluster-wide event pattern is emerging.
- storage, ingress, DNS, and monitoring have been functionally tested.
- application owners have completed their agreed validation.
- follow-up work is captured outside the maintenance window.

## References

- Kubernetes documentation: Upgrade A Cluster.
- Kubernetes documentation: Safely Drain a Node.
- Kubernetes documentation: Specifying a Disruption Budget for your Application.
- Rancher documentation: Cluster administration and upgrade guidance for managed clusters.
