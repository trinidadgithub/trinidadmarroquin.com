+++
title = 'AWS Operational Patterns'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'AWS-specific operational patterns for EKS, networking, IAM, IoT, and workstation tooling.'
tags = ['aws', 'cloud', 'eks', 'iam', 'networking']
categories = ['projects']
+++

AWS operations differ from other providers in naming, service boundaries, and tooling defaults. The patterns below capture what is useful to remember without reaching for the console.

## Account Structure

AWS uses accounts as the hard isolation boundary. Use separate accounts for production, non-production, shared services, security, and sandbox. Organization-level SCPs enforce guardrails before IAM comes into play.

Key differences from other clouds:

- account is also a billing boundary.
- some services (CloudTrail, Config) are per-account by default and must be aggregated.
- VPCs are regional, not global.
- IAM roles are global, but trust policies reference specific accounts.

## EKS Cluster Operations

An EKS cluster needs a VPC with at least two subnets in different AZs, an IAM role with `AmazonEKSClusterPolicy`, and a node group with an instance profile. The control plane is managed, but the node group lifecycle and CNI configuration still require operational attention.

Terraform module shape:

```text
module "eks_cluster" {
  source          = "./modules/eks-cluster"
  cluster_name    = var.cluster_name
  subnet_ids      = aws_subnet.private[*].id
  node_instance_type = var.node_instance_type
  desired_capacity   = var.desired_capacity
  min_size           = var.min_size
  max_size           = var.max_size
}
```

Common issues:

- node groups fail to join the cluster if the IAM instance profile role is missing the required trust policy.
- the CNI must be compatible with the instance type and available IP addresses in the subnet.
- cluster endpoint access settings control whether `kubectl` works from outside the VPC.
- version upgrades require a node group replacement or rolling update strategy.

## Application Deployment On EKS

A Node.js or similar application deployed to EKS follows a standard path: containerize with Docker, package as a Helm chart, deploy with Terraform using `helm_release`.

The Helm chart should expose:

- `replicaCount` for scaling.
- `image.repository` and `image.tag` for promotion.
- `service.type` for exposure model (ClusterIP vs LoadBalancer).

Terraform manages the Helm release, but the chart templates stay in the application repository. This keeps deployment configuration with the team that owns the service.

## IoT And Edge

AWS IoT Core uses X.509 certificates for device authentication. A local Docker container with device certificates mounted as volumes can simulate edge workloads during development.

The IoT data path:

```text
device -> MQTT (port 8883) -> AWS IoT Core -> rule action -> downstream service
```

Local labs should use the same certificate paths as production to avoid configuration drift.

## Workstation Tooling

The AWS CLI, Session Manager plugin, and SDKs should be installed through the package manager, not downloaded once and forgotten. Regular updates matter because API versions and signing algorithms change.

Essential tooling:

- AWS CLI v2 with named profiles for each account.
- Session Manager for SSH-less instance access.
- `terraform` with the AWS provider.
- `kubectl` with `aws eks update-kubeconfig`.
- linters: TFLint, Checkov, terrascan.
- `infracost` for cost awareness during planning.

## Observability

CloudWatch is the default log and metric sink, but it is not always the best place to view operational state. Use CloudWatch for retention and alerting, and a separate observability stack (Prometheus + Grafana) for interactive debugging and dashboarding.

Export CloudWatch metrics to Prometheus where cross-service dashboards need them. Do not rely on the CloudWatch console as the primary dashboard for operator response.

## Acceptance Criteria

- Operators can create an EKS cluster with known networking and IAM requirements.
- Helm-deployed applications follow a consistent chart structure.
- IoT device certificates are treated as secrets with rotation expectations.
- Workstation tooling is version-managed and reproducible.
- Observability data flows to the same dashboards used for other providers.
