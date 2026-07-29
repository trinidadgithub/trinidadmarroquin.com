+++
title = 'What To Put On An SLO Dashboard'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'A practical SLO dashboard checklist for on-call engineers responding to burn-rate alerts and reliability incidents.'
tags = ['sre', 'slo', 'sli', 'observability', 'grafana', 'incident-response', 'operations']
categories = ['field-notes']
+++

An SLO dashboard should help the on-call engineer make the first decision during an incident.

It is not a decoration layer for metrics. It is the operational view that answers:

```text
Is this user-impacting?
How fast are we burning error budget?
What changed?
Who owns the response?
```

If the dashboard cannot answer those questions quickly, the alert may be technically correct but operationally incomplete.

This note pairs with [SLO Burn-Rate Alerting With Prometheus](/field-notes/slo-burn-rate-alerting-prometheus/) and [Burn-Rate Alerting Concepts For Operators](/field-notes/burn-rate-alerting-concepts-for-operators/).

## Start With The Service Contract

Put the SLO definition at the top of the dashboard.

Include:

- service name.
- owning team.
- paging route.
- SLO target.
- SLO window.
- SLI query summary.
- what counts as failure.
- what is intentionally excluded.

Example:

```text
Service: checkout-api
Owner: platform-payments
SLO: 99.9% successful eligible requests over 30 days
Failure policy: 5xx responses and dependency timeout responses count as failures
Excluded: expected 4xx validation errors and health checks
```

This prevents a common incident failure: operators arguing about the metric while users are already impacted.

## Show Request Volume First

Every ratio needs context.

Show request rate near the top of the dashboard:

```promql
sum(rate(http_requests_total{job="checkout-api"}[5m]))
```

Request volume helps answer:

- Is the service receiving normal traffic?
- Did traffic drop because clients stopped calling it?
- Is a small number of requests creating a noisy failure ratio?
- Is the alert firing during low-traffic hours?

For low-volume services, add a minimum-traffic panel or annotation. A `100%` failure rate from one failed request is mathematically true, but it is not always page-worthy.

## Show Success Ratio And Error Ratio

Show the user-facing success ratio in the same language as the SLO.

Example success ratio:

```promql
sum(rate(http_requests_total{job="checkout-api",code!~"5.."}[5m]))
/
sum(rate(http_requests_total{job="checkout-api"}[5m]))
```

Show the error ratio next to it:

```promql
sum(rate(http_requests_total{job="checkout-api",code=~"5.."}[5m]))
/
sum(rate(http_requests_total{job="checkout-api"}[5m]))
```

Use the same failure policy as the alert rule. If the dashboard and alert use different definitions, incident response starts with confusion.

## Show Burn Rate

Burn rate connects current failures to the reliability promise.

For a `99.9%` SLO, the allowed failure rate is `0.001`.

```promql
(
  sum(rate(http_requests_total{job="checkout-api",code=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{job="checkout-api"}[5m]))
)
/
0.001
```

Show at least two windows:

| Panel | Purpose |
|---|---|
| `5m` burn rate | Confirms the problem is happening now |
| `1h` burn rate | Confirms the problem is sustained |
| `6h` burn rate | Shows slow reliability drift |
| `30d` budget remaining | Shows policy impact |

The on-call engineer should not have to calculate budget impact manually while triaging.

## Show Latency Percentiles

Availability is not the whole user experience.

Show latency percentiles for the SLO-critical path:

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket{job="checkout-api"}[5m]))
)
```

Include:

- `p50` for baseline behavior.
- `p95` for typical tail pain.
- `p99` for severe tail behavior.

Do not rely on averages. Averages hide the users who are having the worst experience.

If latency has its own SLO, show it as a separate SLO panel instead of burying it under availability.

## Break Down The Failing Path

After the top-level SLO panels, provide breakdowns for diagnosis.

Useful breakdowns:

- endpoint or route.
- status code class.
- dependency.
- region or cluster.
- tenant or customer tier, if safe and appropriate.
- workload version.
- pod or instance.

Example route error panel:

```promql
sum by (route, code) (
  rate(http_requests_total{job="checkout-api",code=~"5.."}[5m])
)
```

The service-level SLO tells you whether to respond. The breakdown panels help you decide where to respond.

## Add Change Context

Many incidents are change-related.

Add visible context for:

- deployments.
- configuration changes.
- infrastructure changes.
- dependency maintenance.
- feature-flag changes.
- alert rule changes.

In Grafana, use annotations or event panels. A simple deployment marker can reduce minutes of guessing.

The first useful incident question is often:

```text
What changed before the burn rate increased?
```

The dashboard should make that question easy to answer.

## Add Ownership And Response Links

The dashboard should route the operator toward action.

Include links to:

- service repository.
- runbook.
- Alertmanager route.
- escalation policy.
- recent deployments.
- logs view.
- trace search.
- Kubernetes namespace or workload view.

If the service has no runbook, link to the incident review template and make creating a runbook a follow-up.

## Avoid Dashboard Failure Modes

Common mistakes:

- Too many panels on the first screen.
- Alert queries and dashboard queries do not match.
- No traffic volume context.
- No owner or escalation link.
- Percentiles missing from latency panels.
- Endpoint breakdowns shown before the service-level SLO.
- Dashboards built for monthly review instead of incident response.

The first screen should be boring and decisive. Put exploratory panels lower on the page.

## First-Response Layout

A practical layout:

| Row | Panels |
|---|---|
| Service contract | owner, SLO target, window, failure policy, runbook |
| User impact | request rate, success ratio, error ratio |
| Budget impact | burn rate `5m`, burn rate `1h`, budget remaining |
| Latency | `p50`, `p95`, `p99` |
| Failure breakdown | route, status code, dependency, cluster |
| Change context | deploys, config changes, infra changes |
| Response links | logs, traces, runbook, escalation, repo |

That layout supports the first ten minutes of response. It does not try to replace deep debugging tools.

## Review Questions

Use these questions during dashboard review:

```text
Can a new on-call engineer identify the owner in under 30 seconds?
Does the dashboard use the same SLI definition as the alert?
Can the dashboard show whether the alert is still active?
Can it show whether the issue is getting better or worse?
Can it show what changed before the alert fired?
Can it separate user impact from internal noise?
Can it guide the operator to the next system of record?
```

If the answer is no, the dashboard is not finished.

## Practical Takeaway

An SLO dashboard should support operational decisions, not just display metrics.

Start with the service contract, show request volume, show SLO health, show burn rate, show latency percentiles, then provide breakdowns and response links.

The goal is simple: when a burn-rate alert fires, the dashboard should help the on-call engineer decide whether to page, mitigate, escalate, or watch.

## References

- [SLO Burn-Rate Alerting With Prometheus](/field-notes/slo-burn-rate-alerting-prometheus/)
- [Burn-Rate Alerting Concepts For Operators](/field-notes/burn-rate-alerting-concepts-for-operators/)
- [Building A Small SLI Lab With Flask, Prometheus, And Grafana](/field-notes/sli-lab-flask-prometheus-grafana/)
