+++
title = 'Burn-Rate Alerting Concepts For Operators'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Conceptual field note explaining burn-rate alerts, error-budget math, multi-window alerting, common failure modes, and incident review questions for operators.'
tags = ['sre', 'slo', 'sli', 'alerting', 'observability', 'incident-response', 'operations']
categories = ['field-notes']
+++

Burn-rate alerting is easier to operate when the team understands the concepts before touching Prometheus rules.

The implementation details matter, but the operational idea is simple: alert when a service is consuming its allowed failure budget too quickly. That is different from alerting because a metric crossed a convenient threshold.

This note explains the mental model behind burn-rate alerts. For Prometheus examples and alert rule structure, see [SLO Burn-Rate Alerting With Prometheus](/field-notes/slo-burn-rate-alerting-prometheus/). For dashboard design after the alert fires, see [What To Put On An SLO Dashboard](/field-notes/slo-dashboard-first-response-view/).

## Burn-Rate Alerts

A burn-rate alert tells you how fast a service is consuming its error budget.

Instead of asking:

```text
Is the error rate above 5%?
```

it asks:

```text
Are we using the allowed failure budget too quickly?
```

That distinction matters. A `5%` error rate may be catastrophic for one service and tolerable for another, depending on the SLO.

For example:

```text
SLO:             99% successful requests over 30 days
Error budget:    1% failed eligible requests
```

If the service is currently failing `1%` of eligible requests, it is burning budget at the planned rate. If it is failing `2%`, it is burning budget twice as fast as planned.

Burn-rate alerts are useful because they connect paging to reliability policy. The alert is no longer just "red line crossed." It is "the service is consuming reliability budget fast enough that an operator should act."

## Error-Budget Math

An error budget is the failure allowance created by an SLO.

```text
error budget = 100% - SLO target
```

Examples:

| SLO Target | Error Budget |
|---|---:|
| `99%` | `1%` |
| `99.9%` | `0.1%` |
| `99.99%` | `0.01%` |

The burn-rate formula is:

```text
burn rate = observed failure rate / allowed failure rate
```

For a `99%` SLO, the allowed failure rate is `1%`.

```text
Observed failure rate: 2%
Allowed failure rate:  1%
Burn rate:             2x
```

For a `99.9%` SLO, the allowed failure rate is `0.1%`.

```text
Observed failure rate: 1%
Allowed failure rate:  0.1%
Burn rate:             10x
```

That second example is the one that catches teams. A `1%` error rate can sound small in a dashboard review, but for a `99.9%` SLO it burns budget ten times faster than allowed.

## Multi-Window Alerting

A single alert window is usually either too noisy or too slow.

A short window catches sharp incidents quickly:

```text
5 minutes
```

But short windows are noisy. One bad deploy, one dependency timeout, or one small traffic burst can create a scary ratio.

A longer window confirms the problem is sustained:

```text
1 hour
```

But long windows are slower to react if used alone.

Multi-window alerting combines both ideas:

```text
5-minute burn rate is high
AND
1-hour burn rate is high
```

That means the problem is happening now and has lasted long enough to matter.

A practical pattern is:

| Alert Type | Windows | Typical Action |
|---|---|---|
| Fast burn | `5m` and `1h` | Page on-call |
| Slow burn | `30m` and `6h` | Ticket or team-channel review |

Fast burn alerts are for active user-impacting failures. Slow burn alerts are for reliability drift that should not wait for a monthly review.

## Common Failure Modes

Burn-rate alerts can still be bad alerts if the underlying SLI or ownership model is weak.

### The SLI Is Too Broad

If all endpoints are aggregated together, a broken low-traffic path can disappear under a noisy high-traffic path.

Example:

```text
/healthz receives 1,000,000 successful requests
/checkout receives 500 failed requests
```

The overall service may look healthy while the important user path is broken.

Use service-level alerts for paging, but keep endpoint-level dashboards for diagnosis. For critical paths, define separate SLIs.

### Expected Client Errors Count Against The Budget

Not every `4xx` response is service unreliability. A `400` caused by invalid client input is different from a `500` caused by a broken database connection.

The team needs a written policy:

```text
5xx responses count against availability.
Expected 4xx responses are excluded.
Unexpected 4xx patterns are reviewed separately.
```

Without that policy, every burn-rate discussion turns into a debate during the incident.

### Low Traffic Creates Noisy Ratios

If one request arrives and fails, the failure rate is `100%`.

That is mathematically true, but it may not be operationally meaningful.

Low-traffic services usually need a minimum request-volume gate. The alert should only fire after enough requests have occurred for the ratio to be trustworthy.

### The Alert Has No Owner

A correct alert routed to a general channel is still weak operations.

Every burn-rate alert should have:

- service owner.
- severity.
- routing destination.
- dashboard link.
- runbook or first-response notes.
- escalation path.

If ownership is unclear, the alert creates noise instead of action.

### Error Budget Does Not Change Behavior

An error budget is not just a report. It should influence release risk.

The policy should answer:

```text
What happens when burn rate is high?
What happens when the monthly budget is nearly exhausted?
Do risky releases slow down?
Who decides when reliability work takes priority?
```

If nothing changes when the budget is exhausted, the SLO is decoration.

## Incident Review Checks

After a burn-rate alert fires, review the alert as part of the incident review.

Ask:

```text
Did the alert fire before customers reported the issue?
Did it route to the right team?
Did the dashboard answer the first questions?
Was the SLI policy correct?
Was the threshold too sensitive or too slow?
Did the incident consume enough budget to change release risk?
```

If customers reported the issue first, the alert was missing, too slow, or measuring the wrong thing.

If the alert routed to the wrong team, ownership metadata or Alertmanager routing needs work.

If the dashboard did not answer the first questions, the alert is not operationally complete. The on-call engineer should be able to see request rate, error rate, burn rate, latency, affected endpoint, recent deployments, and likely ownership from the first response view.

Do not tune burn-rate alerts only to reduce noise. Tune them to improve decision quality.

## Practical Takeaway

Burn-rate alerting works because it links alerting to a reliability promise.

The strongest implementation has four parts:

1. A clear SLI policy.
2. Error-budget math that matches the SLO.
3. Multi-window alerts that separate fast incidents from slow drift.
4. Incident reviews that improve the alert after it fires.

If those pieces are missing, Prometheus can still evaluate the rule, but the organization may not know what decision the rule is supposed to support.

## References

- [Google SRE Workbook - Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [Google SRE Workbook - Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [SLO Burn-Rate Alerting With Prometheus](/field-notes/slo-burn-rate-alerting-prometheus/)
- [What To Put On An SLO Dashboard](/field-notes/slo-dashboard-first-response-view/)
- [Incident Review Template For SRE Teams](/field-notes/incident-review-template-for-sre-teams/)
- [On-Call Escalation Policy For Platform Teams](/field-notes/on-call-escalation-policy-platform-teams/)
