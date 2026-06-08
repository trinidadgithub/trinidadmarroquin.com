+++
title = 'Projects'
date = 2026-06-08T12:36:18-05:00
draft = false
+++

These are starter areas for project writeups. Each project should explain the problem, constraints, design choices, and what changed operationally.

## Kubernetes Platform Operations

Work around keeping Kubernetes clusters maintainable: upgrades, node lifecycle, add-on management, access patterns, backup and restore expectations, and production readiness checks.

Good writeup topics:

- Cluster upgrade notes and rollback planning.
- Rancher-managed fleet organization.
- Standard namespace, ingress, storage, and policy conventions.
- Operational checklists for new clusters.

## Terraform Infrastructure Modules

Reusable Terraform patterns for infrastructure that needs to be reviewed, promoted, and changed safely.

Good writeup topics:

- Module boundaries that match ownership.
- State layout and environment promotion.
- Plan review practices.
- Handling secrets and generated values without hiding important changes.

## Packer Image Pipelines

Machine image builds for repeatable node or VM provisioning.

Good writeup topics:

- Base image hardening and patch cadence.
- Validation steps before publishing an image.
- Versioning images for rollback and auditability.
- Keeping image builds boring and predictable.

## Concourse CI/CD

Pipeline work focused on clear promotion paths, repeatable tasks, and failure visibility.

Good writeup topics:

- Pipeline structure for infrastructure repositories.
- Separating validation, planning, and apply steps.
- Resource design and credential handling.
- Making failures easy to triage from job output.

## Observability And Operations

Monitoring and alerting work that helps operators make decisions.

Good writeup topics:

- Service-level indicators and actionable alerts.
- Dashboard design for incident response.
- Log and metric naming conventions.
- Post-incident follow-up that improves the system instead of only the document.
