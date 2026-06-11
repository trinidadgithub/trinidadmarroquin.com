+++
title = 'Helm And Terraform Boundary On EKS'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for the Terraform-managed Helm release pattern on EKS, keeping infrastructure provisioning separate from application deployment configuration.'
tags = ['terraform', 'helm', 'eks', 'kubernetes', 'cicd']
categories = ['field-notes']
+++

The boundary between Terraform and Helm is a common source of confusion. Terraform provisions infrastructure. Helm deploys applications. Terraform's `helm_release` resource bridges them, but the chart templates stay in the application repository.

For a runnable lab, see the [`helm-terraform-js-app` directory in the IaC repository](https://github.com/trinidadgithub/IaC/tree/main/helm-terraform-js-app).

## The Pattern

Terraform manages the Helm release with `set` blocks that inject environment-specific values:

```hcl
resource "helm_release" "my_app" {
  name       = "my-app"
  chart      = "${path.module}/../helm/myapp"
  namespace  = kubernetes_namespace.my_app.metadata[0].name

  set {
    name  = "image.repository"
    value = var.docker_image_repository
  }

  set {
    name  = "image.tag"
    value = var.docker_image_tag
  }

  set {
    name  = "replicaCount"
    value = var.replica_count
  }
}
```

The Helm chart stays portable. Environment-specific values live in Terraform variables.

## Chart Structure

The Helm chart should follow the standard layout and expose the values Terraform needs to override:

```text
helm/myapp/
  Chart.yaml
  values.yaml
  templates/
    deployment.yaml
    service.yaml
```

`values.yaml` defines defaults:

```yaml
replicaCount: 1
image:
  repository: my-app
  tag: latest
  pullPolicy: Always
service:
  type: ClusterIP
  port: 80
```

The chart does not need to know about environments. Terraform overrides what changes per environment.

## Validation Before Apply

Run `helm template` against the chart to validate it before Terraform applies:

```bash
helm template my-app helm/myapp --values helm/myapp/values.yaml | kubectl apply --dry-run=client -f -
```

This catches syntax errors, missing template variables, and Kubernetes API validation issues before the release is attempted.

## Deployment Pipeline

The lab includes scripts for the full pipeline:

```bash
./docker_build.sh    # build and tag the image
./docker_push.sh     # push to ECR or registry
terraform apply      # create or update the Helm release
```

The pipeline should:

- build and push the image first.
- run `helm template` validation.
- run `terraform plan` and review.
- apply with the new image tag.

## Image Tag Strategy

Pass the image tag as a Terraform variable:

```hcl
variable "docker_image_tag" {
  description = "Docker image tag for the application"
  type        = string
}
```

Each deployment gets a unique tag. Avoid `latest`. Use commit SHAs, semantic versions, or build numbers so every release is identifiable and rollback is unambiguous.

## Acceptance Criteria

- Terraform creates or updates the Helm release without modifying the chart.
- Image tag overrides are injected via `set` blocks.
- `helm template` validation passes before Terraform apply.
- Rollback restores the previous image tag.
- Chart is versioned in the application repository, not the infrastructure repository.
