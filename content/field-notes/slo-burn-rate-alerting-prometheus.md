+++
title = 'SLO Burn-Rate Alerting With Prometheus'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Field note for turning request-based SLIs into practical Prometheus burn-rate alerts, including error-budget math, multi-window alerting, failure modes, and incident review checks.'
tags = ['sre', 'slo', 'sli', 'prometheus', 'alerting', 'observability', 'incident-response', 'operations']
categories = ['field-notes']
+++

An SLO is not useful because it exists in a document. It becomes useful when it changes operational behavior.

Burn-rate alerting is one way to make that happen. Instead of paging because an error rate crossed a random threshold, the alert asks a better question:

```text
How quickly are we consuming the error budget?
```

That question is easier to defend during an incident. It connects the alert to user impact, time window, and reliability policy instead of dashboard aesthetics.

For the conceptual model behind these rules, see [Burn-Rate Alerting Concepts For Operators](/field-notes/burn-rate-alerting-concepts-for-operators/).

## Start With A Request-Based SLI

For HTTP services, start with request success ratio before adding more complicated signals.

Example policy:

```text
Successful requests: all non-5xx responses
Failed requests: 5xx responses
Excluded or reviewed separately: expected 4xx responses
```

That policy has to be explicit. A `400` from invalid user input is not the same kind of failure as a `500` from a broken dependency. If the team cannot agree on what counts as failure, the burn-rate alert will only make the disagreement louder.

With Prometheus counters, the error-rate SLI usually looks like this:

```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

For the SLI lab used elsewhere on this site, the same shape is:

```promql
sum(rate(sli_http_requests_total{status=~"5.."}[5m]))
/
sum(rate(sli_http_requests_total[5m]))
```

## Convert SLO Target To Error Budget

If the SLO target is `99%` successful requests over thirty days, the allowed error budget is `1%`.

```text
SLO target:       99%
Error budget:    1%
Allowed failure: 0.01 of eligible requests
```

Burn rate compares the current error rate against that allowed failure rate.

```text
burn rate = current error rate / allowed error rate
```

If the service is failing `2%` of requests and the budget allows `1%`, the burn rate is `2x`.

```text
0.02 / 0.01 = 2
```

At `2x`, the service is consuming budget twice as fast as planned. If nothing changes, the thirty-day budget will be exhausted in about fifteen days.

## Basic Burn-Rate Query

For a `99%` SLO, the error budget is `0.01`.

```promql
(
  sum(rate(http_requests_total{status=~"5.."}[5m]))
  /
  sum(rate(http_requests_total[5m]))
)
/
0.01
```

Using the SLI lab metric names:

```promql
(
  sum(rate(sli_http_requests_total{status=~"5.."}[5m]))
  /
  sum(rate(sli_http_requests_total[5m]))
)
/
0.01
```

This produces a multiplier:

| Burn Rate | Meaning |
|---|---|
| `0.5` | Budget is being consumed at half the planned rate. |
| `1` | Budget is being consumed exactly at the planned rate. |
| `2` | Budget is being consumed twice as fast as planned. |
| `14.4` | Budget is being consumed fast enough to exhaust a 30-day budget in about two days. |

Do not page on every value above `1`. A service can briefly run above budget without creating a paging-worthy incident. Burn-rate alerting works best with multiple windows.

## Why Multi-Window Alerts Matter

A short window catches fast-moving failures. A long window proves the problem is sustained.

If the short window fires alone, it may be a spike. If the long window fires alone, the incident may be moving too slowly for a page but still needs review. When both fire together, the signal is stronger.

The common pattern is:

```text
fast burn:  short window + medium window
slow burn:  medium window + long window
```

Fast burn alerts page. Slow burn alerts can usually route to a ticket or team channel unless the service is critical enough to page earlier.

## Example PrometheusRule

This example assumes a `99%` availability SLO and a thirty-day window. Adjust the metric names, labels, team routing, and thresholds for the service.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: example-api-slo-burn-rate
  namespace: monitoring
spec:
  groups:
    - name: example-api-slo.rules
      rules:
        - alert: ExampleApiFastBurnRate
          expr: |
            (
              sum(rate(http_requests_total{service="example-api",status=~"5.."}[5m]))
              /
              sum(rate(http_requests_total{service="example-api"}[5m]))
            ) / 0.01 > 14.4
            and
            (
              sum(rate(http_requests_total{service="example-api",status=~"5.."}[1h]))
              /
              sum(rate(http_requests_total{service="example-api"}[1h]))
            ) / 0.01 > 14.4
          for: 2m
          labels:
            severity: page
            service: example-api
            slo: availability
          annotations:
            summary: "example-api is burning availability error budget quickly"
            description: "The 5m and 1h burn rates are above 14.4x. Treat this as active user-impacting reliability loss."
        - alert: ExampleApiSlowBurnRate
          expr: |
            (
              sum(rate(http_requests_total{service="example-api",status=~"5.."}[30m]))
              /
              sum(rate(http_requests_total{service="example-api"}[30m]))
            ) / 0.01 > 6
            and
            (
              sum(rate(http_requests_total{service="example-api",status=~"5.."}[6h]))
              /
              sum(rate(http_requests_total{service="example-api"}[6h]))
            ) / 0.01 > 6
          for: 15m
          labels:
            severity: ticket
            service: example-api
            slo: availability
          annotations:
            summary: "example-api is steadily burning availability error budget"
            description: "The 30m and 6h burn rates are above 6x. Review before the budget loss becomes an incident."
```

The exact threshold is not sacred. The behavior is the important part: page when burn is fast and sustained; create visible follow-up when burn is slower but still meaningful.

## Add Guardrails For Low Traffic

Low-volume services can produce noisy ratios. One failed request out of one request is `100%` failure, but it may not deserve a page.

Add a minimum request-volume gate:

```promql
sum(rate(http_requests_total{service="example-api"}[5m])) > 1
```

Then combine it with the burn-rate expression:

```promql
(
  (
    sum(rate(http_requests_total{service="example-api",status=~"5.."}[5m]))
    /
    sum(rate(http_requests_total{service="example-api"}[5m]))
  ) / 0.01 > 14.4
)
and
sum(rate(http_requests_total{service="example-api"}[5m])) > 1
```

For low-traffic internal services, request-count gates may be more useful than request-rate gates:

```promql
sum(increase(http_requests_total{service="example-api"}[5m])) > 50
```

The point is not to hide failures. The point is to avoid waking someone up for a mathematically correct but operationally weak signal.

## Dashboard Before Pager

Before enabling the alert, build a dashboard row that shows the same ingredients:

- request rate.
- 5xx error rate.
- burn rate by window.
- p95 and p99 latency.
- recent deploy markers, if available.
- top status codes by route or endpoint.

The on-call engineer should be able to open the alert and answer:

```text
Is this real?
Is this localized?
Is this getting worse?
What changed recently?
Which service owner should act?
```

If the alert does not lead to that dashboard context, the alert is not ready.

## Failure Modes

Burn-rate alerts fail in predictable ways.

### The SLI Is Too Broad

Aggregating all routes can hide the broken path. A low-volume checkout endpoint can disappear under a high-volume health endpoint.

Prefer service-level alerts for paging and route-level panels for diagnosis. For critical endpoints, define separate SLIs.

### The SLI Includes Expected Client Errors

If expected `4xx` responses count against availability, a bad client or integration test can look like a service outage. Decide the policy before the alert exists.

### The Alert Has No Ownership

A good burn-rate alert still fails if it routes to a general channel where no one owns it. Every alert needs service ownership, escalation path, and a runbook or dashboard link.

### The Team Treats Error Budget As Decoration

If budget exhaustion never changes release behavior, the alert becomes another graph with a pager attached. The policy has to say what happens when budget is burning too quickly.

## Incident Review Checks

After a burn-rate alert fires, review the alert itself:

```text
Did it fire before customers reported the issue?
Did it route to the right team?
Did the dashboard answer the first five questions?
Was the SLI policy correct?
Was the threshold too sensitive or too slow?
Did the incident consume enough budget to change release risk?
```

Do not tune the alert only to reduce noise. Tune it to improve decision quality.

## Practical Takeaway

Burn-rate alerting is useful because it links paging to reliability policy. It gives the on-call engineer a reason to act beyond "a line crossed a threshold."

Start with one request-based SLO. Define the failure policy. Add multi-window burn-rate alerts. Gate low-traffic noise. Attach a dashboard. Review every page until the alert either earns trust or gets rewritten.

## References

- [Google SRE Workbook — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Prometheus Alerting Rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Burn-Rate Alerting Concepts For Operators](/field-notes/burn-rate-alerting-concepts-for-operators/)
- [Building A Small SLI Lab With Flask, Prometheus, And Grafana](/field-notes/sli-lab-flask-prometheus-grafana/)
