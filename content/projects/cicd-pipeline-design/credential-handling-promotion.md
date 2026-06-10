+++
title = 'Pipeline Credential Handling And Promotion'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial practices for CI/CD credential handling, pipeline resources, environment promotion, and branch-based controls.'
tags = ['cicd', 'secrets', 'automation']
categories = ['projects']
+++

Pipelines are privileged automation. Treat their credentials like production access, because that is what they are.

Credential design should match the environment and action being performed.

## Credential Handling

Use separate credentials for:

- read-only validation.
- non-production deploys.
- production plans.
- production applies.
- artifact publication.

Prefer short-lived credentials from Vault, cloud identity federation, or platform-native workload identity. Avoid storing long-lived credentials in pipeline definitions.

## Resource Design

Pipeline resources should make flow visible:

- source repository.
- versioned artifact.
- environment configuration.
- approval gate.
- deployment target.

Do not let a pipeline secretly fetch mutable inputs without recording what it used.

## Promotion

Promotion should move the same artifact or reviewed configuration forward.

Recommended flow:

```text
dev -> integration -> staging -> production
```

Promotion should not mean rebuilding a different artifact with the same name.

## Acceptance Criteria

- Production credentials are isolated from non-production jobs.
- Secret access is audited.
- Promotion uses immutable artifacts or reviewed commits.
- Branch rules match environment risk.
- Emergency bypass is documented and reviewed after use.
