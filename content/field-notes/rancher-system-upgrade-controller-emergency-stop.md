+++
title = 'Emergency Stop For Rancher System Upgrade Controller'
date = 2026-06-24T00:00:00-05:00
draft = false
description = 'Field note for stopping a Rancher system-upgrade-controller agent Plan that is repeatedly cordoning workers while GitOps keeps restoring the Plan.'
tags = ['rancher', 'rke2', 'kubernetes', 'gitops', 'upgrades', 'operations']
categories = ['field-notes']
+++

Use this when a Rancher `system-upgrade-controller` worker Plan is actively cordoning or draining nodes and a normal live-object patch does not stick because GitOps restores it.

## Confirm The Controller Is Active

```bash
kubectl get plan -n system-upgrade
kubectl get jobs,pods -n system-upgrade -o wide
kubectl get events -n system-upgrade --sort-by=.lastTimestamp
```

Look for jobs like:

```text
apply-agent-plan-on-worker-1-...
```

Check worker schedulability:

```bash
kubectl get nodes
kubectl describe node worker-1 | grep -E 'Unschedulable|Taints|Ready'
```

## Check GitOps Ownership

Before assuming a patch will hold, check ownership annotations and Argo/ApplicationSet resources:

```bash
kubectl get plan agent-plan -n system-upgrade -o yaml
kubectl get application -n argocd system-upgrade -o yaml
kubectl get applicationset -n argocd system-upgrade -o yaml
```

If Argo CD or an ApplicationSet owns the Plan, live patches may be reverted by self-heal.

## First Stop: Make The Plan Match No Nodes

Patch the Plan with an intentionally absent selector:

```bash
kubectl patch plan agent-plan -n system-upgrade --type=merge -p '
{
  "spec": {
    "nodeSelector": {
      "matchExpressions": [
        {
          "key": "node-role.kubernetes.io/control-plane",
          "operator": "DoesNotExist"
        },
        {
          "key": "system-upgrade.example.com/agent-plan-paused",
          "operator": "In",
          "values": ["false"]
        }
      ]
    }
  }
}'
```

Delete active jobs and uncordon affected workers:

```bash
kubectl delete job -n system-upgrade \
  -l upgrade.cattle.io/plan=agent-plan \
  --ignore-not-found=true

kubectl uncordon worker-1
```

## If GitOps Reverts The Patch

If the Plan is restored and jobs come back, pause GitOps at the source if possible. If that is not fast enough during an incident, stop execution by scaling down the controller:

```bash
kubectl scale deployment system-upgrade-controller \
  -n system-upgrade \
  --replicas=0
```

Then delete active jobs again and uncordon workers:

```bash
kubectl delete job -n system-upgrade \
  -l upgrade.cattle.io/plan=agent-plan \
  --ignore-not-found=true

kubectl uncordon worker-1
```

## Verify The Stop

```bash
sleep 20
kubectl get deploy -n system-upgrade system-upgrade-controller
kubectl get jobs,pods -n system-upgrade -l upgrade.cattle.io/plan=agent-plan -o wide
kubectl get nodes
```

Expected emergency state:

```text
system-upgrade-controller replicas: 0
agent-plan jobs: none
workers: Ready and schedulable unless independently unhealthy
```

## Find Why It Ran

The controller may have started weeks ago and still be acting because workers never reached the desired version.

Check desired and actual versions:

```bash
kubectl get plan agent-plan -n system-upgrade -o yaml
kubectl get nodes -o wide
```

Pattern:

```text
control-plane nodes: desired version reached
worker nodes: older version remains
agent-plan: still selects workers
```

That means the controller is not randomly starting. It is continuously reconciling unfinished desired state.

## Durable Fix

The emergency stop is not the durable fix.

After management access is restored:

- update the Git source that renders the Plan.
- add a real pause flag or disable automated sync for the specific upgrade app.
- restore controller replicas only when worker capacity is healthy.
- make sure at least one worker can be drained without losing management workloads.
- remove emergency live patches after Git reflects the desired state.

## Operating Rule

If GitOps owns the Plan, live Kubernetes patches are temporary.

During an outage, stop execution first. Then make the durable change in Git before turning the controller back on.
