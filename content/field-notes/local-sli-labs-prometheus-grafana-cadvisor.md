+++
title = 'Local SLI Labs With Prometheus Grafana And cAdvisor'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for using a local Docker and Terraform lab to validate service-level indicators with Prometheus, Grafana, and cAdvisor.'
tags = ['sre', 'observability', 'prometheus', 'grafana', 'terraform', 'docker']
categories = ['field-notes']
+++

A local SLI lab is useful when the goal is to understand the signal path before introducing production platform complexity.

For a live local demo, see the [`sli_app` lab in the IaC repository](https://github.com/trinidadgithub/IaC/tree/main/sli_app). If the lab does not run as expected, open a bug fix request against that repository with the failing command, host OS, Docker version, Terraform version, and relevant logs.

The important part is not that everything runs on one machine. The important part is that the lab has the same basic observability chain operators rely on later:

```text
instrumented app -> Prometheus scrape -> dashboard -> operational question
```

## Lab Shape

A small SLI lab can be built from four moving pieces:

- an application that exposes Prometheus metrics.
- Prometheus with explicit scrape targets.
- Grafana with a pre-provisioned data source and dashboard.
- cAdvisor for container-level resource visibility.

Terraform can wire the containers together with the Docker provider, but it should not hide the operational dependencies. Prometheus still needs reachable targets. Grafana still needs a healthy data source. Dashboards are only useful if the metric labels and queries match the application.

## First Checks

After apply, start with reachability rather than dashboard screenshots:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Check that Prometheus can see its targets:

```text
http://localhost:9090/targets
```

The app and cAdvisor targets should be `UP`. If they are not, fix scraping before debugging Grafana.

## Metrics To Prove First

For an HTTP service, prove the basic SLI inputs before creating complex dashboards:

- request count by endpoint and status.
- request latency by endpoint.
- error responses separated from successful responses.
- container CPU and memory signals from cAdvisor.

Example Prometheus checks:

```promql
request_count_total
request_latency_seconds_bucket
container_memory_usage_bytes
container_cpu_usage_seconds_total
```

The names must match the actual instrumentation. A dashboard with stale query names is worse than no dashboard because it creates false confidence.

## Operator Notes

Local SLI labs usually fail in predictable ways:

- Prometheus is healthy, but scrape targets are down.
- the app exposes metrics on a different port than the service port.
- Grafana starts before its data source is ready.
- dashboards import successfully but query labels do not match.
- cAdvisor can run but lacks the host mounts needed for useful container visibility.

Treat these as signal-chain failures. Move from producer to collector to visualization instead of jumping straight to the UI.

## What To Carry Forward

Before promoting the pattern beyond a lab, decide:

- which SLIs represent user experience.
- which labels are stable enough for dashboards and alerts.
- which scrape intervals are useful without creating unnecessary load.
- how dashboards are provisioned, versioned, and reviewed.
- what alert would actually page a human.

The lab proves mechanics. Production requires ownership, retention, access control, alert routing, and service-level intent.

## Acceptance Criteria

- App metrics endpoint is reachable.
- Prometheus target page shows expected targets as `UP`.
- Grafana data source connects to Prometheus.
- Dashboard panels answer a specific operating question.
- Resource metrics and application metrics can be correlated during a test failure.
