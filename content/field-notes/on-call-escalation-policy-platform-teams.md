+++
title = 'On-Call Escalation Policy For Platform Teams'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'A practical on-call escalation policy template for platform teams operating shared infrastructure, Kubernetes, observability, and deployment systems.'
tags = ['sre', 'on-call', 'incident-response', 'operations', 'platform-engineering', 'observability']
categories = ['field-notes']
+++

An escalation policy should tell the on-call engineer what to do when ownership, severity, or impact is unclear.

It is not only a paging schedule. A schedule says who gets woken up. A policy says when to escalate, who should join, and what decisions are expected.

For platform teams, this matters because incidents often cross boundaries: Kubernetes, networking, storage, CI/CD, observability, identity, and application ownership.

Related notes:

- [SLO Burn-Rate Alerting With Prometheus](/field-notes/slo-burn-rate-alerting-prometheus/)
- [What To Put On An SLO Dashboard](/field-notes/slo-dashboard-first-response-view/)
- [Incident Review Template For SRE Teams](/field-notes/incident-review-template-for-sre-teams/)

## Policy Goals

The policy should optimize for clear ownership and fast mitigation.

Good escalation policies answer:

```text
Who owns first response?
When should the incident be escalated?
Who can make risk decisions?
When should application teams be pulled in?
When should leadership or customer-facing teams be notified?
How is handoff handled?
```

The goal is not to page more people. The goal is to page the right people earlier when the incident needs them.

## Severity Levels

Define severity by user impact and operational risk, not by how scary a metric looks.

Example platform severity model:

| Severity | Meaning | Expected Response |
|---|---|---|
| SEV1 | Widespread production outage, data loss risk, security incident, or critical customer impact | Page immediately, incident commander assigned, frequent updates |
| SEV2 | Significant degradation, single critical service impaired, high burn rate, or major platform function degraded | Page owning team, open incident channel, escalate if not mitigated quickly |
| SEV3 | Limited impact, slow burn, partial degradation, or non-critical platform issue | Team-channel alert or ticket with owner and deadline |
| SEV4 | Informational, maintenance follow-up, or low-risk anomaly | Backlog or routine review |

Tie severity to SLO signals where possible.

Example:

```text
Fast burn-rate alert for a customer-facing service defaults to SEV2.
Fast burn-rate alert plus widespread customer reports defaults to SEV1.
Slow burn-rate alert with no immediate customer report defaults to SEV3 unless budget impact is severe.
```

## Primary On-Call Responsibilities

The primary on-call engineer owns first response.

Responsibilities:

- acknowledge the page.
- assess user impact.
- open an incident channel when needed.
- start mitigation or rollback if the path is known.
- escalate when impact, ownership, or mitigation is unclear.
- document key timestamps.
- hand off cleanly if the incident exceeds their shift.

The primary on-call does not need to solve every problem alone. Waiting too long to escalate is a policy failure, not a badge of ownership.

## Secondary On-Call Responsibilities

The secondary on-call engineer provides depth and continuity.

Responsibilities:

- join SEV1 and SEV2 incidents when paged or requested.
- take investigation tasks from the primary.
- help validate dashboards, logs, traces, and recent changes.
- prepare handoff if the incident crosses shifts.
- support communication if no incident commander is assigned yet.

The secondary should not silently shadow. If they join, they should take explicit tasks.

## Incident Commander

Assign an incident commander for SEV1 and complex SEV2 incidents.

Responsibilities:

- maintain incident structure.
- assign owners for investigation, mitigation, and communication.
- keep updates on cadence.
- decide when to escalate further.
- protect responders from parallel requests.
- declare mitigation and resolution after evidence supports it.

The incident commander does not have to be the deepest technical expert. Their job is coordination and decision flow.

## Escalation Triggers

Escalate when any of these are true:

- user impact is confirmed and mitigation is not obvious.
- the burn rate remains high after initial response.
- the service owner is unclear.
- the incident crosses platform and application boundaries.
- data integrity, security, or compliance may be involved.
- rollback is risky or blocked.
- the primary responder has been investigating for 15 minutes without a credible mitigation path.
- customer-facing teams need status updates.
- the incident may exceed the current on-call shift.

Time-boxing matters. If the first responder spends too long alone, the incident loses time and context.

## Ownership Routing

Platform teams often receive alerts for systems they enable but do not fully own.

Use a routing model like this:

| Symptom | Primary Owner | Escalation Partner |
|---|---|---|
| Kubernetes control plane unhealthy | Platform | Infrastructure/networking |
| Node pressure or kubelet failures | Platform | Infrastructure/virtualization |
| Storage attach or mount failures | Platform | Storage owner |
| CI/CD deployment failure | Platform or delivery engineering | Application owner |
| Application SLO burn-rate alert | Application owner | Platform if platform dependency suspected |
| Observability pipeline outage | Observability/platform | Application owners if alerts are blind |
| Certificate expiration risk | Platform/security | Application owner if app-specific |

Document ownership in the alert, dashboard, and service catalog. If ownership only exists in someone's memory, it will fail during an incident.

## Communication Cadence

For SEV1 and SEV2 incidents, define update cadence.

Example:

```text
SEV1: internal update every 15 minutes until mitigated
SEV2: internal update every 30 minutes until mitigated
Customer-facing update: coordinated through support, account, or status-page owner
```

Each update should include:

- current impact.
- current mitigation status.
- next action.
- next update time.

Avoid optimistic guesses. Say what is known, what is being checked, and when the next update will arrive.

## Handoff Rules

Handoff should preserve operational context.

Minimum handoff:

```text
Current severity:
Current impact:
What changed:
What was tried:
Current hypothesis:
Active mitigations:
Open risks:
Next action:
Links to incident channel, dashboard, ticket, and logs:
```

Do not hand off with only "see thread." Threads are not operational summaries.

## Fatigue And Safety

On-call policy should account for responder fatigue.

Rules worth writing down:

- page secondary after a defined duration or severity.
- rotate incident commander during long incidents.
- require handoff after extended overnight response.
- avoid assigning the same person all follow-up actions after a major incident.
- review noisy alerts after every painful shift.

Reliability depends on humans being able to make good decisions. Exhausted responders make worse decisions.

## Escalation Policy Template

```markdown
# On-Call Escalation Policy: <team/service>

## Scope

Systems covered:
Systems excluded:

## Severity Definitions
| Severity | Definition | Response |
|---|---|---|

## Primary On-Call
Responsibilities:

## Secondary On-Call
Responsibilities:

## Incident Commander
Assignment rules:
Responsibilities:

## Escalation Triggers

## Ownership Routing
| Symptom | Primary Owner | Escalation Partner |
|---|---|---|

## Communication Cadence

## Handoff Rules

## Fatigue And Safety Rules

## Review Cadence
```

## Review Cadence

Review the escalation policy after:

- SEV1 incidents.
- painful SEV2 incidents.
- missed pages.
- pages routed to the wrong team.
- major ownership changes.
- team schedule changes.
- new critical services are added.

An escalation policy is operational code. If the environment changes and the policy does not, the policy drifts.

## Practical Takeaway

An on-call policy should reduce hesitation.

The primary on-call should know when to escalate. The secondary should know how to help. The incident commander should know when to coordinate instead of debug. Stakeholders should know when they will hear updates.

Clear escalation turns incident response from individual heroics into a repeatable operating model.
