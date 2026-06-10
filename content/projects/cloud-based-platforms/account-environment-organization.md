+++
title = 'Cloud Account And Environment Organization'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial operating model for cloud account, project, subscription, and environment organization.'
tags = ['cloud', 'platform', 'governance']
categories = ['projects']
+++

Cloud platform organization is an operational control, not just a billing structure.

The account or project boundary should make it obvious who owns the workload, what environment it belongs to, which policies apply, and how blast radius is contained.

## Operating Model

Use separate top-level containers for production, non-production, shared services, security, and sandbox work. The exact cloud terms differ across AWS accounts, Azure subscriptions, and Google Cloud projects, but the principle is the same: production should not share an administrative or network boundary with experiments.

Minimum metadata for each environment:

- owner team.
- cost center or billing tag.
- environment classification.
- data classification.
- support and escalation path.
- lifecycle state.

## Environment Boundaries

Recommended boundaries:

- production: restricted access, change control, backup, monitoring, and incident expectations.
- non-production: realistic enough for testing, but isolated from production identity and data.
- shared services: DNS, artifact repositories, observability, security tooling, and central automation.
- sandbox: time-limited experimentation with quota and cleanup rules.

Avoid using naming alone as the control. Names help humans, but policies, IAM, network segmentation, and budget controls enforce the boundary.

## Review Checklist

- Is the owner clear without opening a ticket?
- Can production access be audited separately from development access?
- Are logs and security events routed centrally?
- Are budgets, quotas, or alerts configured?
- Is there a retirement path for unused environments?

## References

- AWS Well-Architected Framework.
- Google Cloud Architecture Framework.
- Microsoft Cloud Adoption Framework.
