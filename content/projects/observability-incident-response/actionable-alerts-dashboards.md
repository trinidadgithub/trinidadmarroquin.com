+++
title = 'Actionable Alerts And Dashboards'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial guidance for actionable alerts, useful dashboards, ownership, and SRE-style signal quality.'
tags = ['observability', 'alerting', 'sre']
categories = ['projects']
+++

An alert should earn the right to interrupt a human.

Google SRE guidance emphasizes alerting on urgent, actionable, user-visible or imminently user-visible problems. That is the useful standard.

## Alert Review

Every page should answer:

- What is broken?
- Who owns it?
- What is the impact?
- What action should the responder take?
- Can this wait until business hours?

If the response is always robotic, automate it or downgrade it.

## Golden Signals

Dashboards should expose the four golden signals where applicable:

- latency.
- traffic.
- errors.
- saturation.

For infrastructure, add platform health signals such as node readiness, storage attach failures, controller health, certificate expiry, and capacity pressure.

## Dashboard Design

Dashboards should support decisions:

- Is the service healthy?
- Are users affected?
- What changed recently?
- Which dependency is unhealthy?
- Is capacity becoming a constraint?

Avoid dashboards that are just metric galleries.

## Local SLI Labs

A small Docker-based lab with an application, Prometheus, Grafana, and a container exporter is a useful way to practice SLI design. The lab should prove that metrics are scraped, dashboards answer operational questions, and credentials or host mounts are not mistaken for production-safe defaults.

See also: [Secret Handling In Terraform Managed Labs](/field-notes/terraform-lab-secret-handling/).

## Acceptance Criteria

- Every paging alert has an owner and runbook.
- Alerts are actionable and urgent.
- Dashboards show symptoms first, causes second.
- Noisy alerts are reviewed and removed.
- On-call feedback changes alert behavior.

## References

- Google SRE Book: Monitoring Distributed Systems.
- Google SRE Book: Practical Alerting.
