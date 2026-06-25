+++
title = 'RKE2 kube-proxy CrashLoopBackOff After Upgrade Due To UFW'
date = 2026-02-03T00:00:00-06:00
draft = false
description = 'Field note for diagnosing kube-proxy CrashLoopBackOff after an RKE2/Rancher upgrade, separating probe semantics from dataplane failures, and identifying UFW interference with kube-proxy iptables programming.'
tags = ['rke2', 'kubernetes', 'kube-proxy', 'ufw', 'iptables', 'troubleshooting', 'upgrade']
categories = ['field-notes']
+++

After an RKE2/Rancher upgrade, several `kube-proxy` pods entered `CrashLoopBackOff`. The initial event stream pointed at liveness probe failures:

```text
Warning  Unhealthy  kubelet  Liveness probe failed: HTTP probe failed with statuscode: 503
Warning  BackOff    kubelet  Back-off restarting failed container kube-proxy
```

At first glance, this looked like a Kubernetes 1.31 kube-proxy probe behavior change or an RKE2 manifest mismatch. The real cause was more operational: **UFW was active on a subset of Kubernetes nodes and was interfering with kube-proxy's iptables dataplane programming**.

The important lesson: kube-proxy was not crashing because the binary was broken. Kubelet was killing it because the health endpoint reported an unhealthy dataplane, and the unhealthy dataplane was caused by host firewall drift.

## Symptom

The cluster showed mixed kube-proxy status after upgrade:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system get pods -o wide | grep kube-proxy
```

Example pattern:

```text
kube-proxy-fra-2-etcd-1-rke2   0/1   CrashLoopBackOff
kube-proxy-fra-2-etcd-2-rke2   0/1   CrashLoopBackOff
kube-proxy-fra-2-etcd-3-rke2   1/1   Running
kube-proxy-fra-2-wrkr-2-rke2   0/1   CrashLoopBackOff
kube-proxy-fra-2-wrkr-4-rke2   0/1   CrashLoopBackOff
```

That mixed state matters. If every kube-proxy pod fails, suspect a cluster-wide configuration issue. If only some nodes fail, suspect node-specific drift: host firewall state, kernel modules, sysctls, iptables backend, conntrack pressure, or node image differences.

## First Principle: Use The Node-Local Control Plane

When cluster networking is suspect, avoid testing through paths that depend on cluster networking. On an RKE2 server node, use the local kubeconfig and local API endpoint path.

```bash
sudo ss -lntp | egrep ':6443|:2379|:9345' || true

sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  get --raw='/readyz?verbose'
```

Healthy output should include checks like:

```text
[+]ping ok
[+]etcd ok
[+]etcd-readiness ok
[+]informer-sync ok
readyz check passed
```

This separates API server and etcd health from service routing, DNS, kube-proxy, CNI, or load balancer issues.

## Check kube-proxy Health From The Node

kube-proxy health endpoints are commonly bound to localhost on the node, often `127.0.0.1:10256`. Testing them remotely may fail even when kube-proxy is healthy.

On the affected node:

```bash
sudo ss -lntp | egrep '10256|kube-proxy' || true

curl -sS -o /dev/null -w 'healthz=%{http_code}\n' \
  http://127.0.0.1:10256/healthz || echo 'healthz=connect-failed'

curl -sS -o /dev/null -w 'livez=%{http_code}\n' \
  http://127.0.0.1:10256/livez || echo 'livez=connect-failed'
```

Interpretation:

| Result | Meaning |
|---|---|
| `healthz=503`, `livez=200` | Likely Kubernetes 1.31 health endpoint semantics or liveness probe mismatch |
| both `connect-failed` | kube-proxy is not binding the health port or is exiting early |
| both `200` on one node but failures elsewhere | node-specific issue; test a failing node directly |

## Kubernetes 1.31 Probe Semantics Check

Kubernetes 1.31 added `/livez` to kube-proxy to preserve liveness-style behavior, while `/healthz` may report dataplane readiness and can return non-200 when kube-proxy believes the dataplane is stale or unhealthy.

Check the probe paths:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system get ds kube-proxy \
  -o jsonpath='{.spec.template.spec.containers[0].livenessProbe.httpGet.path}{"\n"}'

sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system get ds kube-proxy \
  -o jsonpath='{.spec.template.spec.containers[0].startupProbe.httpGet.path}{"\n"}'
```

A tactical mitigation, if `/healthz` is flapping while `/livez` is stable:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system patch ds kube-proxy --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/livez"},
    {"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/httpGet/path","value":"/livez"}
  ]'
```

In this incident, probe semantics were worth checking, but they were not the durable root cause.

## Pull kube-proxy Logs

The logs showed kube-proxy starting cleanly:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system logs kube-proxy-<node-name> -c kube-proxy --tail=200

sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system logs kube-proxy-<node-name> -c kube-proxy --previous --tail=200
```

Representative lines:

```text
Successfully retrieved node IP(s)
kube-proxy running in dual-stack mode
Using iptables Proxier
Starting service config controller
Starting endpoint slice config controller
Starting node config controller
Caches are synced
```

That is a clue. If kube-proxy logs look normal and the container still restarts, kubelet may be killing it because the health check fails after startup. In that case, focus on why kube-proxy reports the dataplane unhealthy.

## Check Node Networking Requirements

On a failing node:

```bash
# iptables backend
iptables --version || true
update-alternatives --display iptables 2>/dev/null | sed -n '1,120p' || true

# required sysctls
sysctl net.ipv4.ip_forward
sysctl net.bridge.bridge-nf-call-iptables 2>/dev/null || true
sysctl net.bridge.bridge-nf-call-ip6tables 2>/dev/null || true

# common modules
lsmod | egrep 'br_netfilter|nf_conntrack|ip_tables|iptable_nat|x_tables|ip_vs' || true

# conntrack pressure
sysctl net.netfilter.nf_conntrack_count 2>/dev/null || true
sysctl net.netfilter.nf_conntrack_max 2>/dev/null || true
```

In this incident, the expected modules and sysctls were present, and conntrack pressure was low:

```text
iptables v1.8.10 (nf_tables)
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.netfilter.nf_conntrack_count = 817
net.netfilter.nf_conntrack_max = 131072
```

That reduced suspicion on kernel module, sysctl, and conntrack exhaustion problems.

## The Smoking Gun: UFW Was Active

Check host firewall managers:

```bash
sudo systemctl is-active firewalld 2>/dev/null || true
sudo systemctl is-active ufw 2>/dev/null || true
```

The failing node returned:

```text
inactive
active
```

That second line was the key: **UFW was active on the Kubernetes node**.

kube-proxy dynamically programs iptables rules for Services and NodePorts. UFW also manages iptables policy and chains. When both operate on the same node, UFW can interfere with kube-proxy's view of the dataplane through default forwarding policy, rule ordering, chain changes, or reload behavior.

The result can look like this:

```text
UFW changes host firewall policy
kube-proxy cannot reliably maintain service rules
kube-proxy reports /healthz as unhealthy
kubelet kills kube-proxy due to failed liveness probe
kube-proxy enters CrashLoopBackOff
```

## Confirm The Hypothesis

On one failing node only:

```bash
sudo ufw status verbose || true
sudo systemctl stop ufw
sudo systemctl disable ufw
sudo ufw disable || true
```

Then restart the node's RKE2 service or delete the kube-proxy pod.

For an RKE2 server node:

```bash
sudo systemctl restart rke2-server
```

For an RKE2 agent node:

```bash
sudo systemctl restart rke2-agent
```

Or delete only the kube-proxy pod from a server node with local kubeconfig:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system delete pod kube-proxy-<node-name>
```

Validate:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system get pod kube-proxy-<node-name>

curl -sS -o /dev/null -w 'healthz=%{http_code}\n' \
  http://127.0.0.1:10256/healthz || echo 'healthz=connect-failed'
```

In this case, kube-proxy immediately returned to `1/1 Running` with `healthz=200` after UFW was disabled. That confirmed the root cause.

## Recovery Rollout

Disable UFW across all Kubernetes nodes, one node class at a time.

Recommended order for an HA RKE2 environment:

1. etcd nodes, one at a time
2. control-plane/server nodes, one at a time
3. monitor/infra nodes, one at a time
4. worker nodes, failing nodes first

On each node:

```bash
sudo ufw status verbose || true
sudo systemctl stop ufw
sudo systemctl disable ufw
sudo ufw disable || true
```

Then restart the appropriate service:

```bash
# RKE2 server node
sudo systemctl restart rke2-server

# RKE2 agent node
sudo systemctl restart rke2-agent
```

Validate after each node:

```bash
curl -sS -o /dev/null -w 'healthz=%{http_code}\n' \
  http://127.0.0.1:10256/healthz || echo 'healthz=connect-failed'
```

Cluster-wide validation:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  -n kube-system get pods -o wide | grep kube-proxy
```

All kube-proxy pods should settle at `1/1 Running` without climbing restarts.

## RBAC Red Herring

One previous kube-proxy log showed a transient RBAC denial:

```text
Failed to retrieve node info: nodes "<node>" is forbidden:
User "system:kube-proxy" cannot get resource "nodes"
```

This looked concerning, but the effective permission check later passed:

```bash
sudo /var/lib/rancher/rke2/bin/kubectl \
  --kubeconfig /etc/rancher/rke2/rke2.yaml \
  auth can-i get nodes --as=system:kube-proxy
```

Expected output:

```text
yes
```

The cluster had both relevant bindings:

```text
system:kube-proxy   roleRef=system:kube-proxy
system:node-proxier roleRef=system:node-proxier
```

That made the RBAC denial likely transient during upgrade churn, not the persistent cause of kube-proxy CrashLoopBackOff.

## Durable Prevention

Add an explicit control to the node baseline: Kubernetes nodes should not run UFW unless the firewall policy is intentionally designed and tested with the CNI and kube-proxy mode.

For most RKE2 nodes, the practical baseline is:

```bash
sudo systemctl stop ufw || true
sudo systemctl disable ufw || true
sudo ufw disable || true
```

Optional if your baseline allows package removal:

```bash
sudo apt-get purge -y ufw
```

Add this to the image build, cloud-init, Ansible role, or node bootstrap script. Do not rely on manual cleanup after an incident.

## Pre-Upgrade Check

Before future RKE2 upgrades, run a lightweight node drift check:

```bash
for node in $(kubectl get nodes -o name | cut -d/ -f2); do
  echo "=== $node ==="
  ssh "$node" 'systemctl is-active ufw 2>/dev/null || true; systemctl is-active firewalld 2>/dev/null || true'
done
```

Flag any node where `ufw` or `firewalld` is active and validate whether that is intentional.

## Lessons Learned

- Mixed kube-proxy failures usually point at node drift, not a universal cluster defect.
- kube-proxy logs can look normal when kubelet is killing the container due to health checks.
- Test kube-proxy health from the node, not through a path that depends on cluster networking.
- Kubernetes 1.31 `/healthz` vs `/livez` behavior is worth checking, but do not stop there.
- Host firewall managers like UFW can masquerade as upgrade regressions.
- Recovery is not complete until the node baseline prevents UFW from returning on reboot or rebuild.

## References

- [RKE2 Documentation](https://docs.rke2.io/)
- [Kubernetes kube-proxy](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-proxy/)
- [Kubernetes Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/)
- [Kubernetes System Logs](https://kubernetes.io/docs/concepts/cluster-administration/system-logs/)
