+++
title = 'Rancher RKE2 Minor Hops When UI Metadata And GitOps Plans Disagree'
date = 2026-07-16T00:00:00-05:00
draft = false
description = 'A practical Rancher and RKE2 upgrade article covering supported minor hops, Rancher UI version metadata, GitOps-managed system-upgrade-controller plans, stale runtime shims, and post-upgrade cleanup gates.'
tags = ['rancher', 'rke2', 'kubernetes', 'gitops', 'argocd', 'upgrades', 'operations']
categories = ['posts']
+++

The hard part of a Rancher-managed RKE2 upgrade is not always clicking the target version. The hard part is keeping every control plane that thinks it owns the upgrade aligned:

- Kubernetes version-skew rules.
- Rancher UI version metadata.
- Rancher's desired cluster version.
- `system-upgrade-controller` Plans.
- GitOps reconciliation for those Plans.
- node-level runtime cleanup after the upgrade.

In one management-cluster upgrade, the safe Kubernetes path was clear:

```text
v1.31 -> v1.32 -> v1.33
```

But Rancher only advertised newer versions in the UI after the Rancher application itself was upgraded. The UI could offer `v1.33` while the cluster still needed the intermediate `v1.32` hop. That is where an otherwise normal upgrade becomes an ownership problem.

## Do Not Skip The Minor Hop

If the current cluster is on `v1.31`, do not jump directly to `v1.33` just because the UI dropdown offers it.

Use the normal Kubernetes minor-hop model:

```text
current: v1.31.x+rke2r1
next:    v1.32.x+rke2r1
then:    v1.33.x+rke2r1
```

Check the Rancher cluster object before changing anything:

```bash
kubectl get clusters.management.cattle.io local \
  -o jsonpath='{.spec.rke2Config.kubernetesVersion}{"\t"}{.status.version.gitVersion}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\t"}{.status.conditions[?(@.type=="Connected")].status}{"\n"}'
```

If desired and actual versions disagree before the upgrade, pause and understand why. Rancher warnings about version mismatch usually mean the cluster was changed outside the same Rancher control path.

## When The UI Cannot Offer The Intermediate Version

Rancher version metadata can move forward faster than the cluster you are repairing. A newer Rancher release may advertise only a newer supported range, while your cluster still needs one intermediate minor.

When that happens, do not use the UI to skip ahead. Inspect `system-upgrade-controller` instead:

```bash
kubectl -n system-upgrade get deploy,pods,plans
kubectl -n system-upgrade get plan server-plan -o yaml
kubectl -n system-upgrade get plan agent-plan -o yaml
```

Healthy plan shape for a conservative management-cluster upgrade:

```text
server plan: concurrency 1
agent plan:  concurrency 1
agent waits on server plan
```

If the controller deployment is scaled to `0`, treat that as a deliberate emergency brake until proven otherwise. First identify who owns that replica count.

## GitOps May Own The Upgrade Controller

If Argo CD, Fleet, or another GitOps system manages the upgrade controller and Plans, live patches may not hold.

Symptoms:

```text
kubectl patch succeeds
minutes later the old value returns
system-upgrade-controller replicas returns to 0
Plan version returns to the previous RKE2 version
```

In that case, the real change belongs in Git, not directly in the cluster.

Before changing GitOps desired state, capture evidence:

```bash
BACKUP_DIR="$HOME/rancher-upgrade-backups/pre-v132-local-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

kubectl get nodes -o wide > "$BACKUP_DIR/kubectl-get-nodes-wide.txt"
kubectl get pods -A -o wide > "$BACKUP_DIR/kubectl-get-pods-all-wide.txt"
kubectl get events -A --sort-by=.lastTimestamp > "$BACKUP_DIR/kubectl-get-events-all.txt"
kubectl -n system-upgrade get plans -o yaml > "$BACKUP_DIR/system-upgrade-plans.yaml"
kubectl get clusters.management.cattle.io local -o yaml > "$BACKUP_DIR/rancher-local-management-cluster.yaml"
helm -n cattle-system get values rancher > "$BACKUP_DIR/rancher-helm-values.yaml"
helm -n cattle-system list > "$BACKUP_DIR/helm-list-cattle-system.txt"
```

Also take an etcd snapshot from a control-plane node or an equivalent approved backup path:

```bash
sudo rke2 etcd-snapshot save --name pre-v132-local-$(date +%Y%m%d-%H%M%S)
```

Then make the smallest GitOps change required for the intermediate hop:

```text
system-upgrade-controller replicas: 1
server-plan version: v1.32.x+rke2r1
agent-plan version:  v1.32.x+rke2r1
```

Render the overlay before publishing it:

```bash
kustomize build path/to/system-upgrade/overlay >/tmp/system-upgrade.rendered.yaml
```

## Monitor With Polling During Control-Plane Restarts

Watch streams often break during control-plane upgrades:

```text
unable to decode an event from the watch stream
stream error: INTERNAL_ERROR
```

That message is not automatically an upgrade failure. It can just mean the API server connection reset while control-plane components restarted.

Use polling loops instead of `-w` during disruptive phases:

```bash
while true; do
  clear
  date
  echo "== Nodes =="
  kubectl get nodes -o wide
  echo
  echo "== Plans =="
  kubectl -n system-upgrade get plans
  echo
  echo "== Upgrade Pods/Jobs =="
  kubectl -n system-upgrade get pods,jobs
  sleep 15
done
```

Expected sequence:

```text
server-plan runs first
control-plane nodes move one at a time
server-plan reaches Complete
agent-plan runs next
workers move one at a time
agent-plan reaches Complete
Rancher desired version and actual version match
```

## Align GitOps After A UI-Driven Hop

Once the cluster reaches the intermediate version and Rancher desired/actual versions match, the UI may become safe for the next minor hop.

If Rancher UI performs that upgrade, check the GitOps-managed Plans afterward:

```bash
kubectl -n system-upgrade get plans
kubectl get clusters.management.cattle.io local \
  -o jsonpath='{.spec.rke2Config.kubernetesVersion}{"\t"}{.status.version.gitVersion}{"\n"}'
```

Possible final state:

```text
Rancher desired: v1.33.x+rke2r1
Rancher actual:  v1.33.x+rke2r1
SUC Plans:       v1.32.x+rke2r1
```

That means the cluster upgraded, but GitOps still describes the previous Plan version. Update the GitOps overlay to match the completed version. This should be a no-op for node upgrades if every node is already on the target, but it prevents the next reconciliation from fighting the real state.

## Cleanup: Old Runtime Shims Can Survive The Upgrade

After RKE2 upgrades, the active binary symlink should point at the new data directory:

```bash
readlink -f /var/lib/rancher/rke2/bin
```

But orphaned `containerd-shim-runc-v2` processes can keep executing from the old RKE2 data directory:

```text
/var/lib/rancher/rke2/data/v1.31.x-rke2r1-.../bin/containerd-shim-runc-v2
```

First ask containerd and CRI whether they still know about the containers:

```bash
sudo /var/lib/rancher/rke2/bin/crictl \
  --runtime-endpoint unix:///run/k3s/containerd/containerd.sock ps -a

sudo /var/lib/rancher/rke2/bin/ctr \
  --address /run/k3s/containerd/containerd.sock \
  --namespace k8s.io tasks ls
```

If the old shim PIDs are invisible to the current runtime, they are likely orphaned. The cleanest remediation is a one-node-at-a-time reboot, not deleting old data directories while processes still execute from them.

For control-plane nodes:

```bash
kubectl cordon cp-1
ssh -tt operator@cp-1.example.com 'sudo reboot'
kubectl wait node/cp-1 --for=condition=Ready --timeout=15m
kubectl uncordon cp-1
```

## Reboot Automation Needs A Real Reboot Gate

A naive reboot script can finish too early because Kubernetes may still report stale `Ready=True` shortly after the reboot command is sent.

Better gates:

- capture the node's pre-reboot Kubernetes `bootID`.
- if passwordless SSH is available, capture the host's `/proc/sys/kernel/random/boot_id` before reboot.
- after reboot, require SSH to return and the host boot ID to change.
- then require Kubernetes `Ready=True` and, when available, Kubernetes `bootID` to change.

Kubernetes readiness alone is not enough immediately after sending the reboot command. It can be cached long enough to fool automation.

## Acceptance Criteria

Call the minor hop complete only when these are true:

- Rancher desired version matches Rancher reported actual version.
- every node reports the target RKE2 version.
- `server-plan` and `agent-plan` are complete or intentionally aligned to the completed version.
- GitOps desired state matches the live Plan versions and controller replica count.
- Rancher, Fleet, webhooks, ingress, CNI, and DNS are healthy.
- old RKE2 data directories are not held by live shim processes, or reboot cleanup is scheduled.
- the next minor target is planned, not guessed from the newest UI option.

The operating rule is simple: Rancher can drive the upgrade, but GitOps and node runtime state still need reconciliation. The upgrade is not done when the UI says the version changed. It is done when every owner of that version agrees.

Related: [Rancher RKE2 Upgrade Pods Mutate The Host Filesystem](/field-notes/rancher-rke2-upgrade-pods-host-filesystem/) explains the node-local host filesystem update pattern behind Rancher-managed upgrade Jobs.
