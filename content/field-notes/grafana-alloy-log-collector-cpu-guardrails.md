+++
title = 'Grafana Alloy Log Collector CPU Guardrails'
date = 2026-09-15T00:00:00-05:00
draft = false
description = 'Field note for diagnosing Grafana Alloy log collector pods that saturate Kubernetes nodes and vSphere hosts, then applying conservative CPU limits while preserving rollback.'
tags = ['kubernetes', 'grafana', 'alloy', 'loki', 'observability', 'operations']
categories = ['field-notes']
+++

Log collection is workload traffic.

When Grafana Alloy runs as a DaemonSet without a CPU limit, a log storm, destination retry loop, or backlog catch-up can consume most of a worker node. In virtualized clusters, that can also saturate the ESXi hosts underneath the cluster.

## Symptom

The host-level signal may look like a vSphere capacity issue first:

```text
esxi-a  CPU 95-105%
esxi-b  CPU 90-100%
esxi-c  CPU 5%
```

Kubernetes then points at a smaller set of nodes:

```bash
kubectl --context cluster-a top nodes | sort -k3 -nr | head
```

Example shape:

```text
worker-14  7200m  90%
worker-04  7100m  89%
worker-01  7000m  88%
worker-13  6900m  87%
```

The pod view identifies the workload:

```bash
kubectl --context cluster-a top pods -A --no-headers \
  | sort -k3 -hr \
  | head -20
```

Example shape:

```text
grafana-alloy  alloy-logs-gm6sf   7100m  2800Mi
grafana-alloy  alloy-logs-95xtv   7000m  2800Mi
grafana-alloy  alloy-logs-jhc4w   6900m  2800Mi
grafana-alloy  alloy-logs-k2gmc   5800m  3000Mi
```

If the hot Alloy pods sit on the hot nodes, the issue is not abstract host pressure. It is a log collection workload consuming node CPU.

## Check The Resource Policy

Inspect the DaemonSet resources before changing anything:

```bash
kubectl --context cluster-a -n grafana-alloy get ds alloy-logs \
  -o jsonpath='{range .spec.template.spec.containers[*]}name={.name}{"\n"}resources={.resources}{"\n---\n"}{end}'
```

A risky shape is:

```text
name=alloy
resources={"limits":{"memory":"3Gi"},"requests":{"cpu":"200m","memory":"256Mi"}}
---
name=config-reloader
resources={"requests":{"cpu":"10m","memory":"50Mi"}}
```

The Alloy container requests `200m`, but has no CPU limit. It can consume the whole node if the workload allows it.

## Save A Rollback

Save the current object before patching:

```bash
kubectl --context cluster-a -n grafana-alloy get ds alloy-logs -o yaml \
  > alloy-logs.before.yaml
```

Rollback is then simple:

```bash
kubectl --context cluster-a -n grafana-alloy apply -f alloy-logs.before.yaml
```

## Apply A Conservative Limit

Patch only the Alloy container. Leave sidecars alone unless they are part of the problem.

```bash
kubectl --context cluster-a -n grafana-alloy patch ds alloy-logs \
  --type=json \
  -p='[
    {
      "op":"replace",
      "path":"/spec/template/spec/containers/0/resources",
      "value":{
        "requests":{"cpu":"200m","memory":"256Mi"},
        "limits":{"cpu":"1000m","memory":"3Gi"}
      }
    }
  ]'
```

This is a mitigation, not a permanent capacity model. The goal is to stop the collector from starving the node while the root cause is investigated.

## Restart Old Uncapped Pods

The patch affects only newly created pods. Existing pods may keep running without the CPU limit until replaced.

Check rollout state:

```bash
kubectl --context cluster-a -n grafana-alloy get ds alloy-logs -o wide
```

Find pods that have not picked up the limit:

```bash
kubectl --context cluster-a -n grafana-alloy get pods \
  -l app.kubernetes.io/name=alloy-logs \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.nodeName}{" cpuLimit="}{.spec.containers[0].resources.limits.cpu}{"\n"}{end}' \
  | sort
```

Delete hot uncapped pods so the DaemonSet recreates them with the new limit:

```bash
kubectl --context cluster-a -n grafana-alloy delete pod \
  alloy-logs-gm6sf \
  alloy-logs-95xtv \
  alloy-logs-jhc4w \
  alloy-logs-k2gmc
```

Then verify:

```bash
kubectl --context cluster-a -n grafana-alloy get ds alloy-logs -o wide
kubectl --context cluster-a top nodes | sort -k3 -nr | head
kubectl --context cluster-a -n grafana-alloy top pods | sort -k2 -hr | head
```

A successful mitigation looks like this:

```text
DaemonSet: desired=16 current=16 ready=16 up-to-date=16 available=16
hot workers: 85-90% CPU -> 2-20% CPU
top Alloy pod: 6000-7000m CPU -> less than 200m CPU
ESXi hosts: 95-105% CPU -> about 45% CPU
```

The exact numbers do not matter. The shape does: capped Alloy pods should stop dominating node CPU.

## Inspect Alloy Logs For Cause

After the immediate pressure is controlled, inspect recent Alloy logs:

```bash
kubectl --context cluster-a -n grafana-alloy logs ds/alloy-logs \
  -c alloy \
  --since=30m \
  | grep -Ei 'error|dropping|retry|batch|queue|backpressure|tailing|loki'
```

Two patterns are especially useful.

Missing Loki endpoints:

```text
failed to list rules from loki
lookup loki-ruler.loki.svc.cluster.local: no such host
lookup loki-gateway.loki.svc.cluster.local: no such host
final error sending batch, no retries left, dropping data
```

Broad file tailing or backlog catch-up:

```text
start tailing file path=/var/log/pods/<namespace>_<pod>_<uid>/<container>/0.log
```

Repeated missing-service errors do not prove they caused all CPU burn by themselves, but they are a strong configuration clue. Alloy should not repeatedly try to use a Loki service that does not exist in that environment.

## Decide Ownership

The CPU cap protects the cluster. It does not decide the observability architecture.

If Loki is expected to exist soon, keep the cap and deploy the missing services. If Loki is not part of the environment yet, disable the Alloy components that depend on it until the backend exists.

Suggested handoff statement:

```text
Alloy log collection was repeatedly trying to use Loki services that do not exist in this environment. Several uncapped Alloy DaemonSet pods consumed multiple CPU cores each and saturated worker nodes. A temporary 1 CPU limit reduced node and host pressure. Please either deploy the expected Loki services or remove the Loki rule/write components from this environment until Loki exists.
```

## Watch For Falling Behind

A CPU limit can reveal under-capacity if log volume is genuinely high. Watch for:

```bash
kubectl --context cluster-a -n grafana-alloy top pods | sort -k2 -hr | head

kubectl --context cluster-a -n grafana-alloy logs ds/alloy-logs -c alloy --since=10m \
  | grep -Ei 'dropping|backpressure|retry|batch|queue|too old|error'
```

Warning signs:

```text
many Alloy pods pinned near 1000m for long periods
dropping data
queue or batch retry errors
growing node disk usage under /var/log/pods
missing logs in the destination once Loki exists
```

If the cap is too low, raise it gradually, for example from `1000m` to `1500m` or `2000m`. Do not remove the limit entirely unless the backend and log volume problem have been fixed.

## Operating Rule

Observability agents need resource guardrails like any other workload.

For Alloy log collection on Kubernetes:

```text
1. Correlate vSphere host CPU to Kubernetes nodes.
2. Correlate hot nodes to Alloy pods.
3. Save the DaemonSet as rollback evidence.
4. Add a conservative CPU limit.
5. Restart old uncapped pods so the limit actually applies.
6. Verify node, pod, and host CPU.
7. Inspect Alloy logs for missing backends, retry loops, and broad tailing.
8. Fix the backend/configuration owner, then tune the limit intentionally.
```

For broader Loki incident-readiness design, see [Loki Tempo And Incident Correlation Paths](/field-notes/loki-tempo-incident-correlation-path/). For general metrics-system safety boundaries, see [Prometheus Operations And Query Safety](/field-notes/prometheus-operations-query-safety/).
