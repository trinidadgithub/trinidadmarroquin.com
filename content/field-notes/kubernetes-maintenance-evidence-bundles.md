+++
title = 'Kubernetes Maintenance Evidence Bundles Need A Redaction Plan'
date = 2026-07-22T00:00:00-05:00
draft = false
description = 'A field note on retaining Kubernetes maintenance evidence without leaking sensitive cluster names, IPs, credentials, workload names, or internal topology.'
tags = ['kubernetes', 'rke2', 'operations', 'runbooks', 'security']
categories = ['field-notes']
+++

Good maintenance windows produce evidence. Bad evidence bundles become a new secret store.

During RKE2 reboot and upgrade work, the most useful artifacts were not complicated: preflight JSON, per-batch reboot logs, final cluster state captures, and error files. They proved which context was used, which nodes were touched, whether boot IDs changed, whether workers were drained, whether PodDisruptionBudgets blocked eviction, and whether the cluster returned to the expected baseline.

That same evidence can expose internal hostnames, IP addresses, SSH usernames, kubeconfig paths, workload names, Vault paths, webhook URLs, and temporary access helpers. Treat maintenance output as operational evidence and sensitive data at the same time.

## Keep The Bundle Shape Boring

Use predictable file names that encode the maintenance phase without exposing unnecessary detail:

```text
cluster-a-preflight.json
cluster-a-batch-1-control-plane.log
cluster-a-batch-2-etcd.log
cluster-a-workers.log
cluster-a-final-state.json
cluster-a-final-errors.err
```

The useful pattern is phase-based:

```text
preflight
batch execution
post-batch health
final validation
errors and exceptions
```

That lets another operator reconstruct what happened without reading a chat transcript or guessing which terminal command mattered.

## Capture Operator Intent

Every execution log should start with the maintenance inputs that change behavior:

```text
KUBE_CONTEXT=cluster-a-prod
DRAIN_WORKERS=true
READY_TIMEOUT=30m
REBOOT_SETTLE_SECONDS=90
POLL_SECONDS=15
WAIT_FOR_BOOT_ID=true
VERIFY_HOST_REBOOT=true
```

These values explain the run. If a worker was drained, the log should say so. If a control-plane node was cordoned but not drained, the log should say so. If the run required host boot-ID verification, the log should show that requirement before any node is touched.

## Capture Before And After State

For node maintenance, retain enough state to prove the sequence:

```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o wide
kubectl get pdb -A
kubectl get events -A --sort-by=.lastTimestamp
```

For RKE2 and Longhorn, add role-specific checks:

```bash
kubectl -n kube-system get pods -o wide
kubectl -n longhorn-system get volumes.longhorn.io,replicas.longhorn.io,nodes.longhorn.io -o wide
kubectl -n longhorn-system get pdb -o wide
```

The important part is not the exact command list. The important part is that the same evidence exists before the first node and after the last node.

## Drain Output Is Evidence

Do not discard drain output. It often reveals the real maintenance constraint.

Examples of useful signals:

- which pods were evicted successfully.
- which DaemonSet pods were intentionally ignored.
- whether a PDB blocked eviction.
- whether a storage controller waited and then allowed eviction.
- whether the drain completed before reboot.

For Longhorn, an instance-manager PDB can temporarily block eviction. That is useful information, not just noisy output. It tells the operator that storage components were in the disruption path and that future worker maintenance should account for Longhorn placement before assuming a normal drain will be quick.

## Verify Reboot With Two Views

SSH availability only proves a host is reachable. It does not prove the host rebooted.

Capture the pre-reboot and post-reboot boot IDs:

```bash
cat /proc/sys/kernel/random/boot_id
kubectl get node worker-1 -o jsonpath='{.status.nodeInfo.bootID}{"\n"}'
```

The evidence bundle should show:

```text
pre host boot ID
pre Kubernetes boot ID
post host boot ID changed
post Kubernetes boot ID changed or reconciled
node Ready after reboot
```

This prevents a false success where SSH reconnects but the host never restarted, or Kubernetes still shows stale node information while the kubelet is catching up.

## Redact Before Sharing

Raw maintenance artifacts are usually safe to keep in the controlled operations workspace. They are not safe to paste into tickets, public notes, blog posts, or vendor cases without review.

Redact or generalize:

- real cluster names.
- internal DNS names.
- RFC 1918 IP addresses.
- SSH usernames and key paths.
- kubeconfig paths.
- Vault paths and auth mount names.
- webhook URLs.
- customer workload names.
- temporary privileged helper names.
- organization-specific labels and namespaces.

Prefer examples like:

```text
cluster-a-prod
cp-1
etcd-1
worker-1
storage-1
192.0.2.10
vault.example.com
```

Do not redact away the operational meaning. Keep the role, phase, and outcome.

## Close The Loop

An evidence bundle should answer five questions:

1. What context and cluster did the operator intend to touch?
2. What was the health baseline before maintenance?
3. Which nodes were touched, in what order, and with what drain behavior?
4. What proved each host actually rebooted?
5. What final checks proved the cluster returned to baseline?

If the bundle answers those questions, it is useful during review. If it also has a redaction plan, it is safe to reuse for procedures, postmortems, and public writing.

The runbook is the plan. The evidence bundle is how you prove the plan actually happened.
