+++
title = 'RKE2 Calico Readiness Failures From Stale Port Owners'
date = 2026-08-03T00:00:00-05:00
draft = false
description = 'Field note for diagnosing Calico and Typha readiness failures after RKE2 changes when old node-local processes still own health or service ports.'
tags = ['rke2', 'kubernetes', 'calico', 'rancher', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

After an RKE2 upgrade or node maintenance event, Calico can fail readiness even when the node itself is `Ready`.

One failure pattern is node-local and easy to miss: old Calico or Typha processes survive from a previous RKE2 runtime path and keep owning the ports that the current pods need. Kubernetes shows the new pods as unhealthy, but the real conflict is on the host.

This is not a YAML problem first. It is a process ownership problem.

## Symptoms

Start with the cluster view:

```bash
kubectl -n calico-system get pods -o wide
kubectl get nodes -o wide
```

Typical signals:

- one or more `calico-node` pods are `Running` but not ready.
- one or more `calico-typha` pods are `CrashLoopBackOff` or repeatedly failing readiness.
- the affected Kubernetes node is still `Ready`.
- the node may have been left cordoned by a previous upgrade or maintenance action.
- other nodes may be healthy, which makes this look node-specific rather than cluster-wide.

Do not uncordon a node just because the upgrade Plan says complete. Check the CNI pods on that node first.

## Check Host Port Owners

On the affected host, check who owns the relevant ports:

```bash
sudo ss -lntup | grep -E '9099|5473|179|4789' || true
sudo ps -eo pid,ppid,cmd | grep -E 'calico|typha|containerd-shim' | grep -v grep || true
```

Useful ports to recognize:

```text
9099  Calico Felix health endpoint
5473  Typha
179   BGP, if used
4789  VXLAN
```

Then compare the process path with the current RKE2 runtime path:

```bash
readlink -f /var/lib/rancher/rke2/bin
sudo ls -ld /var/lib/rancher/rke2/data/*/bin 2>/dev/null
```

Problem shape:

```text
current RKE2 bin path: /var/lib/rancher/rke2/data/v1.32.x-rke2r1-.../bin
port owner process:    /var/lib/rancher/rke2/data/v1.31.x-rke2r1-.../bin/containerd-shim-runc-v2
```

That tells you an old runtime process may still be alive while the current Kubernetes pod is trying to start a replacement.

## Ask The Runtime First

Before manually killing host processes, ask the current runtime whether it still owns them:

```bash
sudo /var/lib/rancher/rke2/bin/crictl \
  --runtime-endpoint unix:///run/k3s/containerd/containerd.sock ps -a

sudo /var/lib/rancher/rke2/bin/ctr \
  --address /run/k3s/containerd/containerd.sock \
  --namespace k8s.io tasks ls
```

If the process is invisible to the current runtime but still owns a Calico or Typha port, it is likely orphaned. At that point, a controlled node reboot is usually safer than deleting old RKE2 data directories or killing process trees by hand.

## Reboot One Node At A Time

For a worker, the safe pattern depends on workload risk.

If you can drain:

```bash
kubectl cordon worker-1
kubectl drain worker-1 --ignore-daemonsets --delete-emptydir-data
ssh operator@worker-1.example.com 'sudo reboot'
kubectl wait node/worker-1 --for=condition=Ready --timeout=30m
kubectl uncordon worker-1
```

If draining would cause unnecessary disruption and the platform owner accepts a no-drain reboot, still cordon first and verify after:

```bash
kubectl cordon worker-1
ssh operator@worker-1.example.com 'sudo reboot'
kubectl wait node/worker-1 --for=condition=Ready --timeout=30m
kubectl -n calico-system get pods -o wide | grep worker-1
kubectl uncordon worker-1
```

For control-plane nodes, use the existing control-plane maintenance process: one node at a time, cordon/no-drain unless your platform runbook says otherwise, and verify API, etcd, and Calico health before moving to the next node.

## Verify The Reboot Actually Happened

Do not trust SSH reconnect alone. Record the boot ID before and after:

```bash
cat /proc/sys/kernel/random/boot_id
kubectl get node worker-1 -o jsonpath='{.status.nodeInfo.bootID}{"\n"}'
```

The node is not remediated until the boot ID changes and the replacement Calico pods are healthy.

## Post-Reboot Checks

After each node returns:

```bash
kubectl get node worker-1 -o wide
kubectl -n calico-system get pods -o wide | grep worker-1
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o wide
```

On the host, confirm the stale owners are gone:

```bash
sudo ss -lntup | grep -E '9099|5473|179|4789' || true
sudo ps -eo pid,ppid,cmd | grep -E 'calico|typha|containerd-shim' | grep -v grep || true
```

Then uncordon only when the node-local CNI state is healthy:

```bash
kubectl uncordon worker-1
```

## Watch For Stale Pod Objects

Immediately after a reboot, Kubernetes can briefly show old pods as `Unknown` or `ContainerStatusUnknown` while kubelet and controllers reconcile. Do not confuse that transient cleanup with a persistent failure.

Use a short settle window and check whether the replacement pods are actually ready:

```bash
kubectl get pods -A -o wide --field-selector spec.nodeName=worker-1
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o wide
```

If the only remaining non-running pod is an old completed upgrade artifact or a long-standing unrelated issue, document it separately instead of blocking the CNI remediation.

## The Pattern

The useful triage order is:

1. Identify unhealthy Calico/Typha pods by node.
2. Check host port owners for Calico and Typha ports.
3. Compare process paths with the current RKE2 data directory.
4. Ask `crictl` and `ctr` whether the current runtime owns the processes.
5. Reboot one affected node at a time instead of deleting runtime data under live processes.
6. Require boot-ID change, Kubernetes `Ready`, and Calico readiness before uncordoning.
7. Separate stale pod objects from real post-reboot failures.

The key lesson: a CNI readiness failure after RKE2 maintenance may be a host-runtime residue problem. Fix it like node maintenance, not like a manifest typo.
