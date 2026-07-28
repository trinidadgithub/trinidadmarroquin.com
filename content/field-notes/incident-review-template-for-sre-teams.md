+++
title = 'Incident Review Template For SRE Teams'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'A practical incident review template for SRE and platform teams focused on impact, detection, mitigation, contributing factors, and follow-up quality.'
tags = ['sre', 'incident-response', 'postmortem', 'operations', 'observability', 'reliability']
categories = ['field-notes']
+++

An incident review should improve the system, not assign blame.

The useful output is a better service, a better alert, a better runbook, or a clearer ownership boundary. If the review only produces a timeline and a vague action item, it is documentation theater.

This template is designed for platform and SRE teams running production services, Kubernetes platforms, observability stacks, and shared infrastructure.

Related notes:

- [SLO Burn-Rate Alerting With Prometheus](/field-notes/slo-burn-rate-alerting-prometheus/)
- [What To Put On An SLO Dashboard](/field-notes/slo-dashboard-first-response-view/)
- [On-Call Escalation Policy For Platform Teams](/field-notes/on-call-escalation-policy-platform-teams/)

## Incident Summary

```text
Incident title:
Incident date:
Severity:
Status:
Services affected:
Primary owner:
Incident commander:
Review date:
```

Write a short summary in plain language.

Example:

```text
Checkout API returned elevated 5xx responses for 42 minutes after a database connection pool change. The SLO burn-rate alert paged the on-call engineer, the change was rolled back, and error rates returned to baseline.
```

Avoid starting with root cause if root cause was not known during the incident. Start with observed impact.

## Customer Or User Impact

Describe impact from the user's perspective.

```text
Who was affected?
What could they not do?
How many requests, users, tenants, or clusters were affected?
When did impact start?
When did impact end?
Was there data loss, degraded performance, or failed transactions?
```

Good impact statements are specific:

```text
Between 14:08 and 14:50 UTC, approximately 7.4% of checkout requests returned 5xx responses. Users could browse products but some checkout attempts failed before payment authorization.
```

Weak impact statements hide the operational reality:

```text
The service was degraded for some users.
```

## Detection

Document how the incident was detected.

```text
Detected by:
Detection time:
First alert:
First human acknowledgement:
Customer report before alert: yes/no
```

Review the detection path:

- Did the alert fire before customers reported the issue?
- Did it route to the right team?
- Did it include a useful dashboard link?
- Did the alert describe user impact or only metric symptoms?
- Was the alert too sensitive, too slow, or missing?

If the incident was customer-reported before monitoring detected it, create a monitoring follow-up.

## Timeline

Use objective timestamps.

```text
14:02 - Deployment started for checkout-api version 2026.07.28.1
14:08 - 5xx error rate increased above baseline
14:12 - Fast burn-rate alert fired
14:14 - On-call acknowledged page
14:18 - Incident channel opened
14:24 - Database connection pool change identified
14:32 - Rollback started
14:50 - Error rate returned to baseline
15:10 - Incident resolved
```

Do not use the timeline to imply blame. The timeline is evidence for understanding detection, diagnosis, mitigation, and communication.

## What Happened

Describe the technical sequence.

Useful structure:

```text
Trigger:
Immediate failure:
Why users were affected:
Why existing controls did not prevent it:
Why detection happened when it did:
```

Separate confirmed facts from reasonable hypotheses.

Example:

```text
Confirmed: The new connection pool limit caused workers to queue requests under normal traffic.
Confirmed: Checkout requests timed out and returned 5xx responses.
Hypothesis: The staging load test did not reproduce production concurrency because it used synthetic traffic with lower fan-out.
```

## Contributing Factors

Most incidents have multiple contributing factors.

Consider:

- recent deploys or configuration changes.
- missing canary or rollback guardrails.
- dependency behavior.
- resource exhaustion.
- unclear ownership.
- missing runbook steps.
- dashboards that did not answer first-response questions.
- alert thresholds that were not tied to SLO impact.

Avoid stopping at the first technical cause. The cause may explain why the service failed, but not why the organization was vulnerable to that failure.

## Mitigation And Recovery

Document what restored service.

```text
Mitigation used:
Rollback required: yes/no
Data repair required: yes/no
Customer communication required: yes/no
Verification used:
```

Recovery is not complete just because a deployment was rolled back. Verify user-facing signals:

- request success ratio returned to baseline.
- burn rate returned below alert threshold.
- latency percentiles returned to baseline.
- dependency errors stopped.
- backlog or queue depth recovered.
- support/customer reports stopped.

## SLO And Error-Budget Impact

If the service has an SLO, quantify the impact.

```text
SLO target:
SLO window:
Error budget consumed:
Peak burn rate:
Budget remaining after incident:
Release risk changed: yes/no
```

This is where SLOs become operational policy.

If an incident consumed a meaningful amount of budget, the team should decide whether to slow risky changes, prioritize reliability work, or adjust the SLO definition.

## Communication Review

Review internal and external communication.

```text
Was an incident channel opened?
Was there a clear incident commander?
Were updates sent on a predictable cadence?
Were customer-facing teams informed?
Was the status page updated, if applicable?
Was resolution clearly communicated?
```

Communication failures create second-order incidents. A technically mitigated incident can still be operationally messy if stakeholders do not know what happened or what to expect.

## What Went Well

Capture strengths so they are repeated.

Examples:

- burn-rate alert fired before customer reports.
- rollback completed quickly.
- dashboard showed the failing route.
- incident commander role was clear.
- dependency owner joined quickly.

This section should be specific. "Team responded well" is too vague to repeat.

## What Could Be Improved

Focus on system and process improvements.

Examples:

- staging load test did not represent production concurrency.
- dashboard lacked deployment annotations.
- runbook did not include rollback verification.
- escalation path for database ownership was unclear.
- alert description did not include the SLO failure policy.

Avoid writing improvements as personal criticism.

## Follow-Up Actions

Every action item needs an owner and a deadline.

```text
Action:
Owner:
Due date:
Tracking link:
Verification method:
```

Good action item:

```text
Add deployment annotations to the checkout SLO dashboard.
Owner: platform-observability
Due: 2026-08-07
Verification: next dashboard review confirms deploy markers appear within 60 seconds of rollout start.
```

Weak action item:

```text
Improve monitoring.
```

If an action cannot be verified, it is not ready.

## Review Checklist

Use this checklist before closing the incident review:

- Impact is described from the user perspective.
- Timeline uses timestamps and facts.
- Detection path is reviewed.
- SLO and error-budget impact are quantified when possible.
- Contributing factors go beyond the immediate technical trigger.
- Follow-up actions have owners and due dates.
- Monitoring, dashboard, and runbook gaps are captured.
- The review avoids blame and focuses on system improvement.

## Template

```markdown
# Incident Review: <title>

## Summary

## Impact

## Detection

## Timeline

## What Happened

## Contributing Factors

## Mitigation And Recovery

## SLO And Error-Budget Impact

## Communication Review

## What Went Well

## What Could Be Improved

## Follow-Up Actions

| Action | Owner | Due Date | Verification |
|---|---|---|---|

## Review Checklist
```

## Practical Takeaway

The incident review is part of the reliability system.

Use it to improve alerts, dashboards, runbooks, escalation, and release safety. A useful review changes how the next incident is detected, understood, or mitigated.

If nothing changes after the review, the team wrote a report but did not improve operations.
