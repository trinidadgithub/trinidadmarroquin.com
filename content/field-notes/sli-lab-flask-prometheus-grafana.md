+++
title = 'Building A Small SLI Lab With Flask, Prometheus, And Grafana'
date = 2026-06-30T00:00:00-05:00
draft = false
description = 'Field note for building a small local SLI lab with Flask, Terraform-managed Docker containers, Prometheus, and Grafana, including availability, latency percentiles, error-rate analysis, and simple trend awareness.'
tags = ['sre', 'sli', 'slo', 'prometheus', 'grafana', 'flask', 'docker', 'terraform', 'observability', 'data-science']
categories = ['field-notes']
+++

Service Level Indicators (SLIs) are easier to understand when they are tied to a working service. Abstract definitions are useful, but a small lab makes the tradeoffs visible: what counts as success, what counts as failure, how latency should be measured, and how trends can reveal degradation before a full incident.

This field note uses a companion lab in GitHub:

```text
https://github.com/trinidadgithub/IaC/tree/main/sli_app
```

The lab runs a small Flask application, exposes Prometheus metrics, provisions Prometheus and Grafana with Terraform, and includes a basic SLI dashboard. It also introduces lightweight data science habits: percentiles, rolling windows, error-rate comparison, and avoiding misleading averages.

## What This Lab Demonstrates

The application intentionally creates variable latency and occasional failures. A perfectly reliable demo app is not useful for learning reliability measurement.

The lab helps answer practical questions:

- What percentage of requests are successful?
- How slow is the service for typical users and tail users?
- Is the error rate stable, improving, or getting worse?
- Are `4xx` responses client errors, service errors, or excluded from the SLI?
- Which metrics belong on a Grafana dashboard?
- Which measurements could support an SLO later?

This is not a production architecture. It is a small observability lab for making SLI design concrete.

## Repository Layout

The lab lives under `sli_app` in the IaC repository.

```text
sli_app/
├── app.py
├── Dockerfile
├── requirements.txt
├── prometheus.yml
├── scripts/
│   └── generate_traffic.sh
└── terraform/
    ├── main.tf
    ├── outputs.tf
    ├── prometheus.yml
    └── grafana/
        ├── dashboards/
        │   ├── system-docker-monitoring.json
        │   └── sli-lab-dashboard.json
        └── provisioning/
            └── datasources/
                └── datasources.yml
```

Terraform creates a local Docker network and runs:

| Component | Purpose | Local URL |
|---|---|---|
| Flask app | Example service | `http://localhost:5000` |
| App metrics | Prometheus metrics endpoint | `http://localhost:8000` |
| Prometheus | Metrics storage/querying | `http://localhost:9090` |
| Grafana | Dashboards | `http://localhost:3000` |
| cAdvisor | Container metrics | `http://localhost:8080` |

Prometheus scrapes the Flask app through the shared Docker network at `sli_app:8000`.

## Service Shape

The Flask application exposes a few endpoints:

| Endpoint | Purpose | Behavior |
|---|---|---|
| `/` | Basic landing route | Returns `200` |
| `/healthz` | Local health check | Returns `200` |
| `/api/data` | Simulated read path | Adds random latency and occasional `500` errors |
| `/api/submit` | Simulated write path | Requires JSON input, adds random latency, occasional `500` errors |

The distinction between `/api/data` and `/api/submit` is useful because read and write paths often have different latency and reliability expectations.

## Metrics Exposed

The application uses `prometheus_client` and exposes metrics from a separate port, `8000`.

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `sli_http_requests_total` | Counter | `endpoint`, `method`, `status` | Request volume, availability, and error-rate analysis |
| `sli_http_request_duration_seconds_bucket` | Histogram | `endpoint`, `method`, `status`, `le` | p95/p99 latency analysis |

The explicit labels make it possible to separate endpoint behavior and status classes. That matters when distinguishing expected `400` responses from service-side `500` failures.

## Running The Lab

Clone the repository and apply Terraform:

```bash
git clone https://github.com/trinidadgithub/IaC.git
cd IaC/sli_app/terraform

terraform init
terraform validate
terraform apply
```

Grafana credentials:

```text
username: admin
password: admin01
```

Generate traffic from the `sli_app` directory:

```bash
chmod +x scripts/generate_traffic.sh
./scripts/generate_traffic.sh
```

For a longer run:

```bash
ITERATIONS=100 SLEEP_SECONDS=0 ./scripts/generate_traffic.sh
```

The traffic script sends valid read/write requests and occasional invalid submit requests to produce expected `400` responses.

## Defining The SLIs

SLIs should represent user-visible service behavior, not just container health.

| SLI | Practical Definition | Why It Matters |
|---|---|---|
| Availability | Ratio of successful requests to total eligible requests | Measures whether users can complete requests |
| Latency | p95 or p99 request duration by endpoint | Captures tail user experience better than averages |
| Error Rate | Ratio of server-side failures to total eligible requests | Shows service-side reliability degradation |
| Throughput | Request rate by endpoint | Helps interpret latency and error changes under load |

Container uptime is not the same as availability. A container can be running while every request fails.

## PromQL Examples

### Request Rate

```promql
sum by (endpoint, method) (
  rate(sli_http_requests_total[5m])
)
```

### Availability

This version treats `5xx` responses as service failures:

```promql
1 - (
  sum(rate(sli_http_requests_total{status=~"5.."}[5m]))
  /
  sum(rate(sli_http_requests_total[5m]))
)
```

If the SLI should exclude expected client errors from the denominator:

```promql
1 - (
  sum(rate(sli_http_requests_total{status=~"5.."}[5m]))
  /
  sum(rate(sli_http_requests_total{status!~"4.."}[5m]))
)
```

The policy decision matters. A bad client request may not indicate service unreliability, but a broken API contract might.

### Error Rate

```promql
sum(rate(sli_http_requests_total{status=~"5.."}[5m]))
/
sum(rate(sli_http_requests_total[5m]))
```

### p95 Latency

```promql
histogram_quantile(
  0.95,
  sum by (le, endpoint, method) (
    rate(sli_http_request_duration_seconds_bucket[5m])
  )
)
```

### p99 Latency

```promql
histogram_quantile(
  0.99,
  sum by (le, endpoint, method) (
    rate(sli_http_request_duration_seconds_bucket[5m])
  )
)
```

## Practical Data Science Layer

This lab becomes more valuable when metrics are treated as time-series data rather than isolated values.

### Percentiles Instead Of Averages

Average latency hides tail pain. If most users receive a response quickly but a meaningful minority wait several seconds, the average may look acceptable while real users suffer.

Use:

- p50 for typical behavior
- p95 for most-user experience
- p99 for tail pain

Average latency is still useful as a supporting signal, but it should not be the primary user-experience SLI.

### Error-Rate Analysis

Error rate should be reviewed by endpoint, method, and status class:

```promql
sum by (endpoint, method, status) (
  rate(sli_http_requests_total[5m])
)
```

This helps separate:

- expected `400` responses from bad input
- service-side `500` responses
- endpoint-specific failure patterns
- read-path versus write-path behavior

Define what counts against the SLI before reviewing the graph. Otherwise, teams are tempted to redefine reliability after the fact.

### Trend Awareness

A single five-minute window can be noisy. Compare short and longer windows to detect direction.

Short-window error rate:

```promql
sum(rate(sli_http_requests_total{status=~"5.."}[5m]))
/
sum(rate(sli_http_requests_total[5m]))
```

Longer-window error rate:

```promql
sum(rate(sli_http_requests_total{status=~"5.."}[30m]))
/
sum(rate(sli_http_requests_total[30m]))
```

If the five-minute rate is much higher than the thirty-minute rate, the service may be entering a failure window. If both are rising, the issue may be sustained.

### Simple Baseline Comparison

PromQL `offset` can compare current behavior with a prior window:

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(sli_http_request_duration_seconds_bucket[5m]))
)
```

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(sli_http_request_duration_seconds_bucket[5m] offset 1h))
)
```

This is not advanced forecasting. It is operational awareness: is the service behaving materially differently from a recent stable period?

## Grafana Dashboard

The lab provisions an **SLI Lab - Flask Service** dashboard with panels for:

- Request rate by endpoint
- Availability
- 5xx error rate
- p95 and p99 latency
- Status code breakdown
- Short-window versus long-window error-rate comparison

The dashboard is intentionally small. It focuses on operational questions rather than every metric available.

## What This Teaches

This lab reinforces several SRE lessons:

- SLIs must be user-centered.
- Availability is not container uptime.
- Averages hide tail latency.
- `4xx` and `5xx` responses should not be blindly grouped together.
- Short windows detect fast changes but are noisy.
- Longer windows show sustained behavior but can hide spikes.
- Dashboards should support decisions.
- SLOs should be based on carefully chosen SLIs, not whatever metric is easiest to graph.

## Gaps Addressed From The Original Notes

The original notes had the right general direction but needed cleanup before becoming a repeatable lab.

Key improvements:

- Updated Python and Flask dependency guidance.
- Removed unrelated outbound network traffic from the app.
- Used explicit Prometheus counters and histograms.
- Added labels for endpoint, method, and status.
- Kept the existing Terraform-managed Docker lab pattern.
- Pinned Prometheus and Grafana image versions.
- Added a repeatable traffic generation script.
- Added an SLI-specific Grafana dashboard.
- Defined availability from request success ratio, not uptime.
- Added explicit `4xx` versus `5xx` discussion.
- Used histogram percentiles for latency instead of averages.
- Added trend and baseline comparison examples.
- Removed unrelated GitHub branch-protection and C-programming notes.

## Next Steps

Good follow-up work for this lab:

1. Add alerting rules for high error rate and high p95 latency.
2. Define a sample SLO, such as `99% successful eligible requests over 30 days`.
3. Add an error budget calculation.
4. Export Prometheus data and perform a small Python notebook analysis.
5. Compare average latency against p95 and p99 latency to show why averages mislead.
6. Extend this into a first article for a practical data science for DevOps/SRE track.

The most useful next field note would be **Using Percentiles Instead Of Averages In Reliability Reviews**, because this lab already creates the data needed to demonstrate the point.

## References

- [Google SRE Book — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Prometheus Querying Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Prometheus Histograms And Summaries](https://prometheus.io/docs/practices/histograms/)
- [Grafana Prometheus Data Source](https://grafana.com/docs/grafana/latest/datasources/prometheus/)
- [Flask Documentation](https://flask.palletsprojects.com/)
