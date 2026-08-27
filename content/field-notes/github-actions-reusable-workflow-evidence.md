+++
title = 'GitHub Actions Reusable Workflow Evidence'
date = 2026-08-26T00:00:00-05:00
draft = false
description = 'Field note for using GitHub Actions reusable workflows with pinned versions, explicit inputs, concurrency controls, artifact retention, and reviewable CI evidence.'
tags = ['github-actions', 'cicd', 'automation', 'workflow', 'operations']
categories = ['field-notes']
+++

Reusable workflows reduce copy-paste. They also centralize failure, permissions, and release risk.

Treat a reusable workflow like an internal platform API: version it, document its inputs, and preserve the evidence callers need during review or incident response.

## Pin The Interface

Call reusable workflows by a reviewed ref:

```yaml
jobs:
  terraform-plan:
    uses: org/platform-workflows/.github/workflows/terraform-plan.yml@v1
    with:
      working-directory: infra/prod
      environment: prod
```

Avoid calling shared workflow logic from a moving branch such as `main` for production-impacting work. A central workflow change should not silently alter every repository's deployment behavior.

## Inputs And Outputs

Make inputs boring and explicit:

- target environment.
- working directory.
- tool version.
- plan or validation mode.
- artifact retention period.
- whether apply is allowed.
- required approver environment.

Useful outputs include:

- artifact name.
- plan summary.
- image digest.
- rendered manifest path.
- deployment URL.
- verification result.

The caller should not have to parse logs to know what the reusable workflow produced.

## Concurrency Controls

Use concurrency groups for stateful targets:

```yaml
concurrency:
  group: terraform-${{ inputs.environment }}-${{ inputs.working-directory }}
  cancel-in-progress: false
```

For infrastructure, `cancel-in-progress: false` is usually safer. Canceling a plan may be fine; canceling an apply can leave state, locks, or external systems in an unclear state.

## Evidence Retention

Retain artifacts that explain the run:

- command summary.
- tool versions.
- rendered manifests.
- Terraform plan output.
- policy check results.
- test reports.
- deployment or verification summary.

GitHub logs expire and can be noisy. Important review artifacts should be uploaded with clear names and retention settings.

## Failure Model

The common failure is invisible central change:

```text
shared workflow changes on main
-> dozens of repos call it by branch
-> validation behavior changes overnight
-> teams debug local repos while failure lives in shared CI code
```

The operating rule: reusable workflows need versioned contracts, stateful concurrency, and evidence that survives beyond a green check mark.
