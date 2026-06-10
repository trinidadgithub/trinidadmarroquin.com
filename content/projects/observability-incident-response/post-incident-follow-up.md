+++
title = 'Post-Incident Follow-Up'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial post-incident follow-up model for timelines, contributing factors, corrective actions, and measurable system improvements.'
tags = ['incidents', 'sre', 'operations']
categories = ['projects']
+++

Post-incident follow-up should improve the system, not just produce a document.

The useful output is a small set of changes that reduce recurrence, shorten detection, or make recovery safer.

## Timeline

Build a factual timeline:

- first signal.
- detection time.
- acknowledgement time.
- mitigation actions.
- recovery time.
- customer or user impact.
- follow-up decisions.

Avoid filling gaps with guesses. Mark unknowns explicitly.

## Analysis

Separate:

- trigger.
- contributing factors.
- detection gap.
- mitigation gap.
- recovery gap.
- durable fix.

Do not stop at the first human mistake. Ask what system condition made that mistake possible or likely.

## Corrective Actions

Good actions are specific:

- add alert for symptom X.
- remove noisy alert Y.
- add runbook step Z.
- test restore path monthly.
- enforce policy in CI.
- change ownership or escalation path.

Bad actions are vague:

```text
be more careful
improve monitoring
document better
```

## Acceptance Criteria

- Incident has a factual timeline.
- Customer or system impact is described clearly.
- Follow-up actions have owners and due dates.
- At least one action improves detection, mitigation, or prevention.
- Lessons are fed back into runbooks, alerts, or platform standards.

## References

- Google SRE Book: Managing Incidents.
- Google SRE Book: Postmortem Culture.
