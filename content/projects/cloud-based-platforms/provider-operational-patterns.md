+++
title = 'Cloud Provider Operational Patterns'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial model for documenting cloud operational patterns by provider and platform discipline.'
tags = ['cloud', 'operations', 'platform']
categories = ['projects']
+++

Cloud operations become easier when provider differences are documented as patterns, not rediscovered during incidents.

The useful pattern is to separate provider-specific commands from provider-neutral operating expectations.

## Pattern Categories

Document patterns by discipline:

- identity and access.
- network routing and exposure.
- compute lifecycle.
- storage and backup.
- Kubernetes integration.
- observability and audit logging.
- cost and capacity review.
- incident response.

For each provider, keep the same structure so operators can compare behavior quickly.

## Provider Notes

Each provider page should answer:

- What is the account boundary called?
- What is the network boundary called?
- Where are audit logs configured?
- How are service identities created and rotated?
- Where are quotas and limits reviewed?
- How do private endpoints and public exposure work?
- Which services are approved for production?

## Runbook Shape

Every operational pattern should include:

- intent.
- owner.
- safe read-only checks.
- common failure modes.
- remediation path.
- escalation path.

## Acceptance Criteria

- Operators can find provider-specific commands without rewriting the operating model.
- Patterns are organized by discipline, not by one-off incidents.
- Cloud differences are documented where they matter.
- Shared expectations remain consistent across AWS, Azure, Google Cloud, and private cloud.

## References

- AWS Well-Architected Framework.
- Google Cloud Architecture Framework.
- Microsoft Cloud Adoption Framework.
