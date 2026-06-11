+++
title = 'GitOps For Infrastructure Teams'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Project page for GitOps patterns applied to infrastructure operations: pipeline-controlled infrastructure, platform tenant workflows, fleet-wide change orchestration, and the operating model that makes GitOps practical for platform teams.'
tags = ['gitops', 'cicd', 'concourse', 'infrastructure', 'platform']
categories = ['projects']
+++

GitOps for a platform team is not about syncing a Kubernetes manifest directory. It is about making Git the source of truth for infrastructure state and using pipelines to enforce that state across environments, sites, and provider boundaries.

This page collects patterns, pipeline shapes, and operating model decisions for GitOps in infrastructure teams.

## Scope

These patterns apply to:

- Multi-site RKE2 cluster fleets.
- vSphere and cloud provider resource lifecycle.
- Template and image pipeline workflows.
- Platform tenant onboarding.
- Secrets and certificate lifecycle management.
- Configuration drift detection and remediation.

The common thread is that Git is the single entry point for change, and pipelines are the only path to production.

## Pipeline Shapes

### Infrastructure Change Pipeline

The standard promotion path for infrastructure repositories:

```text
pull request → lint → validate → plan → plan review → apply (non-prod) → apply (prod) → verify
```

Key properties:

- Plan output is retained as a pipeline artifact.
- Apply stages are serialized per environment backend.
- Verification runs after apply and fails the job if the declared state does not match the target.

### Fleet-Wide Change Pipeline

For changes that must roll across multiple data centers (image updates, configuration baseline changes, credential rotations):

```text
pipeline triggers → per-site jobs (parallel or serial) → per-site verification → aggregate summary
```

Each site job runs independently and can be retried without rerunning completed sites.

### Platform Tenant Pipeline

For onboarding a new cluster, environment, or project:

```text
tenant request (PR) → validate tenant manifest → generate resources → apply → notify tenant
```

The tenant manifest is a declarative document (YAML or HCL) that captures the tenant's requirements. The pipeline translates it into platform resources.

## Operating Model

### Git As The Entry Point

Every infrastructure change starts with a pull request. There is no SSH + ad-hoc change path for platform state. This includes:

- Cluster node configuration.
- Pipeline configuration and secrets binding.
- Image template versions.
- DNS and load balancer configuration.
- Monitoring and alerting rules.

### Pipelines Are The Only Author

No human runs `terraform apply` or `ansible-playbook` directly against production. The pipeline is the only entity with credentials to apply changes.

This means:

- Pipeline credentials are scoped per environment.
- Apply jobs require an explicit approval gate for production.
- Rollback is a Git revert followed by a pipeline run.

### State Is In Git, Not In A Backend

Terraform state files, Ansible inventory, and configuration registries are treated as artifacts derived from Git. If the Git repo is lost, the ability to manage infrastructure is lost. Backup and disaster recovery procedures must account for the Git repository first, not the remote state backend.

## Repository Structure

A common pattern for infrastructure GitOps:

```text
infra-repo/
├── environments/
│   ├── dev/
│   ├── uat/
│   └── prod/
├── modules/
│   ├── terraform/
│   ├── ansible/
│   └── helm/
├── pipelines/
│   ├── change-pipeline.yml
│   └── fleet-rollout.yml
└── tenants/
    └── team-a-cluster.yml
```

Environments are self-contained roots with their own backend configuration and variable files. Modules are shared and versioned through the repo, not through a separate registry.

## Key Differences From Application GitOps

| Aspect | Application GitOps | Infrastructure GitOps |
|---|---|---|
| State backend | Manifests in repo | Terraform state, inventory, secrets |
| Apply frequency | Continuous sync | Gated per change |
| Rollback | Revert manifest | Revert + reapply, may need manual cleanup |
| Secrets | External sealed/secrets store | Pipeline-bound, never in repo |
| Target | Kubernetes cluster | Clusters, vSphere, cloud APIs, DNS |
| Blast radius | Namespace or app | Environment, site, or fleet |

## Acceptance Criteria

- Every production change is traceable to a Git commit.
- Pipelines are the only path to apply infrastructure changes.
- Plan output is reviewed before apply.
- Rollback is a documented and practiced procedure.
- Fleet-wide changes can be scoped, serialized, and retried per site.
- New sites or tenants can be onboarded through a pull request.
