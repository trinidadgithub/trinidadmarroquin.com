+++
title = 'Packer Base Image Hardening'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial model for Packer base image hardening, patch cadence, template ownership, and retirement.'
tags = ['packer', 'images', 'security']
categories = ['projects']
+++

Base images are production dependencies. Treat them like versioned platform artifacts, not disposable installer output.

Packer should create the repeatable baseline. Per-environment configuration should happen later through Terraform, cloud-init, configuration management, or bootstrap scripts.

## Baseline Contents

Images should include:

- OS updates at build time.
- required agents.
- VMware tools or cloud guest agents.
- logging and monitoring prerequisites.
- bootstrap entrypoint.
- security baseline packages.
- cleanup of machine identity before sealing.

Images should not include environment-specific secrets, static hostnames, or one-off workload configuration.

## Patch Cadence

Define how often images are rebuilt even when no feature changes are requested.

Recommended triggers:

- monthly patch cycle.
- critical CVE.
- guest agent update.
- bootstrap framework change.
- cloud or vSphere template requirement change.

## Retirement

Template retirement is part of image hygiene.

Track:

- current recommended image.
- previous rollback image.
- deprecated images.
- deletion date.
- dependent environments.

## Acceptance Criteria

- Images are reproducible from source.
- Build date and version are visible.
- Secrets are not baked into templates.
- Old images are retired intentionally.
- Downstream consumers know the supported image set.

## References

- Packer documentation: HCL Templates.
- Packer documentation: Build Block.
