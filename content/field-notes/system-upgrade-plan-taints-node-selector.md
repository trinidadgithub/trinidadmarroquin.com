+++
title = 'RKE2 System Upgrade Plans Need Taint-Aware Node Selection'
date = 2026-09-08T00:00:00-05:00
draft = false
description = 'A Kubernetes operations field note on system-upgrade-controller Plans that select tainted nodes but do not include matching tolerations.'
tags = ['kubernetes', 'rke2', 'rancher', 'system-upgrade-controller', 'upgrades', 'operations']
categories = ['field-notes']
+++

An upgrade Plan can be syntactically correct and still create pods that can never schedule.

One recurring pattern is a Plan that excludes control-plane and etcd nodes, but unintentionally includes monitor or infrastructure nodes with custom taints. The controller creates Jobs for those nodes. The scheduler rejects the pods. The Jobs age out with `DeadlineExceeded`. The cluster keeps generating warning events even though the nodes are healthy.

The bug is not in the node. It is in the relationship between Plan selection and node taints.

## Symptom

Events show upgrade Jobs failing to schedule:

```text
Warning  FailedScheduling  pod/system-upgrade-agent-plan-worker-1
0/19 nodes are available: node(s) did not match pod affinity/selector,
node(s) had untolerated taint {workload: monitoring},
node(s) had untolerated taint {CriticalAddonsOnly: true}

Warning  DeadlineExceeded  job/system-upgrade-agent-plan-worker-1
Job was active longer than specified deadline
```

The affected node may be `Ready`. Nothing is wrong with kubelet. The Plan selected a node that the rendered upgrade pod is not allowed to run on.

## Check The Plan Selector

Inspect Plans and their selectors:

```bash
kubectl -n system-upgrade get plans -o wide
kubectl -n system-upgrade get plan agent-plan -o yaml
```

Look for selector logic such as:

```yaml
nodeSelector:
  matchExpressions:
    - key: node-role.kubernetes.io/control-plane
      operator: DoesNotExist
    - key: node-role.kubernetes.io/etcd
      operator: DoesNotExist
```

That selector matches more than workers. It also matches any non-control-plane, non-etcd node: monitor nodes, ingress nodes, storage nodes, or other specialized pools.

## Compare Against Node Taints

List labels and taints for candidate nodes:

```bash
kubectl get nodes -o json \
  | python3 -c '
import json,sys
for node in json.load(sys.stdin)["items"]:
    name=node["metadata"]["name"]
    labels=node["metadata"].get("labels",{})
    taints=node["spec"].get("taints",[])
    roles=[k.removeprefix("node-role.kubernetes.io/") for k in labels if k.startswith("node-role.kubernetes.io/")]
    print(name, ",".join(roles) or "<none>", taints)
'
```

Then compare those taints with the Plan's tolerations:

```bash
kubectl -n system-upgrade get plan agent-plan \
  -o jsonpath='{.spec.tolerations}{"\n"}'
```

If the Plan selects a node but the pod does not tolerate that node's taints, the Job cannot run.

## Include Or Exclude The Node Pool

There are two valid fixes.

If the node pool should be upgraded by this Plan, add a matching toleration:

```yaml
tolerations:
  - key: workload
    operator: Equal
    value: monitoring
    effect: NoSchedule
```

If the node pool should not be upgraded by this Plan, narrow the selector:

```yaml
nodeSelector:
  matchExpressions:
    - key: node-role.kubernetes.io/worker
      operator: Exists
```

The right answer depends on ownership. Monitor, storage, and ingress nodes often have different disruption windows than general workers.

## Validate Before Syncing GitOps

Before merging the Plan change, verify which nodes it will target:

```bash
kubectl get nodes -l node-role.kubernetes.io/worker -o name
```

The important question is operational, not YAML-shaped:

```text
Will every selected node accept the upgrade pod?
Should every selected node be upgraded in this wave?
```

After GitOps applies the change, watch Jobs and events:

```bash
kubectl -n system-upgrade get jobs,pods -o wide
kubectl get events -A --sort-by=.lastTimestamp \
  | grep -i 'system-upgrade\|FailedScheduling\|DeadlineExceeded'
```

Kubernetes events are short-lived. A quiet event list is not a historical audit.

## Practical Takeaway

Every system-upgrade Plan needs two matching contracts:

```text
selector says which nodes the Plan wants
tolerations say which selected taints the upgrade pod can cross
```

If those contracts disagree, the controller will create work the scheduler can never run.

## References

- [Rancher RKE2 Upgrade Pods Touch The Host Filesystem](/field-notes/rancher-rke2-upgrade-pods-host-filesystem/)
- [Rancher System Upgrade Controller Emergency Stop](/field-notes/rancher-system-upgrade-controller-emergency-stop/)
- [Kubernetes Taints And Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
