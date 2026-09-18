+++
title = 'Kubernetes OS Maintenance Needs Storage Safety Gates'
date = 2026-09-17T00:00:00-05:00
draft = false
description = 'Field note for staging and applying Ubuntu OS updates on Kubernetes nodes while separating firmware, phased packages, etcd quorum, drain retries, and Longhorn degraded-volume risk.'
tags = ['kubernetes', 'linux', 'ubuntu', 'longhorn', 'maintenance', 'operations']
categories = ['field-notes']
+++

Updating Kubernetes nodes is not just an `apt-get dist-upgrade` loop.

The safe boundary is different for package download staging, package application, reboot, etcd quorum, CSI detach behavior, and Longhorn replica health. A node can be Ready and still be the wrong node to reboot next.

## Separate Staging From Applying

Use download-only staging when the goal is to warm package caches before a maintenance window:

```bash
sudo bash -lc '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=300 update -qq
apt-get -y \
  -o DPkg::Lock::Timeout=300 \
  --download-only \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold \
  dist-upgrade
echo "STAGED_DOWNLOAD_ONLY rc=0"
echo "upgradable_count=$(apt list --upgradable 2>/dev/null | grep -c upgradable)"
echo "cache_mb=$(du -sm /var/cache/apt/archives 2>/dev/null | awk '\''{print $1}'\'')"
echo "reboot_required=$(test -f /var/run/reboot-required && echo YES || echo no)"
'
```

After download-only staging, `apt list --upgradable` can still show the same updates. That is expected. The packages were downloaded, not installed.

Verify the staging boundary:

```bash
apt list --upgradable 2>/dev/null | grep -c upgradable
du -sh /var/cache/apt/archives
test -f /var/run/reboot-required && echo 'reboot_required=YES' || echo 'reboot_required=no'
uname -r
```

The running kernel should not change during staging.

## Keep Firmware Out Of The OS Pipeline

`fwupdmgr` is not part of an OS package staging pipeline.

If the maintenance task is Ubuntu package patching, do not run this as a side quest:

```bash
fwupdmgr update
```

Firmware updates can touch UEFI dbx, Secure Boot state, device firmware, and reboot behavior. Track them as a separate maintenance class with a separate rollback and vendor-risk decision.

## Apply One Node At A Time

For the apply phase, cordon and drain first:

```bash
kubectl --context cluster-a cordon worker-1
kubectl --context cluster-a drain worker-1 \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --timeout=300s
```

Then apply packages on the node:

```bash
sudo bash -lc '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=300 update -qq
apt-get -y \
  -o DPkg::Lock::Timeout=300 \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold \
  dist-upgrade
apt list --upgradable 2>/dev/null | grep -c upgradable
test -f /var/run/reboot-required && echo "reboot_required=YES" || echo "reboot_required=no"
'
```

Reboot only after the package phase completes:

```bash
sudo reboot
```

Wait for Kubernetes to see the node again:

```bash
kubectl --context cluster-a wait --for=condition=Ready node/worker-1 --timeout=600s
kubectl --context cluster-a get node worker-1 \
  -o custom-columns='NODE:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,KERNEL:.status.nodeInfo.kernelVersion'
```

Then uncordon:

```bash
kubectl --context cluster-a uncordon worker-1
```

## Treat Roles Differently

Workers, control-plane nodes, and etcd nodes do not carry the same blast radius.

Recommended order for a conventional RKE2 cluster:

```text
monitor/utility nodes
etcd nodes, one at a time with quorum checks
control-plane nodes, one at a time
workers, one at a time or in small batches only if workload and storage allow it
```

For etcd, verify quorum between nodes:

```bash
kubectl --context cluster-a -n kube-system exec etcd-cp-1 -- \
  etcdctl endpoint health --cluster --write-out=table
```

Do not let a successful SSH reboot outrun Kubernetes state. Wait for the node and core pods to settle before moving to the next control-plane or etcd member.

## Distinguish Transient Drain Failures

Not every drain failure has the same meaning.

A transient API or tunnel error while evicting a pod may be retryable after the previous node settles:

```text
error trying to reach service: tunnel disconnect
error when evicting pod ...
```

Before retrying, check current state:

```bash
kubectl --context cluster-a get nodes \
  -o custom-columns='NODE:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,SCHED:.spec.unschedulable,KERNEL:.status.nodeInfo.kernelVersion'

kubectl --context cluster-a get pods -A \
  --field-selector=status.phase!=Running,status.phase!=Succeeded
```

If the previous node is still `Unknown` or important pods are still rescheduling, wait. Retrying immediately can stack failures.

## Stop On Longhorn Replica Risk

Longhorn deserves a separate gate.

An `instance-manager-*` PodDisruptionBudget blocking eviction is not just annoying drain noise. It says the storage layer is in the disruption path.

Stop if the next node has degraded attached volumes where the only running replica is on that same node:

```text
volume-a degraded, only running replica on worker-2
volume-b degraded, only running replica on worker-2
```

Rebooting that node can fault those volumes. The safe response is:

```text
1. Stop the rollout.
2. Uncordon the node if the drain already cordoned it.
3. Record which volumes block maintenance.
4. Restore Longhorn replica redundancy or get explicit risk acceptance.
5. Resume only after storage is healthy or the business accepts the risk.
```

Do not bypass the Longhorn PDB just because every Kubernetes node still says Ready.

## Handle Phased Packages Intentionally

Ubuntu phased updates can leave a small set of packages upgradable after the main patch run. Common examples include libraries or network tooling that are held back by phasing.

Record them separately:

```bash
apt list --upgradable 2>/dev/null
```

If you force-install them, do it as an explicit cleanup step and recheck `reboot_required`. Do not hide phased-package cleanup inside the main reboot loop without saying so.

## Operating Rule

A safe Kubernetes OS maintenance run proves more than package success.

The minimum evidence bundle should show:

```text
download-only staging completed, if used
firmware excluded or separately approved
node cordon/drain completed
package apply completed
reboot issued only after apply completed
node returned Ready
kernel version matches expectation
node uncordoned
no non-running pods after settle
PVCs bound
etcd healthy after each etcd node
Longhorn volumes healthy before storage-node reboot
remaining phased packages documented or cleaned up
```

For maintenance evidence collection, see [Kubernetes Maintenance Evidence Bundles Need A Redaction Plan](/field-notes/kubernetes-maintenance-evidence-bundles/). For temporary host access during maintenance windows, see [Temporary Privileged DaemonSets Are Host Access Changes](/field-notes/temporary-privileged-daemonset-maintenance-access/).
