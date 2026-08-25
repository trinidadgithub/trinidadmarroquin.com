+++
title = 'Service Mesh Telemetry And Debugging Checks'
date = 2026-08-25T00:00:00-05:00
draft = false
description = 'Field note for debugging service mesh incidents with proxy status, request telemetry, policy state, certificate health, and sidecar rollout evidence.'
tags = ['service-mesh', 'kubernetes', 'observability', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

Service mesh incidents are request-path incidents. Debug them like one.

The mesh adds useful telemetry, but it also adds another place where a request can fail. Start by proving whether the failure is application, ingress, Service/endpoints, NetworkPolicy, mesh policy, proxy health, or certificate state.

## Baseline The Path

Write the expected path before changing anything:

```text
client -> ingress/load balancer -> source workload proxy
-> destination service -> destination workload proxy -> application
```

Then check the non-mesh objects first:

```bash
kubectl get pods,svc,endpoints -n app-namespace
kubectl describe pod -n app-namespace app-pod
kubectl get events -n app-namespace --sort-by=.lastTimestamp
```

If the destination has no ready endpoints, the mesh is probably the messenger.

## Proxy And Control Plane Checks

Confirm the mesh components are healthy before debugging policy:

- control-plane pods are Ready.
- proxies are injected where expected.
- proxy versions match the supported rollout window.
- workloads restarted after injection labels changed.
- proxy resource requests are not causing scheduling pressure.
- sidecar readiness is not blocking application startup.

For mesh-specific CLIs, capture read-only status output before applying fixes. The exact command differs by implementation, but the evidence should answer whether the control plane thinks the proxy is configured.

## Policy And Identity Checks

When traffic fails only across a mesh boundary, inspect:

- mTLS mode for source and destination namespaces.
- authorization policy selecting the destination.
- service account identity used by the caller.
- destination rule or traffic policy affecting the service.
- retry and timeout behavior.
- certificate expiration or rotation failures.

The failure is often a selector mismatch. A policy can look correct while selecting no workloads or the wrong workloads.

## Telemetry That Matters

Useful dashboards show:

- request rate by source and destination.
- error rate by response code and policy decision.
- latency percentiles at proxy and application layers.
- TCP connection failures where HTTP telemetry is unavailable.
- mTLS success/failure counts.
- proxy restart and config-push errors.
- control-plane reconciliation latency.

Do not rely only on golden signals at ingress. Many mesh failures happen after the request has entered the cluster.

## Failure Model

The common failure is troubleshooting from the wrong edge:

```text
user path fails -> ingress looks healthy -> app pod looks healthy
-> mesh policy silently denies or reroutes -> team changes the app anyway
```

The operating rule: preserve the full request path, then prove which layer made the decision.
