+++
title = 'Rancher RKE2 Upgrade Pods Mutate The Host Filesystem'
date = 2026-07-17T00:00:00-05:00
draft = false
description = 'Field note for understanding Rancher-managed RKE2 upgrade pods: how system-upgrade-controller runs pods on nodes, mounts the host filesystem, replaces RKE2 binaries, restarts services, and leaves post-upgrade signals to verify.'
tags = ['rancher', 'rke2', 'kubernetes', 'system-upgrade-controller', 'upgrades', 'operations']
categories = ['field-notes']
+++

Rancher-managed RKE2 upgrades are Kubernetes workflows that intentionally mutate node-local filesystems.

That sounds odd until you inspect an upgrade pod. The pod is scheduled onto the node being upgraded, mounts host paths, compares the new RKE2 binary inside the upgrade image with the host binary, replaces the host binary, and restarts the node service.

That is the useful mental model:

```text
Rancher desired version
  -> system-upgrade-controller Plan
  -> upgrade Job/Pod on each selected node
  -> host filesystem mounted under /host
  -> RKE2 binary/config/service update on that node
  -> node restarts components and rejoins
```

The pod is not just a health check. It is the delivery mechanism for node-local changes.

## Pre-Upgrade Evidence First

Before letting a Rancher-managed plan move a cluster, capture state from both the target cluster and Rancher management cluster.

Target cluster captures:

```bash
BACKUP_DIR="$HOME/rancher-upgrade-backups/pre-v134-cluster-a-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

kubectl get nodes -o wide > "$BACKUP_DIR/kubectl-get-nodes-wide.txt"
kubectl get pods -A -o wide > "$BACKUP_DIR/kubectl-get-pods-all-wide.txt"
kubectl get events -A --sort-by=.lastTimestamp > "$BACKUP_DIR/kubectl-get-events-all.txt"
kubectl get storageclasses -o yaml > "$BACKUP_DIR/storageclasses.yaml"
kubectl get pv -o yaml > "$BACKUP_DIR/persistentvolumes.yaml"
kubectl get pvc -A -o yaml > "$BACKUP_DIR/persistentvolumeclaims.yaml"
kubectl get ingress -A -o yaml > "$BACKUP_DIR/ingresses.yaml"
kubectl get services -A -o wide > "$BACKUP_DIR/services-wide.txt"
kubectl get apiservices -o yaml > "$BACKUP_DIR/apiservices.yaml"
kubectl get crds -o wide > "$BACKUP_DIR/crds-wide.txt"
kubectl get namespaces -o yaml > "$BACKUP_DIR/namespaces.yaml"
kubectl get plans -A -o yaml > "$BACKUP_DIR/system-upgrade-plans.yaml"
kubectl get pods,jobs -A | grep -i upgrade > "$BACKUP_DIR/system-upgrade-pods-jobs.txt" || true
```

Rancher management captures:

```bash
kubectl --context rancher-mgmt get clusters.management.cattle.io -o yaml \
  > "$BACKUP_DIR/rancher-management-clusters.yaml"

kubectl --context rancher-mgmt get clusters.provisioning.cattle.io -A -o yaml \
  > "$BACKUP_DIR/rancher-provisioning-clusters.yaml"

kubectl --context rancher-mgmt get clusters.fleet.cattle.io -A -o yaml \
  > "$BACKUP_DIR/fleet-clusters.yaml"

kubectl --context rancher-mgmt get bundles.fleet.cattle.io -A -o yaml \
  > "$BACKUP_DIR/fleet-bundles.yaml"

kubectl --context rancher-mgmt get bundledeployments.fleet.cattle.io -A -o yaml \
  > "$BACKUP_DIR/fleet-bundledeployments.yaml"
```

Also take an etcd snapshot and control-plane file archives according to the platform runbook. Verify the artifacts, not just the commands:

```bash
tar tzf control-plane-backup.tgz >/dev/null
ls -lh etcd-snapshot-name
```

Non-empty `.err` files are not automatically failures. For example, Kubernetes `v1.33+` can warn that core `Endpoints` is deprecated. Classify warnings separately from failed captures.

## Know Which Plans Are Active

Rancher can create managed Plans in `cattle-system` while older GitOps-managed Plans still exist in `system-upgrade`.

Check all Plans:

```bash
kubectl get plans -A -o wide
```

You may see both:

```text
cattle-system   rke2-master-plan   rancher/rke2-upgrade   v1.34.9+rke2r1
cattle-system   rke2-worker-plan   rancher/rke2-upgrade   v1.34.9+rke2r1
system-upgrade  server-plan        rancher/rke2-upgrade   v1.32.8+rke2r1
system-upgrade  agent-plan         rancher/rke2-upgrade   v1.32.8+rke2r1
```

Do not assume every Plan is active. Inspect labels and ownership:

```bash
kubectl -n cattle-system get plan rke2-master-plan -o yaml
kubectl -n cattle-system get plan rke2-worker-plan -o yaml
```

Rancher-managed plans commonly show signals like:

```text
metadata.labels.rancher-managed: "true"
metadata.finalizers: systemcharts.cattle.io/rancher-managed-plan
spec.concurrency: 1
spec.cordon: true
```

The worker Plan should wait for the master Plan through `prepare`, rather than upgrading workers before control-plane completion.

## The Upgrade Pod Writes Through `/host`

Inspecting a Rancher-managed upgrade pod makes the mechanism visible:

```bash
kubectl -n cattle-system get jobs,pods -o wide | grep -i rke2
kubectl -n cattle-system describe pod <upgrade-pod>
kubectl -n cattle-system logs <upgrade-pod> --previous=false
```

Log shape:

```text
[INFO] rke2 binary is running with pid 486375
RKE2_BIN_PATH=/usr/local/bin/rke2
FULL_BIN_PATH=/host/usr/local/bin/rke2
Comparing old and new binaries
sha256sum /opt/rke2 /host/usr/local/bin/rke2
```

That tells you the upgrade container sees:

```text
/opt/rke2                  new binary from the upgrade image
/host/usr/local/bin/rke2   host binary on the node
/host/proc/<pid>/cmdline   host process metadata
```

The pod is using Kubernetes scheduling to run node-local maintenance. This is why permissions, host mounts, and node selection matter.

## Labels Control The Blast Radius

Rancher-managed Plans select nodes with labels such as:

```text
upgrade.cattle.io/kubernetes-upgrade=true
```

Before the run, verify the selected nodes:

```bash
kubectl get nodes -l upgrade.cattle.io/kubernetes-upgrade=true \
  -o custom-columns=NAME:.metadata.name,VERSION:.status.nodeInfo.kubeletVersion
```

If the wrong nodes are selected, fix the labels before the controller starts new jobs:

```bash
kubectl label node worker-6 worker-9 upgrade.cattle.io/kubernetes-upgrade- --overwrite
kubectl label node cp-1 cp-2 cp-3 upgrade.cattle.io/kubernetes-upgrade=true --overwrite
```

This is especially important when moving from one hop to the next. Stale labels can make a worker Plan start before the intended control-plane sequence.

## Monitor The Rollout By Plans And Nodes

Poll instead of relying only on watches during control-plane restarts:

```bash
while true; do
  date
  kubectl get nodes -o json \
    | jq -r '.items[] | [.metadata.name, (if (.spec.unschedulable // false) then "cordoned" else "schedulable" end), .status.nodeInfo.kubeletVersion, ([.status.conditions[] | select(.type=="Ready")][0].status)] | @tsv'
  echo
  kubectl -n cattle-system get plans -o json \
    | jq -r '.items[] | [.metadata.name, ([.status.conditions[]? | select(.type=="Complete")][0].status // ""), (.status.applying // [] | join(",")), .status.latestVersion] | @tsv'
  echo
  kubectl -n cattle-system get jobs,pods -o wide | grep -i rke2 || true
  sleep 30
done
```

Completion shape:

```text
rke2-master-plan  True  v1.34.9-rke2r1
rke2-worker-plan  True  v1.34.9-rke2r1
```

Every node should be `Ready`, schedulable, and on the target version.

## Post-Upgrade Cleanup Signals

Upgrade pods often become `ContainerStatusUnknown` or `Failed` because the node restarted underneath them. If the owning Jobs are complete and Plans are complete, these pods are usually stale artifacts.

Clean them after verification:

```bash
kubectl -n cattle-system delete pod --field-selector=status.phase=Failed
```

Then check the platform add-ons:

```bash
kubectl get ds -A -o json \
  | jq -r '.items[] | select(.status.desiredNumberScheduled != .status.numberReady) | [.metadata.namespace, .metadata.name, .status.desiredNumberScheduled, .status.numberReady] | @tsv'

kubectl get deploy -A -o json \
  | jq -r '.items[] | select((.status.readyReplicas // 0) < (.spec.replicas // 1)) | [.metadata.namespace, .metadata.name, (.status.readyReplicas // 0), (.spec.replicas // 1)] | @tsv'
```

One post-upgrade symptom worth recognizing is a host-port stale bind:

```text
port 80 is already in use. Please check the flag --http-port
```

For an ingress DaemonSet pod after a node restart, deleting the one bad pod can force a fresh sandbox and clear the stale bind:

```bash
kubectl -n kube-system delete pod rke2-ingress-nginx-controller-abcde
```

Do not delete the whole DaemonSet first. Confirm the failure is isolated to one pod/node.

## Acceptance Criteria

The upgrade is complete when these are true:

- Rancher desired version and reported actual version match.
- active Rancher-managed Plans are `Complete=True`.
- all nodes are `Ready`, schedulable, and on the target RKE2 version.
- stale failed upgrade pods are cleaned after Jobs complete.
- DaemonSets and deployments are at expected ready counts.
- event scans show no current `port in use`, sandbox, PDB, or image-pull blockers.
- pre-existing unrelated workload failures are documented separately.

The operating rule: a Rancher RKE2 upgrade pod is a privileged node maintenance action packaged as a Kubernetes workload. Treat it with the same care you would give an SSH-based node patch, but use Kubernetes evidence to prove what it changed and when it is done.
