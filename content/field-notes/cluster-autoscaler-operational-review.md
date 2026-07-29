+++
title = 'Cluster Autoscaler Operational Review'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Operational review checklist for Kubernetes cluster autoscaler behavior, including pending pods, node groups, scale-up blockers, scale-down safety, and capacity risks.'
tags = ['kubernetes', 'cluster-autoscaler', 'autoscaling', 'capacity', 'platform-engineering', 'operations']
categories = ['field-notes']
+++

Cluster autoscaler is capacity automation, not a replacement for capacity ownership.

It can add nodes when pods cannot schedule and remove nodes when capacity is unused, but it only works inside the boundaries the platform team gives it: node groups, quotas, labels, taints, pod requests, disruption budgets, and cloud or virtualization capacity.

This review is for platform teams that need to know whether autoscaling is safe, predictable, and observable.

## Start With The Capacity Contract

Document the autoscaling boundary.

```text
Cluster:
Autoscaler owner:
Node groups:
Minimum nodes:
Maximum nodes:
Instance or VM types:
Critical taints and labels:
Scale-up expected time:
Scale-down policy:
Cloud, vSphere, or provider quota owner:
```

If nobody owns the maximum size, quota, or image supply chain, autoscaler failures will be discovered during incidents.

## Check Pending Pods First

Autoscaler scale-up starts with unschedulable pods.

```bash
kubectl get pods -A --field-selector=status.phase=Pending
kubectl describe pod -n app-namespace pending-pod-name
```

Look for scheduler reasons:

- insufficient CPU.
- insufficient memory.
- node selector mismatch.
- taint not tolerated.
- topology spread constraints.
- persistent volume binding.
- pod affinity or anti-affinity rules.
- max node group size reached.

Not every pending pod is solved by adding nodes. If labels, taints, or storage constraints prevent scheduling, autoscaler may not be able to help.

## Review Autoscaler Logs

The autoscaler usually explains its decision.

```bash
kubectl logs -n kube-system deploy/cluster-autoscaler
```

Search for:

- scale-up decisions.
- node group max size reached.
- pods not triggering scale-up.
- failed cloud provider calls.
- node template mismatch.
- scale-down blocked by pods.
- insufficient quota or capacity.

The useful question is:

```text
Did autoscaler choose not to scale, or did it try and fail?
```

Those are different incidents.

## Node Group Design

Autoscaler works best when node groups map to clear workload needs.

Review each node group:

- purpose.
- min and max size.
- instance or VM shape.
- labels.
- taints.
- zones or failure domains.
- image or template version.
- storage and network assumptions.

Avoid one giant generic node group if workloads have distinct needs. Also avoid too many special node groups that fragment capacity and make scheduling unpredictable.

## Requests Drive Scheduling

Autoscaler responds to scheduler capacity, and scheduler capacity is based on requests.

Review workload requests:

```bash
kubectl top pods -A
kubectl describe node node-name
```

Look for:

- pods with no CPU or memory requests.
- requests much higher than observed usage.
- requests too low for actual usage.
- namespace quotas that block scheduling.
- limit ranges that set surprising defaults.

Bad requests create bad autoscaling. A cluster can add nodes and still have poor reliability if requests do not represent workload needs.

## Scale-Up Blockers

Common scale-up blockers:

- node group is already at maximum size.
- provider quota is exhausted.
- requested instance or VM type is unavailable.
- node image or template is broken.
- bootstrap fails before the node joins.
- new node joins with wrong labels or taints.
- CNI fails and node remains `NotReady`.
- storage or CSI dependencies fail on new nodes.
- pod requires a zone with no scalable node group.

For RKE2 or vSphere-style environments, node template readiness matters as much as the autoscaler configuration. A new node that cannot join the cluster is not capacity.

## Scale-Down Safety

Scale-down can be more dangerous than scale-up.

Review:

- PodDisruptionBudgets.
- local storage usage.
- system and daemonset pods.
- critical workloads with anti-affinity.
- long-running jobs.
- stateful workloads.
- drain behavior.
- minimum node group sizes.

If scale-down evicts the wrong workload at the wrong time, autoscaler becomes a reliability risk.

Use PDBs to express disruption safety, but do not rely on them as the only control. Operators still need to understand which workloads should not be moved casually.

## Observability Panels

Autoscaler dashboards should show:

- pending pods by namespace and reason.
- node count by node group.
- desired versus current node count.
- scale-up events.
- scale-down events.
- autoscaler errors.
- node readiness after scale-up.
- time from pending pod to ready node.
- provider quota or capacity errors.
- unschedulable pod count.

For incident response, pair autoscaler metrics with scheduler events and node readiness. A scale-up event is not successful until the node is ready and the pod schedules.

## Common Failure Modes

### Autoscaler Cannot See The Right Node Group

The pending pod requires labels, taints, or zone placement that no autoscaled group can provide.

### Max Size Is Too Low

Autoscaler behaves correctly but stops at the configured maximum.

### Quota Blocks Provider Capacity

The node group could scale, but cloud or virtualization quota prevents provisioning.

### New Nodes Join Broken

The provider creates the node, but bootstrap, CNI, kubelet, CSI, or certificates fail.

### Scale-Down Fights Operations

Autoscaler removes nodes during maintenance or while teams are debugging noisy workloads. Pause or constrain scale-down during risky windows when needed.

### Requests Are Wrong

Pods either never trigger scale-up when they should, or trigger expensive scale-up because requests are inflated.

## Review Questions

Use these during platform review:

```text
Can every critical workload schedule onto at least one autoscaled node group?
Are min and max sizes documented and owned?
Does the team know how long scale-up normally takes?
Are pending pod reasons visible in dashboards?
Are provider quota failures alerted?
Do new nodes pass CNI, CSI, and node readiness checks?
Are PDBs protecting critical workloads during scale-down?
Is there a clear way to pause or limit autoscaler during maintenance?
```

## Practical Takeaway

Cluster autoscaler should make capacity response predictable.

It is healthy when pending pods trigger understandable decisions, node groups match workload needs, scale-up produces ready nodes, scale-down respects disruption safety, and operators can explain why autoscaler did or did not act.

If autoscaler is a mystery during incidents, it is not an automation layer. It is another system to troubleshoot.

## References

- [Packer Image Factory Workflow](/projects/packer-image-pipelines/image-factory-workflow/)
- [RKE2 Worker Join Failures From Calico Wrong Interface Selection](/field-notes/rke2-worker-join-calico-wrong-interface/)
- [Kubernetes Maintenance Evidence Bundles](/field-notes/kubernetes-maintenance-evidence-bundles/)
