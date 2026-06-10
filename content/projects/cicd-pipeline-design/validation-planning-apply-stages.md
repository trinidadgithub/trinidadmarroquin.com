+++
title = 'Pipeline Validation Planning And Apply Stages'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial CI/CD stage model for validation, planning, approval, apply, and post-deploy verification.'
tags = ['cicd', 'terraform', 'automation']
categories = ['projects']
+++

Infrastructure pipelines should make change intent visible before they mutate anything.

The stage design should separate fast feedback from approval and execution.

## Stage Model

A practical infrastructure pipeline usually has:

```text
format -> validate -> security checks -> plan -> review -> apply -> verify
```

Each stage should produce evidence that the next stage can trust.

## Validation

Validation should be fast and safe:

- formatting.
- static syntax validation.
- provider initialization without touching production state when possible.
- unit-style checks for generated manifests.
- policy checks for obvious violations.

## Planning

Plan output is the core review artifact.

For Terraform, capture:

- command used.
- workspace or root module.
- variables used.
- provider lock file state.
- human-readable plan.
- JSON plan for automation.

## Apply

Apply should be controlled by branch, environment, approval, or change window.

Avoid automatic production applies from unreviewed commits. Automation should reduce toil, not remove accountability.

## Post-Deploy Verification

The pipeline should verify the result:

- resource exists.
- service is reachable.
- health checks pass.
- monitoring sees the new state.
- drift does not immediately reappear.

## Acceptance Criteria

- Failed validation blocks planning.
- Plan review happens before production apply.
- Apply output is retained.
- Verification is explicit.
- Rollback or recovery notes are linked to the change.
