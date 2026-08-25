+++
title = 'Service Mesh mTLS And Traffic Policy Rollout'
date = 2026-08-25T00:00:00-05:00
draft = false
description = 'Field note for rolling out service mesh mTLS, authorization, retries, timeouts, and traffic splitting without breaking healthy service paths.'
tags = ['service-mesh', 'kubernetes', 'mtls', 'traffic-management', 'operations']
categories = ['field-notes']
+++

mTLS is often the reason teams adopt a service mesh. It is also where a mesh stops being invisible plumbing.

The goal is not "turn on strict mode." The goal is to prove that service identity, policy, and traffic behavior match the application's real dependency graph.

## Inventory Service Calls

Before enforcing policy, map the request path:

```text
source workload -> service -> destination workload -> external dependency
```

Capture:

- namespace and service account for each workload.
- protocols and ports.
- internal and external dependencies.
- readiness and liveness probe paths.
- jobs, cronjobs, and maintenance callers.
- traffic that bypasses Kubernetes Service objects.

Do not enforce mTLS from memory. Hidden callers become outage reports.

## Roll Out In Modes

A safe rollout separates visibility from enforcement:

```text
observe plaintext -> enable permissive mTLS -> prove identities
-> add authorization policy -> move to strict where callers are known
```

Use permissive mode to discover who actually talks to whom. Strict mode belongs after the dependency map and telemetry agree.

## Traffic Policy Ownership

Retries, timeouts, and circuit breakers are application behavior.

The platform can provide defaults, but service owners must confirm:

- which requests are idempotent.
- how long callers can wait.
- whether retries amplify load during partial failure.
- which errors should trigger fallback.
- whether traffic splitting is safe for stateful sessions.

A mesh retry policy can turn one failing request into three failing requests. That may protect a flaky dependency, or it may overload it faster.

## Pre-Change Checks

Before changing mesh policy, verify:

- control-plane pods are healthy.
- affected workloads have current sidecars or proxies.
- certificate issuance is healthy.
- destination services have ready endpoints.
- existing error rate and latency are known.
- rollback manifests or prior policy are available.

Then validate from both sides of the request path. A passing ingress check does not prove internal service-to-service policy is correct.

## Failure Model

The quiet failure is enforcing identity before discovering traffic:

```text
mTLS strict enabled -> known app path works
-> cronjob, probe, or maintenance caller lacks identity
-> intermittent failure appears later
```

The operating rule: observe first, enforce second, and make traffic policy an application-owned decision with platform guardrails.
