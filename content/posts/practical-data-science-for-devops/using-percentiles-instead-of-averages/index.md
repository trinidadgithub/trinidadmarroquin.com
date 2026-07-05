+++
title = "Using Percentiles Instead Of Averages In Reliability Reviews"
date = 2026-07-05T00:00:00-05:00
draft = false
description = "Part 1 of Practical Data Science For DevOps And SRE: why average latency hides user pain, how p95 and p99 expose tail behavior, and how to validate the idea with a small Prometheus and Grafana SLI lab."
tags = ["devops", "sre", "data-science", "percentiles", "latency", "prometheus", "grafana", "sli", "observability"]
categories = ["Practical Data Science For DevOps And SRE"]
series = ["Practical Data Science For DevOps And SRE"]
+++

Part 1 of the Practical Data Science For DevOps And SRE series.

Average latency is easy to explain and easy to graph. That is why it shows up everywhere. It is also why it can mislead reliability reviews.

If most requests are fast but a meaningful slice of users wait several seconds, the average may still look healthy. The users in the slow tail do not experience the average. They experience the request they are waiting on.

Percentiles give DevOps and SRE teams a better way to talk about that tail.

## The Problem With Averages

An average compresses a distribution into one number. That can be useful for a quick summary, but it hides shape.

Consider a small set of request durations in seconds:

| Request | Duration |
|---|---:|
| 1 | 0.12 |
| 2 | 0.13 |
| 3 | 0.14 |
| 4 | 0.15 |
| 5 | 0.16 |
| 6 | 0.18 |
| 7 | 0.21 |
| 8 | 0.25 |
| 9 | 1.80 |
| 10 | 2.40 |

The average is about `0.55` seconds. That sounds acceptable if the service target is vague.

But two users waited nearly two seconds or more. If this is a checkout flow, login path, search endpoint, or API used by another service, those slow requests matter.

The average did not lie mathematically. It just answered a weaker operational question.

## Better Questions

Instead of asking only:

```text
What is the average latency?
```

Ask:

```text
How fast is the service for a typical request?
How slow is it for the slowest meaningful slice of users?
Is the tail getting worse over time?
Does the tail change by endpoint, method, or status code?
```

Those questions map better to percentiles.

| Metric | Practical Meaning |
|---|---|
| `p50` | Half of requests are faster than this value. Useful for typical behavior. |
| `p95` | 95% of requests are faster than this value. Useful for most-user experience. |
| `p99` | 99% of requests are faster than this value. Useful for tail pain. |

Percentiles are not magic. They still need context. But they preserve more operational truth than an average alone.

## Lab Context

This article uses the SLI lab from the companion IaC repository:

```text
https://github.com/trinidadgithub/IaC/tree/main/sli_app
```

The lab runs a Flask app, Prometheus, Grafana, and cAdvisor with Terraform-managed Docker containers. The Flask app intentionally creates variable latency and occasional failures so the graphs have something useful to show.

The application exposes a Prometheus histogram:

```text
sli_http_request_duration_seconds_bucket
```

That histogram is what makes p95 and p99 latency analysis possible.

## Run The Lab

From the lab directory:

```bash
cd IaC/sli_app/terraform
terraform init
terraform apply
```

Generate traffic from the `sli_app` directory:

```bash
cd ..
ITERATIONS=100 SLEEP_SECONDS=0 ./scripts/generate_traffic.sh
```

Open Grafana:

```text
http://localhost:3000
```

Credentials:

```text
username: admin
password: admin01
```

Open the SLI dashboard:

```text
http://localhost:3000/d/sli-lab-flask/sli-lab-flask-service
```

## Query p95 Latency

In Prometheus, p95 latency for the SLI lab can be queried with `histogram_quantile`:

```promql
histogram_quantile(
  0.95,
  sum by (le, endpoint, method) (
    rate(sli_http_request_duration_seconds_bucket[5m])
  )
)
```

This reads as:

```text
For each endpoint and method, estimate the latency value below which 95% of recent requests completed.
```

That is more useful than asking whether the average looks acceptable across the whole service.

## Query p99 Latency

p99 uses the same pattern with a different quantile:

```promql
histogram_quantile(
  0.99,
  sum by (le, endpoint, method) (
    rate(sli_http_request_duration_seconds_bucket[5m])
  )
)
```

p99 is more sensitive to rare slow requests. That can be valuable, but it can also be noisy when traffic volume is low. In a small lab, p99 may jump around. In production, p99 should be interpreted with request volume, endpoint criticality, and scrape window in mind.

## Compare Against Average Latency

You can still calculate average latency from Prometheus histogram data:

```promql
sum by (endpoint, method) (
  rate(sli_http_request_duration_seconds_sum[5m])
)
/
sum by (endpoint, method) (
  rate(sli_http_request_duration_seconds_count[5m])
)
```

This query is not useless. It tells you the mean request duration over the window. The mistake is treating it as the whole user experience.

In the lab, compare the average latency query with the p95 and p99 queries. Watch for cases where the average looks calm while p95 or p99 shows a slower tail.

## What To Look For In Grafana

On the SLI dashboard, focus on these panels:

- `Latency Percentiles`
- `Request Rate By Endpoint`
- `Status Code Breakdown`
- `5xx Error Rate`

Latency percentiles should not be reviewed alone. If p99 jumps during a tiny request window, it may represent one slow request. If p95 rises while request rate is healthy and error rate also increases, that is a stronger degradation signal.

The point is not to worship p95 or p99. The point is to see the shape of service behavior before turning it into a reliability claim.

## A Practical Review Pattern

During a reliability review, use a small sequence of questions:

1. What is the request rate for the endpoint?
2. What are p50, p95, and p99 doing over the same window?
3. Are slow requests concentrated on one endpoint or method?
4. Did error rate rise at the same time?
5. Did a deployment, infrastructure change, or dependency issue occur near the change in latency?

This is practical data science. It is not advanced modeling. It is disciplined observation using the data already produced by the system.

## Common Mistakes

Percentiles are better than averages for tail behavior, but they can still be misused.

Do not compare percentiles from different systems unless the measurement method is compatible. A p95 from load balancer logs, a p95 from application instrumentation, and a p95 from synthetic checks may describe different populations of requests.

Do not review p99 without traffic volume. A p99 from ten requests is not the same kind of signal as a p99 from ten thousand requests.

Do not aggregate unrelated endpoints too early. A slow write path can disappear inside a service-level aggregate if the read path has much higher traffic.

Do not set thresholds before understanding normal behavior. A good SLO should come from user expectations and observed service behavior, not from a random round number on a dashboard.

## What This Supports

Using percentiles supports better operational decisions:

- Whether an endpoint needs performance work.
- Whether an SLO should include latency.
- Whether a change degraded user experience.
- Whether a dashboard is hiding tail behavior.
- Whether alert thresholds are tied to meaningful user pain.

Percentiles do not replace engineering judgment. They make the discussion harder to fake.

## Field Note Takeaway

Average latency is a useful supporting signal, but it is a weak primary reliability measure. Users experience individual requests, not averages.

For reliability reviews, start with request rate, p95, p99, error rate, and endpoint context. That combination gives a clearer picture of whether the service is healthy for most users and whether the slow tail is becoming operationally meaningful.

When the lab is no longer needed, shut it down cleanly:

```bash
cd IaC/sli_app/terraform
terraform destroy
```

## References

- [Prometheus Histograms And Summaries](https://prometheus.io/docs/practices/histograms/)
- [Prometheus `histogram_quantile`](https://prometheus.io/docs/prometheus/latest/querying/functions/#histogram_quantile)
- [Google SRE Workbook: Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Building A Small SLI Lab With Flask, Prometheus, And Grafana](/field-notes/sli-lab-flask-prometheus-grafana/)
