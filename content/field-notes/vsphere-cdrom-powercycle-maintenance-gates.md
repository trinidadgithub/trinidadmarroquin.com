+++
title = 'vSphere CD-ROM Cleanup With Power-Cycle Gates'
date = 2026-08-13T00:00:00-05:00
draft = false
description = 'Field note for removing stale vSphere CD-ROM devices from Kubernetes VMs by combining cordon, drain, powered-off device removal, boot ID verification, and storage-specific health gates.'
tags = ['vsphere', 'vmware', 'govc', 'kubernetes', 'longhorn', 'maintenance', 'operations']
categories = ['field-notes']
+++

The first version of a vSphere CD-ROM cleanup runbook treated device removal as a live VM reconfigure task. That worked for some VMs, but it also exposed a bad assumption: a CD-ROM change on a running Kubernetes VM is still a VM reconfigure operation, and VM reconfigure operations can disturb guest responsiveness, kubelet status, API availability, and storage controllers.

The safer pattern was to stop trying to make CD-ROM removal invisible. Treat it as node maintenance:

```text
cordon or drain
power off
remove unused CD-ROM
power on
wait for Ready and a new boot ID
uncordon
run role-specific health checks
```

That converts an unpredictable live reconfigure into one planned disruption window per VM.

## Why Power Off First

Powered-off removal avoids the most fragile part of the earlier flow: changing virtual hardware while the guest is still serving Kubernetes traffic.

It also lets the operator combine two related tasks when appropriate:

```text
remove stale virtual media
activate already-installed kernel updates
```

That combination should still be intentional. It is easier to troubleshoot a node reboot than a live reconfigure that briefly stuns the guest and leaves every layer guessing whether the symptom came from vCenter, kubelet, etcd, storage, or workload rescheduling.

## Dry-Run Must Show The Real Order

The dry-run should be specific enough that another operator can approve or reject it without reading the script.

Useful dry-run output includes:

```text
target cluster and vCenter folder
VM path
mapped Kubernetes node name
node role
cordon behavior
drain behavior
CD-ROM device selected for removal
whether boot ID verification is required
whether non-Kubernetes VMs are allowed
include and exclude filters
```

If the tool supports regex targeting, use it to resume partial runs safely:

```bash
remediate-cdrom-powercycle.sh \
  --include-regex 'cluster-a-(etcd-[2-5]|worker-[1-5])' \
  cluster-a prod
```

Do not rely on naming convention alone. The runbook should map each VM to the Kubernetes node case-insensitively, classify the role, and print the exact plan before `--execute` is allowed.

## Role Gates

Not every VM in a Kubernetes folder should be handled the same way.

API load balancers or other non-Kubernetes support VMs can be power-cycled without `kubectl cordon` or `kubectl drain`, but that should require an explicit `--allow-non-nodes`-style flag.

Workers should normally be cordoned and drained:

```bash
kubectl cordon worker-1
kubectl drain worker-1 --ignore-daemonsets --delete-emptydir-data --timeout=6m
```

Control-plane and etcd nodes should not be treated like normal workers. Static pods cannot be evicted the same way workload pods can, and etcd sensitivity changes the risk model. Cordon them, power-cycle one at a time, and make the health checks explicit.

For each Kubernetes node, require these gates before moving on:

```bash
kubectl get node worker-1 -o jsonpath='{.status.nodeInfo.bootID}{"\n"}'
kubectl wait node/worker-1 --for=condition=Ready --timeout=15m
kubectl uncordon worker-1
kubectl get nodes
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
```

The boot ID check matters. A node becoming reachable again is not the same as proving the intended reboot happened and Kubernetes observed the new boot.

## Longhorn Nodes Need Storage Gates

Storage nodes are not just workers with different labels. Before power-cycling a Longhorn storage node, check whether the cluster can tolerate losing one replica host.

The precheck should answer three questions:

```text
Are all attached volumes healthy?
Does each attached volume have enough running replicas on distinct storage nodes?
Are Longhorn system pods and Longhorn nodes healthy?
```

Useful checks:

```bash
kubectl -n longhorn-system get volumes.longhorn.io
kubectl -n longhorn-system get replicas.longhorn.io
kubectl -n longhorn-system get nodes.longhorn.io
kubectl -n longhorn-system get pods
```

If attached volumes are already degraded or rebuilding, stop before touching a storage node.

After each storage node returns, wait for attached volumes to return to `healthy` before starting the next node. A temporary degraded state is expected while one replica host is down or recovering. Moving to the next storage node before recovery turns a controlled one-replica loss into a possible availability incident.

The closeout gate should be boring:

```text
all storage nodes Ready
all attached Longhorn volumes healthy
no Longhorn pods unhealthy
no Kubernetes nodes cordoned
```

## Handle Tool Bugs Like Change Failures

One useful failure mode from this maintenance pattern was a command syntax bug: one `govc` subcommand expected the VM path as a positional argument while device subcommands used `-vm`. The first execute attempt failed before making a change.

That is a good outcome only if the runbook handles it like a production change failure:

```text
stop the background run
verify no VM was changed
verify no nodes are cordoned
verify all nodes are Ready
patch the tool
syntax-check the tool
run a targeted dry-run
test the corrected govc command against one VM
then relaunch inside the window
```

Do not rush past a failed first command just because the maintenance window is open. The safest run is the one that proves the failure was contained before retrying.

## Final Evidence

At the end, collect evidence from both platforms.

vSphere desired state:

```text
VMs audited: 20
VMs with no CD/DVD device: 20
CD/DVD devices connected or start-connected: 0
```

Kubernetes desired state:

```text
all nodes Ready
zero cordoned nodes
no unexpected non-running pods
control-plane and etcd pods healthy
storage volumes healthy
```

Those checks are the difference between "the script finished" and "the maintenance is complete."

## Operating Rule

If live VM hardware cleanup causes Kubernetes symptoms, redesign the method instead of adding more retries.

For Kubernetes VMs, stale CD-ROM removal is safest when it is a planned power-cycle with dry-run evidence, explicit role gates, boot ID verification, and storage-specific stop conditions.
