+++
title = 'When A Latent Rancher Worker Upgrade Becomes An Outage'
date = 2026-06-24T00:00:00-05:00
draft = false
description = 'A Rancher and RKE2 incident pattern where a continuously reconciled system-upgrade-controller Plan stayed pending until worker capacity collapsed, then cordoned the last healthy worker.'
tags = ['rancher', 'rke2', 'kubernetes', 'gitops', 'upgrades', 'operations']
categories = ['notes']
+++

Not every outage starts with a new deployment.

Sometimes the trigger is old desired state that never finished converging. A controller keeps watching. A GitOps reconciler keeps restoring. The cluster looks stable until capacity drops, and then the old desired state becomes active at the worst possible time.

That is the failure pattern I want to remember from this Rancher/RKE2 investigation.

## The Shape Of The Problem

The cluster had a Rancher-managed RKE2 system-upgrade workflow with separate plans:

```text
server-plan -> control-plane / etcd nodes
agent-plan  -> worker nodes
```

The server side had already completed. Control-plane nodes were on the desired RKE2 version.

The worker side had not completed. The `agent-plan` still targeted non-control-plane nodes and expected worker nodes to reach the newer RKE2 version.

That meant the upgrade was not historical. It was still live desired state.

## Why It Happened Later

The confusing part was timing. The plan had been synced weeks earlier, so why did it cause trouble later?

Because a Kubernetes `Plan` managed by `system-upgrade-controller` is declarative. It does not run once and disappear. It keeps reconciling until selected nodes satisfy the desired version.

The effective logic was:

```text
worker node selected by agent-plan
worker version != desired version
controller creates or retries upgrade job
job cordons and drains selected worker
```

That was latent risk while there was enough worker capacity.

It became an outage when worker capacity collapsed:

- one worker had been unreachable for a long time.
- another worker became `NotReady`.
- the upgrade job cordoned and drained the remaining healthy worker.

At that point, management workloads that needed schedulable workers lost placement. Rancher and Argo CD HTTP access disappeared at the same time.

## The First Fix Was Not Durable

The first mitigation was to patch the `agent-plan` so it matched no worker nodes. That stopped the immediate job briefly.

But the Plan was GitOps-managed. Argo CD self-heal restored the desired Plan, removed the manual pause, and the controller created another job.

That is the key lesson:

```text
Patching the live object is not durable if GitOps owns the object.
```

If GitOps self-heal is enabled, the durable fix must happen in Git or in the GitOps control path. Otherwise the cluster will undo the emergency patch.

## Emergency Stop Sequence

The safer stop path was layered:

```text
pause or disable GitOps reconciliation for the system-upgrade app
patch the Plan so it matches no nodes
delete active upgrade jobs
uncordon affected workers
if reconciliation still wins, scale down system-upgrade-controller
verify no jobs return
```

The last step was necessary because the ApplicationSet/GitOps path continued to restore the Plan. Scaling the controller to zero cut off execution even while the declarative object still existed.

That is not the long-term fix. It is an emergency brake.

## Commands Worth Keeping

Inspect Plans and jobs:

```bash
kubectl get plan -n system-upgrade
kubectl get jobs,pods -n system-upgrade -o wide
kubectl get events -n system-upgrade --sort-by=.lastTimestamp
```

Check whether GitOps owns the Plan:

```bash
kubectl get plan agent-plan -n system-upgrade -o yaml
kubectl get application -n argocd system-upgrade -o yaml
kubectl get applicationset -n argocd system-upgrade -o yaml
```

Pause execution when the controller is actively disrupting workers:

```bash
kubectl scale deployment system-upgrade-controller \
  -n system-upgrade \
  --replicas=0

kubectl delete job -n system-upgrade \
  -l upgrade.cattle.io/plan=agent-plan \
  --ignore-not-found=true

kubectl uncordon worker-1
```

Verify it stays stopped:

```bash
kubectl get deploy -n system-upgrade system-upgrade-controller
kubectl get jobs,pods -n system-upgrade -l upgrade.cattle.io/plan=agent-plan -o wide
kubectl get nodes
```

## Cordoned Is Not NotReady

During the investigation, one worker looked suspicious because it had been unusable for a long time. It was important to separate two states:

```text
cordoned / SchedulingDisabled -> spec.unschedulable=true
NotReady / unreachable       -> kubelet stopped reporting status or node is unreachable
```

A node can be NotReady without being cordoned. Uncordoning does nothing for a node whose kubelet is not reporting.

Useful check:

```bash
kubectl get node worker-3 -o jsonpath='{.spec.unschedulable}{"\n"}'
kubectl describe node worker-3
```

## What I Would Add To The Runbook

Before allowing an automated worker upgrade Plan to run:

- require at least N healthy schedulable workers after one worker is cordoned.
- block or pause upgrades when any worker has been NotReady longer than a threshold.
- alert on `agent-plan` jobs retrying for days or weeks.
- document whether the Plan is GitOps-owned and where the durable pause lives.
- verify Rancher and Argo CD workloads have enough placement redundancy.
- treat ApplicationSet self-heal as part of the control plane, not background noise.

## The Practical Lesson

The system-upgrade controller did what it was told. Argo CD did what it was told. Kubernetes did what it was told.

The outage came from the gap between desired state and operational readiness:

```text
workers still needed upgrade
controller kept reconciling
GitOps kept restoring the Plan
worker capacity dropped
the remaining worker was cordoned and drained
management workloads lost placement
```

That is why upgrade automation needs a readiness gate, not just a desired version.

Related Field Note:

- [Emergency Stop For Rancher System Upgrade Controller](/field-notes/rancher-system-upgrade-controller-emergency-stop/)
