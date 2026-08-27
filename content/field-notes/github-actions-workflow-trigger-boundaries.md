+++
title = 'GitHub Actions Workflow Trigger Boundaries'
date = 2026-08-26T00:00:00-05:00
draft = false
description = 'Field note for designing GitHub Actions workflow triggers with clear pull request, push, tag, schedule, and manual dispatch boundaries.'
tags = ['github-actions', 'cicd', 'automation', 'gitops', 'operations']
categories = ['field-notes']
+++

GitHub Actions makes it easy to run automation on almost every repository event. That convenience is also the failure mode.

A workflow should say what kind of decision it represents: validation, packaging, release, deployment, or scheduled maintenance. Mixing those decisions into one trigger set makes incidents harder to explain.

## Separate Trigger Intent

Use different workflows or clearly separated jobs for different events:

```text
pull_request       -> validate proposed change
push to main       -> build or publish reviewed artifact
tag                -> release or promote immutable version
workflow_dispatch  -> operator-controlled action
schedule           -> maintenance or drift detection
```

Do not let a documentation-only PR, force-push, or branch experiment accidentally run production-impacting automation.

## Pull Request Checks

PR workflows should be safe for untrusted input.

Review:

- whether the workflow runs on `pull_request` or `pull_request_target`.
- whether secrets are available.
- whether generated scripts from the PR are executed.
- whether the job can write to the repository.
- whether artifacts from the PR are trusted by later jobs.

`pull_request_target` is useful for privileged repository automation, but dangerous if it executes code from the incoming branch.

## Push And Tag Boundaries

Push workflows should assume the change has passed review, but that does not automatically mean deployment is safe.

For infrastructure and platform repositories, decide:

- Does `main` only build and validate?
- Do tags promote?
- Are production jobs protected by environments?
- Is manual approval required?
- Are deployments serialized by environment?

The trigger should match the release model. If tags are deployment requests, make tag creation auditable and protected.

## Schedule And Manual Runs

Scheduled workflows are good for drift checks, dependency review, certificate reporting, and stale artifact cleanup. They are poor places for hidden production mutation.

Manual workflows should print their target and inputs before doing work:

```text
environment: prod
cluster: phx-platform-01
action: plan-only
requested-by: github.actor
```

If an operator cannot tell what a `workflow_dispatch` run will change from the run summary, the workflow is too opaque.

## Failure Model

The common failure is an overloaded workflow:

```text
one workflow handles PR, push, tag, and manual deploy
-> conditionals grow
-> privileged job runs on the wrong event
-> cleanup becomes incident response
```

The operating rule: event triggers are part of the control plane. Treat them like production change boundaries, not YAML plumbing.
