+++
title = 'GitOps-Owned vSphere CSI Maintenance Pauses'
date = 2026-08-05T00:00:00-05:00
draft = false
description = 'Field note for pausing vSphere CSI controllers during storage incidents when Argo CD, ApplicationSets, and self-heal keep restoring controller replicas.'
tags = ['kubernetes', 'vsphere', 'csi', 'argocd', 'gitops', 'storage', 'operations']
categories = ['field-notes']
+++

During a vSphere CNS backlog, stopping the source of new CSI work can be safer than continuing to submit attach, detach, resize, and update requests into a stuck backend queue. The trap is that GitOps may immediately undo the pause.

Scaling a vSphere CSI controller Deployment to `0` is not a durable pause if Argo CD, an ApplicationSet, or a higher root Application owns it. The visible command succeeds, then self-heal restores the replicas and new controller pods start submitting tasks again.

## Confirm Ownership First

Before scaling anything, inspect ownership and sync policy:

```bash
kubectl -n vmware-system-csi get deploy vsphere-csi-controller -o yaml \
  | yq '.metadata.labels, .metadata.annotations'

kubectl get applications.argoproj.io,applicationsets.argoproj.io -A \
  | grep -i 'vsphere\|csi'
```

Then inspect the owning Application and ApplicationSet:

```bash
kubectl -n argocd get application <app-name> -o yaml \
  | yq '.spec.syncPolicy'

kubectl -n argocd get applicationset <applicationset-name> -o yaml \
  | yq '.spec.syncPolicy, .spec.template.spec.syncPolicy'
```

Look for:

```text
automated.prune=true
automated.selfHeal=true
applicationsSync: create-update
```

Those settings mean live edits may not hold.

## Prefer A Narrow Pause

Try the least broad pause first:

```bash
kubectl -n argocd patch application <cluster-vsphere-csi-app> --type=json \
  -p='[{"op":"remove","path":"/spec/syncPolicy/automated"}]'

kubectl -n vmware-system-csi scale deploy/vsphere-csi-controller --replicas=0
```

If an ApplicationSet recreates the Application policy, pause the service-specific ApplicationSet rather than the entire GitOps platform when possible. If a parent Application self-heals that ApplicationSet, keep walking up the ownership chain until you understand which controller is restoring the change.

Do not disable broad GitOps controllers unless the incident requires that blast radius and the rollback is explicit.

## Scheduling Block When Self-Heal Will Not Stop

When the GitOps chain cannot be paused cleanly during an active incident, a temporary scheduling block can stop CSI controller pods from running without deleting the desired state.

For a controller that only schedules on control-plane nodes, add a dedicated maintenance taint to those eligible nodes:

```bash
kubectl taint nodes cp-1 cp-2 cp-3 \
  storage-maintenance/freeze-csi=true:NoSchedule

kubectl -n vmware-system-csi delete pod -l app=vsphere-csi-controller
```

Then verify the pause is real:

```bash
kubectl -n vmware-system-csi get pods -l app=vsphere-csi-controller -o wide
kubectl -n vmware-system-csi get deploy vsphere-csi-controller
```

The desired replica count may still be `3`, but the important operational signal is that replacement controller pods are `Pending` and have no assigned node. Pending pods are not submitting new CNS work.

Do not taint worker nodes unless the CSI controller actually schedules there. A `NoSchedule` taint does not evict existing non-CSI pods, but it can still affect new scheduling, so keep the scope tight and documented.

## Verify The Backend Queue Stops Growing

After the pause, watch vCenter queued/running tasks:

```bash
govc tasks -json -s queued -s running -n=300 \
  | jq -r '.Tasks[]? | [
      .QueueTime,
      .State,
      .DescriptionId,
      (.EntityName // ""),
      .Key
    ] | @tsv'
```

Compare the latest task timestamps before and after the pause. The goal is not that the old backlog disappears immediately. The goal is that new CSI-generated work stops appearing while vCenter drains or times out the existing tasks.

## Roll Back In Phases

Do not unpause every cluster at once. If multiple clusters were paused to reduce CNS load, restore the lower-risk or actively needed cluster first and keep the problematic cluster paused until its VM-level locks are clear.

Rollback the scheduling block by removing the same taint key. The trailing `-` is the `kubectl taint` syntax for removal:

```bash
kubectl taint nodes cp-1 cp-2 cp-3 \
  storage-maintenance/freeze-csi-
```

Then verify:

```bash
kubectl -n vmware-system-csi get pods -l app=vsphere-csi-controller -o wide
kubectl get volumeattachments -o wide
govc tasks -json -s queued -s running -n=300
```

Restore GitOps automation only after confirming the CSI controller is healthy and vCenter is not immediately accumulating new attach/detach work.

## Operating Rule

A CSI pause is not successful when `kubectl scale` returns success. It is successful when no controller pod is running and the vCenter CNS task queue stops receiving new work from that cluster.

In GitOps-owned environments, verify the effective runtime state, not just the live object you patched.
