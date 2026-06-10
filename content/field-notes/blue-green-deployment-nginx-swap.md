+++
title = 'Blue-Green Deployment With NGINX'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for blue-green deployment mechanics using NGINX upstream switching, covering manual and weighted patterns.'
tags = ['deployment', 'nginx', 'cicd', 'docker']
categories = ['field-notes']
+++

Blue-green deployment keeps two environments running. At any time, one environment serves production traffic and the other waits for the next release.

For a runnable lab, see the [`blue-green-simulation` directory in the IaC repository](https://github.com/trinidadgithub/IaC/tree/main/Deployments/blue-green-simulation). Version 1 demonstrates a manual NGINX upstream switch. Version 2 adds weighted routing and named containers.

The switch is the critical moment. How it happens determines whether the pattern is fast rollback or just extra complexity.

## The NGINX Upstream Switch

The simplest blue-green switch is an NGINX `upstream` block with one active server and one standby:

```nginx
upstream backend {
    server blue:5000;
    # server green:5000;
}
```

Comment or uncomment the server line, then reload NGINX. Traffic moves to the active environment.

## Reload, Not Restart

```bash
docker exec nginx nginx -s reload
```

The reload applies configuration changes without dropping active connections. A restart would terminate the worker processes and lose in-flight requests. Always reload when changing upstream targets.

## Proxy Headers Matter

When switching between backends, the proxy must forward the original client information:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

If these headers are missing or inconsistent, the new backend sees different client information than the old one, which can break logging, rate limiting, and application logic.

## Manual Switch Failure Modes

A manual upstream edit is the lowest-common-denominator blue-green pattern. It fails when:

- the wrong server line is uncommented.
- a syntax error in `nginx.conf` prevents reload.
- the backend is not ready but the switch happens anyway.
- no one checks whether the new environment is healthy before switching.
- the operator forgets to reload after editing the config.

The manual pattern teaches the mechanics. Automate the switch before relying on it in production.

## Weighted Routing As Blue-Green

NGINX supports weighted upstream servers:

```nginx
upstream backend {
    server blue:5000 weight=5;
    server green:5000 weight=1;
}
```

This is not true blue-green. Weighted routing is a gradual shift closer to canary deployment. True blue-green is an atomic cutover: all traffic moves from blue to green at once. Weighted routing blends traffic across both environments.

Use weighted routing when the goal is to test the new environment with a fraction of traffic before committing. Use a hard upstream switch when the goal is instant rollback capability.

## Named Containers For Debugging

In Docker Compose, set `container_name` on each service:

```yaml
services:
  blue:
    container_name: blue
  green:
    container_name: green
  nginx:
    container_name: router
```

Named containers make debugging predictable:

```bash
docker exec -it router curl http://blue:5000
docker logs blue
docker logs green
```

Without named containers, Docker assigns random names and every debug session starts with `docker ps` to find the right container.

## Acceptance Criteria

- Upstream switch moves all traffic to the target environment.
- `nginx -s reload` applies changes without dropping connections.
- Proxy headers are identical before and after the switch.
- The standby environment is running and healthy before the switch.
- Rollback is a single reload away.
