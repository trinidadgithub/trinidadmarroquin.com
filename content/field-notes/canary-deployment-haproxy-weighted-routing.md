+++
title = 'Canary Deployments With HAProxy Weighted Routing'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for canary deployment mechanics using HAProxy weighted backends to control blast radius during rollout.'
tags = ['deployment', 'haproxy', 'cicd', 'docker']
categories = ['field-notes']
+++

A canary deployment sends a small fraction of traffic to a new version while the stable version handles the rest. If the canary fails, only the test fraction is affected.

For a runnable lab, see the [`canary-deployment` directory in the IaC repository](https://github.com/trinidadgithub/IaC/tree/main/Deployments/canary-deployment). It uses HAProxy weighted routing with raw C API servers.

HAProxy makes this pattern visible and controllable through weighted backend servers.

## Weight Ratio

```haproxy
backend servers
    balance leastconn
    server v1 api_v1:8080 weight 10 check
    server v2 api_v2:8080 weight 1 check
```

With weights 10 and 1, approximately 9% of requests reach v2. The weight proportion directly controls the blast radius:

- weight 10 : weight 1 = ~9% canary
- weight 10 : weight 10 = 50% (half the traffic, not a canary)
- weight 100 : weight 1 = ~1% canary
- weight 1 : weight 0 = disabled (v2 receives no traffic)

Start with a small fraction and increase as confidence grows.

## Balance Strategy

The `balance leastconn` directive distributes requests to the server with the fewest active connections. This matters for long-lived connections like WebSockets or streaming responses.

For short-lived request-response workloads, `roundrobin` works just as well and is more predictable. Choose `leastconn` when backend response time varies significantly.

## Health Checks Are TCP By Default

HAProxy's `check` directive sends a TCP connection check by default. It only verifies that the port is open, not that the application is healthy.

A real canary should have a dedicated health check endpoint:

```haproxy
option httpchk GET /healthz
```

Without an HTTP health check, HAProxy may route traffic to a v2 that accepts TCP connections but returns 500s on every request.

## Reading The Logs

Confirm which version served each request by checking response headers or structured logs. In a lab, the simplest approach is a version header:

```text
HTTP/1.1 200 OK
X-Version: v2
```

If the canary is weighted at 10%, roughly 1 in 10 requests should show the v2 header.

## Why Raw C In The Lab

The IaC repo canary lab uses a raw C HTTP server with BSD sockets. No framework, no dependencies. This is deliberate: deployment strategy labs should test traffic behavior, not framework configuration. If the lab requires understanding a web framework before testing the canary, it misses the point.

## Production Translation

Lab canary:

```text
HAProxy -> v1 (weight 10) | v2 (weight 1) -> manual observation
```

Production canary:

```text
service mesh -> v1 (traffic) | v2 (traffic) -> metrics comparison -> auto-promote or auto-rollback
```

The lab teaches the weight concept. Production requires automated analysis and decision gates.

## Acceptance Criteria

- Weighted traffic reaches both versions.
- Health checks catch an unresponsive canary before user impact.
- Request distribution matches the configured weight ratio.
- Rollback is a config reload away.
- Canary logs are distinguishable from stable logs.
