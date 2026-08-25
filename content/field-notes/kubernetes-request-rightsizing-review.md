+++
title = 'Kubernetes Request Rightsizing Review'
date = 2026-08-24T00:00:00-05:00
draft = false
description = 'Field note for rightsizing Kubernetes CPU and memory requests without turning cost optimization into reliability risk.'
tags = ['finops', 'kubernetes', 'rightsizing', 'capacity', 'operations']
categories = ['field-notes']
+++

Kubernetes cost optimization usually starts with requests, not invoices.

The scheduler reserves capacity based on CPU and memory requests. Cluster autoscaler responds to unschedulable pods based on those requests. If requests are inflated, nodes are added early and stay underused. If requests are too low, workloads run cheap until they become noisy, evicted, or throttled.

Rightsizing is a reliability exercise with a cost outcome.

## Review Inputs

Do not rightsize from a single dashboard screenshot.

Use enough evidence to understand normal and peak behavior:

- current requests and limits.
- observed CPU and memory usage over a representative window.
- p95 or p99 memory working set where available.
- CPU throttling signals.
- restarts, OOM kills, and evictions.
- deployment replica count and rollout behavior.
- node group and autoscaler constraints.

The review window should include the workload's real pattern: batch windows, business hours, deploy spikes, and known seasonal traffic.

## Separate CPU And Memory

CPU and memory fail differently.

CPU is compressible. A low CPU limit can throttle a service and inflate latency while the pod remains healthy. Memory is not compressible. A low memory request may schedule too tightly, and a low memory limit can turn a traffic spike into an OOM kill.

Treat them separately:

- CPU requests: scheduling and baseline entitlement.
- CPU limits: throttling risk and noisy-neighbor control.
- memory requests: bin-packing and eviction priority.
- memory limits: hard failure boundary.

Do not apply a universal percentage rule to both.

## Change In Small Batches

Rightsizing should have a rollout plan:

```text
measure -> propose -> review owner -> change one workload class
-> observe -> expand -> record savings and risk
```

Start with obvious outliers:

- requests far above sustained usage.
- memory limits repeatedly hit.
- CPU limits causing throttling.
- idle dev workloads with production-sized requests.
- namespaces without quota or limit range policy.

Avoid cutting critical workloads during an incident response or before a major release. Cost work that creates reliability work is not optimization.

## Validate After Change

After changing requests or limits, check:

- pod restart count.
- OOMKilled events.
- CPU throttling.
- latency and error-rate SLIs.
- pending pods and autoscaler activity.
- node utilization and scale-down behavior.

If the cluster autoscaler removes nodes after rightsizing, validate disruption budgets and workload distribution. A lower bill is not the only acceptance criterion.

## Failure Model

The quiet failure is saving money by deleting safety margin nobody had named:

```text
requests reduced -> utilization improves -> bill drops
-> peak traffic arrives -> pods throttle or evict
-> reliability team buys back capacity under pressure
```

The operating rule: rightsizing should make unused capacity visible and intentional, not simply smaller.
