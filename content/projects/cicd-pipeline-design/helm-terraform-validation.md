+++
title = 'Helm And Terraform Validation Strategy'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Project notes for validating Helm-rendered Kubernetes manifests and Terraform-managed Helm releases before deployment.'
tags = ['cicd', 'helm', 'terraform', 'kubernetes', 'validation']
categories = ['projects']
+++

When Terraform manages Helm releases, validation needs to happen at more than one layer.

Terraform can show that the `helm_release` resource is configured. Helm can render templates. Kubernetes can reject invalid manifests. Production can still fail if the workload has no useful health checks or the image tag points at the wrong build.

## Validation Layers

A practical validation sequence is:

```text
terraform fmt -> terraform validate -> helm lint -> helm template -> kubectl dry-run -> terraform plan
```

Each step answers a different question:

- Terraform validation checks infrastructure syntax and provider configuration.
- Helm lint checks chart structure and template conventions.
- Helm template shows the rendered Kubernetes objects.
- Kubernetes dry-run checks whether the API server accepts the manifests.
- Terraform plan shows what release change Terraform intends to make.

## Review Artifacts

For deployment review, retain:

- rendered manifests.
- values files or explicit `set` overrides.
- Terraform plan output.
- image repository and tag.
- namespace and release name.
- rollback command or previous release reference.

The rendered manifest is especially useful because it removes ambiguity. Reviewers should not have to mentally evaluate templates during an incident or change window.

## Acceptance Criteria

- Chart linting passes.
- Rendered manifests are captured.
- Kubernetes dry-run passes against the intended cluster version when possible.
- Terraform plan is reviewed before apply.
- Image tags are specific enough to audit.
- Rollback path is known before deployment.
