+++
title = 'Fast OS Template Node Replacement Rehearsal'
date = 2026-08-03T00:00:00-05:00
draft = false
description = 'Field note for rehearsing fast RKE2 node replacement with prebuilt powered-off VMs, one-minor upgrade sequencing, image-cache warming, identity conflict rules, and rollback gates.'
tags = ['rke2', 'kubernetes', 'rancher', 'vsphere', 'terraform', 'templates', 'upgrades', 'operations']
categories = ['field-notes']
+++

Replacing Kubernetes nodes from a fresh OS template can be faster than repairing legacy VM drift in place, but speed only helps if the risky work is moved out of the maintenance window without creating identity conflicts.

The useful rehearsal pattern is to pre-create replacement VMs from the current template, leave them powered off, and join them one at a time during the window. That turns the maintenance window into a controlled cluster-change sequence instead of a race to clone, customize, debug, and drain all at once.

## What To Move Out Of The Window

Move clone and baseline configuration work earlier:

```text
1. Terraform creates replacement VMs from the current OS template.
2. Terraform applies final hostname, static IP, DNS, NTP, routes, SSH, users, sudo policy, CPU, memory, and disks.
3. The VM is validated without joining the live cluster.
4. Optional image-cache warming pulls known large workload images into the RKE2 containerd store.
5. The VM is shut down cleanly and left powered off.
6. Terraform outputs the VM path/name, intended role, IP, and maintenance notes.
```

The acceptance check before the window is not just “Terraform applied.” It is that the replacement VM has the final identity it will use when it joins the cluster, and Terraform has no planned changes against the active old nodes unless those changes are explicitly part of the maintenance plan.

## Keep Version Skew Boring

If replacement nodes are also moving the cluster forward by one Kubernetes minor, replace server-side nodes before allowing workers or monitoring nodes to run a newer kubelet minor than the API servers.

For a conservative RKE2 replacement rehearsal:

```text
1. Control-plane nodes, beginning with non-identity-takeover replacements.
2. Etcd nodes, one at a time with explicit etcd validation.
3. Monitoring or specialized worker pools.
4. General workers.
```

If the rehearsal goal is only to prove VM power-on and RKE2 join mechanics, use a lower-risk worker-capacity proof at the current cluster version. That proves the provisioning path, but it does not prove the one-minor server-side upgrade path.

## Do Not Create Identity Conflicts

The replacement VM should join with its intended final hostname and IP. Do not join a node, then rename or re-IP it into the old identity afterward.

If old hostname or IP reuse is required, the old identity must be removed from service before the replacement joins:

```text
cordon old node
drain old node if disruption is acceptable
stop old VM or otherwise guarantee the old IP is no longer active
join replacement with the old hostname/IP from the start
```

When possible, prefer new permanent names and IPs for replacement nodes. Save identity takeover for the nodes that truly need it, and do those last after the non-takeover path has been proven.

## Power On One Replacement At A Time

During the maintenance window, power on only the current replacement VM:

```bash
govc vm.power -on '<vm-path-or-name>'
govc vm.ip -wait=5m '<vm-path-or-name>'
```

Then validate the host before running the RKE2 join step:

```bash
ssh operator@192.0.2.24 \
  'hostname; . /etc/os-release && echo "$PRETTY_NAME"; uname -r; timedatectl status --no-pager; ip -brief addr show; ip route'
```

Check that the VM booted with the expected hostname, IP, OS version, time sync, route, and access policy. If the VM has the wrong identity or reruns destructive initialization unexpectedly, power it off and stop before touching the cluster.

## Warm The Right Image Cache

Image pre-pull can reduce maintenance-window variance, especially when large application images would otherwise cold-pull after the node joins. The important detail is where the image is pulled.

For RKE2, pull into the containerd store kubelet will actually use:

```bash
sudo /var/lib/rancher/rke2/bin/ctr \
  --address /run/k3s/containerd/containerd.sock \
  -n k8s.io images pull registry.example.com/platform/app:1.2.3
```

Validate the cache from the same store:

```bash
sudo /var/lib/rancher/rke2/bin/ctr \
  --address /run/k3s/containerd/containerd.sock \
  -n k8s.io images ls | grep 'registry.example.com/platform/app'
```

Do not confuse Docker, a separate containerd root, or a template-build cache with the RKE2 runtime cache. Also avoid baking short-lived join tokens or registry secrets into images, Terraform state, or durable logs.

If tags are mutable, refresh or verify them shortly before the window. Digest-pinned pulls are safer when the deployment process supports them.

## Worker Drain Shape

When adding replacement worker capacity, avoid moving the same workload repeatedly across old nodes that will be drained later.

A useful worker pattern is:

```text
1. Join one new replacement worker.
2. Confirm CNI, CSI, ingress, and representative workload scheduling.
3. Cordon old workers that should not receive newly evicted pods.
4. Drain one old worker only after reviewing PDB, RWO volume, and capacity risk.
5. Validate workloads and volume attachments.
6. Delete or decommission the old worker.
7. Repeat one worker at a time.
```

Do not cordon the new replacement worker if it is supposed to absorb workloads. If new capacity is insufficient, stop and uncordon old workers rather than forcing drains into a bad placement state.

## Validation Gates

For every replacement, capture a small before/after set:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
kubectl get pvc -A
kubectl get volumeattachments
kubectl -n kube-system get pods -o wide
kubectl get plans.upgrade.cattle.io -A
```

For server and etcd nodes, add etcd health and membership checks after every add or removal:

```bash
kubectl -n kube-system exec <etcd-pod> -- etcdctl \
  --cacert=/var/lib/rancher/rke2/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/rke2/server/tls/etcd/server-client.crt \
  --key=/var/lib/rancher/rke2/server/tls/etcd/server-client.key \
  --endpoints=https://127.0.0.1:2379 endpoint health --cluster
```

The per-node checklist should include node readiness, labels, taints, RKE2 service health, CNI pod health on the node, CSI node pod health, PVC mounts, VolumeAttachments, ingress behavior, and Rancher cluster visibility.

## Stop And Roll Back

Stop if any of these appear:

- etcd health or membership is ambiguous.
- the replacement node does not become `Ready` within the agreed timeout.
- CSI node plugin or volume attachment behavior is unhealthy.
- critical pods remain `Pending`, `CrashLoopBackOff`, or `ContainerCreating` beyond the agreed timeout.
- Rancher marks the cluster disconnected and it does not recover quickly.
- ingress or load-balancer behavior breaks for representative services.
- duplicate node names, wrong node IPs, or stale provider IDs appear.
- Terraform or vCenter shows an unexpected change to active old VMs.

Rollback is easiest when the old VM was only cordoned or powered off. If the old node still exists and is intact, uncordon or power it back on and let it return to `Ready`. If the replacement joined and failed post-join validation, cordon, drain, delete the replacement if safe, and keep the old node in service.

For etcd failures, stop replacement work immediately. Try to recover quorum by bringing a known-good old member back before considering restore from the latest off-node snapshot.

## Operating Rule

Fast node replacement is not fast because operators skip checks. It is fast because VM cloning, baseline configuration, inventory collection, and optional image warming happen before the window.

The maintenance window should only do the work that must happen against the live cluster: power on one prepared VM, validate host identity, join it at the intended version and role, prove cluster health, decommission one old node, and decide whether to continue.
