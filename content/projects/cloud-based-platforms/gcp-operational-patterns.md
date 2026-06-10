+++
title = 'GCP Operational Patterns'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'GCP-specific operational patterns for project structure, GKE, IAM, networking, and SRE discipline.'
tags = ['gcp', 'cloud', 'gke', 'iam', 'networking']
categories = ['projects']
+++

GCP organizes resources into projects, which are lighter and more numerous than AWS accounts. This changes how isolation, IAM, and networking are approached.

## Project Structure

A GCP project is the primary boundary for resources, IAM, and billing. Use separate projects for production, non-production, shared services, and sandbox work.

Key differences from other providers:

- projects belong to a hierarchy: organization -> folder -> project.
- IAM policies are inherited from parent nodes in the hierarchy.
- service accounts are project-scoped but can be shared across projects.
- VPCs are global, not regional.
- projects have a quota and API enablement surface that must be managed.

## GKE Cluster Operations

GKE offers three modes: Autopilot, Standard (regional), and Standard (zonal). Regional clusters are the recommended default for production because the control plane and nodes are replicated across zones.

Essential checks during GKE provisioning:

- the cluster is regional, not zonal.
- the node pool uses a stable channel and a supported Kubernetes minor version.
- Workload Identity is enabled for pod-to-GCP authentication.
- VPC-native (alias IP) is enabled for pod networking.
- private cluster is enabled for control plane access.

Common failure patterns:

- node auto-upgrade can break compatibility with custom daemonsets or node-level configuration.
- Workload Identity requires both the GKE metadata server and the IAM binding between the Kubernetes service account and the Google service account.
- IP address exhaustion in the pod CIDR range causes scheduling failures.
- regional clusters are more expensive but survive zone failures without manual intervention.

## IAM And Service Accounts

GCP IAM uses roles (primitive, predefined, custom) attached to principals. Service accounts are the identity for workloads, not humans.

Patterns:

- one service account per microservice, not one shared service account per project.
- use Workload Identity on GKE instead of mounting service account keys.
- use the Secret Manager or a Vault integration for service account keys that must run outside GCP.
- audit IAM using the Policy Analyzer, not ad hoc scripts.

Cloud IAM conditionals can restrict access by resource, IP range, or time, reducing the need for separate projects for fine-grained access control.

## Networking

GCP VPCs are global. A single VPC can span regions, which simplifies hub-and-spoke designs but requires careful CIDR planning.

Key networking expectations:

- VPC firewall rules are evaluated in order, with an implicit deny at the end.
- Cloud NAT is required for private instances to reach the internet.
- Private Google Access allows on-premises and VM-based access to Google APIs without public IPs.
- Shared VPC lets the host project own the network while service projects consume subnets.

## SRE Discipline On GCP

Google Cloud publishes SRE resources that map directly to operational maturity. The Google Cloud Architecture Framework covers design, security, privacy, reliability, cost optimization, performance, operations, and sustainability.

Useful GCP-native observability tools:

- Cloud Monitoring for metrics and alerting.
- Cloud Logging for log aggregation and querying (Logging Query Language).
- Error Reporting for application error aggregation.
- Cloud Trace for distributed tracing.

For multi-cloud teams, use a consistent observability stack (Prometheus + Grafana) across all providers and treat Cloud Monitoring as a backup sink, not the primary dashboard.

## Quota And Capacity

GCP projects have per-service quotas that are not always obvious until a deployment fails.

Check before expanding infrastructure:

- compute engine API capacity in the target region.
- static IP address quota.
- GKE cluster and node pool quota.
- Cloud Load Balancing forwarding rules.

Quota increases require a support ticket and should be requested before the capacity is needed.

## Acceptance Criteria

- Project hierarchy matches team and environment ownership.
- GKE clusters are regional with Workload Identity and VPC-native networking.
- Service account keys are not used where Workload Identity can replace them.
- VPC design accounts for the global scope and firewall evaluation order.
- Quota monitoring is in place before production deployment.
