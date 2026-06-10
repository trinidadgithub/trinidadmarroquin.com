+++
title = 'Kubernetes Platform Conventions'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Platform conventions for Kubernetes namespaces, ingress, storage, labels, policies, and ownership patterns that reduce operational drift.'
tags = ['kubernetes', 'platform', 'storage', 'ingress', 'policy']
categories = ['projects']
+++

Kubernetes gives teams enough flexibility to create drift quickly. Platform conventions are the small set of decisions that keep clusters operable when many teams share them.

The goal is not to standardize everything. The goal is to standardize the parts that affect troubleshooting, access, security, cost, and recovery.

## Namespace Ownership

Every namespace should have an owner, purpose, and lifecycle expectation.

Use consistent labels:

```yaml
metadata:
  labels:
    owner: team-platform
    environment: prod
    workload-tier: platform
    data-classification: internal
```

Use annotations for human-facing metadata:

```yaml
metadata:
  annotations:
    owner/contact: platform-ops@example.com
    runbook/url: https://example.com/runbooks/service
    escalation/url: https://example.com/oncall/team-platform
```

Minimum namespace contract:

- named owning team.
- support and escalation path.
- intended environment.
- resource quota expectation.
- default network posture.
- Pod Security Admission level.
- backup expectation for stateful workloads.

## Resource Controls

Namespaces should not be unlimited by default.

Use `ResourceQuota` to prevent one namespace from consuming shared cluster capacity, and use `LimitRange` to provide defaults or bounds where appropriate.

Review:

```bash
kubectl get resourcequota -A
kubectl get limitrange -A
kubectl describe namespace <namespace>
```

Avoid setting defaults so low that teams cargo-cult tiny requests. The point is to make resource ownership visible, not to create noisy throttling incidents.

## Ingress Conventions

Ingress should be boring and predictable.

Define:

- supported ingress class names.
- TLS ownership and certificate issuer expectations.
- DNS naming patterns.
- allowed public versus internal exposure.
- required annotations for timeouts, body size, redirects, or auth integrations.
- where ingress controller logs and metrics are reviewed.

Recommended defaults:

- every production ingress uses TLS.
- hostnames follow environment and ownership naming rules.
- public exposure requires explicit approval.
- ingress class is explicit, not assumed.
- app teams own route intent; platform owns controller behavior.

Useful checks:

```bash
kubectl get ingress -A
kubectl get ingressclass
kubectl describe ingress -n <namespace> <name>
```

## Storage Conventions

Storage drift is expensive to debug. Make the intended storage path explicit.

Define:

- approved StorageClasses.
- default StorageClass policy.
- reclaim policy expectations.
- volume expansion support.
- snapshot and restore expectations.
- which workloads require backup outside Kubernetes.
- node or VM prerequisites for CSI drivers.

For vSphere CSI, worker VMs should meet the CSI prerequisites, including disk UUID visibility where required:

```text
disk.EnableUUID = "TRUE"
```

Useful checks:

```bash
kubectl get storageclass
kubectl get pvc -A -o wide
kubectl get pv -o wide
kubectl get volumeattachments -o wide
```

PVCs should specify the intended class when the default is ambiguous or has changed over the cluster lifetime.

## Policy Conventions

Policy should protect shared infrastructure without surprising application teams.

Baseline policies to define:

- Pod Security Admission labels by namespace type.
- NetworkPolicy default stance.
- image registry allowlist or private registry behavior.
- required workload labels.
- secret handling expectations.
- admission exceptions and ownership.

For Pod Security Admission, namespace labels make the enforcement level visible:

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

Not every namespace can start at `restricted`. Platform namespaces for ingress, CSI, CNI, monitoring, and node agents often need elevated permissions. The convention should document exceptions rather than hide them.

## NetworkPolicy Conventions

NetworkPolicy behavior depends on having a policy-capable CNI. If the CNI does not enforce NetworkPolicy, policy manifests are documentation only.

Define:

- whether default deny is required.
- how namespaces allow DNS.
- how ingress controller traffic reaches workloads.
- how monitoring and logging agents scrape or collect data.
- how cross-namespace service calls are approved.

Useful checks:

```bash
kubectl get networkpolicy -A
kubectl describe networkpolicy -n <namespace> <name>
```

## Labels And Naming

Labels should support operations, not just organization charts.

Recommended common labels:

```text
app.kubernetes.io/name
app.kubernetes.io/instance
app.kubernetes.io/component
app.kubernetes.io/part-of
app.kubernetes.io/managed-by
owner
environment
```

Use labels for selectors and automation. Use annotations for URLs, descriptions, and long-form metadata.

## GitOps Boundary

Platform-owned conventions should live in Git:

- namespace definitions.
- quotas and limit ranges.
- baseline policies.
- ingress controller configuration.
- storage class definitions, when platform-managed.
- monitoring and logging add-ons.

Avoid letting long-lived manual changes become the real standard. If a live patch fixes the platform, the follow-up is to commit the desired state.

## Acceptance Criteria

A cluster has useful platform conventions when:

- every namespace has an owner and support path.
- ingress, DNS, and TLS rules are predictable.
- approved StorageClasses are documented and visible.
- stateful workloads have backup and restore expectations.
- Pod Security Admission levels are labeled and exceptions are intentional.
- NetworkPolicy posture is understood and enforced by the CNI.
- common labels support troubleshooting and ownership.
- GitOps preserves the conventions after sync.

## References

- Kubernetes documentation: Namespaces.
- Kubernetes documentation: Recommended Labels.
- Kubernetes documentation: Ingress and IngressClass.
- Kubernetes documentation: StorageClasses and PersistentVolumes.
- Kubernetes documentation: Pod Security Standards and Pod Security Admission.
- Kubernetes documentation: Network Policies.
