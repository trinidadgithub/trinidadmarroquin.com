+++
title = 'Rancher Fleet Standards'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Operating standards for Rancher-managed Kubernetes fleets, including Active Directory authentication, break-glass access, RBAC, Fleet GitRepo organization, and cluster ownership.'
tags = ['kubernetes', 'rancher', 'fleet', 'rbac', 'active-directory']
categories = ['projects']
+++

Rancher is useful because it gives operators a single control plane for many Kubernetes clusters. That centralization is also the risk: if access, workspace boundaries, cluster ownership, and GitOps conventions are loose, the management plane becomes another source of drift.

The operating standard should make the boring parts explicit.

## Access Model

Rancher should authenticate normal users through Active Directory. Roles should be assigned to AD groups, not individual users, wherever possible.

This gives the platform team a single place to manage onboarding, offboarding, role changes, and audit expectations. Rancher supports external authentication providers, including Active Directory, and uses users and groups from that provider for authorization decisions.

The default posture should be:

- AD is the source of truth for human access.
- Rancher global admin access is limited to a small platform operations group.
- Cluster and project access is granted through AD groups mapped to Rancher roles.
- Individual user grants are temporary exceptions with an owner and expiration date.
- Access to the Rancher local cluster is restricted to trusted administrators only.

Avoid broad site access. Rancher documents an option to allow any valid user from the external provider, but that is a poor default for production. Use a restricted or authorized-user model so only approved AD groups can log in.

## Break-Glass Access

Keep a local Rancher break-glass account for emergencies.

This is not a convenience account. It exists for cases where AD, SSO, DNS, certificate trust, or the external identity path is unavailable and operators must still recover the platform.

Break-glass expectations:

- one or two local accounts maximum.
- unique long random password stored in the approved emergency secret store.
- MFA if supported by the chosen access path.
- no day-to-day use.
- every login triggers review or an incident note.
- password is rotated after use and on a scheduled cadence.
- account ownership is documented with the platform operations team.

Rancher documentation explicitly notes that local users may be useful for rare circumstances such as external authentication provider outages or maintenance. That matches this model: AD for normal access, local account only for emergency recovery.

## RBAC Shape

Rancher authorization is layered on top of Kubernetes RBAC. Treat Rancher roles as production access controls, not UI preferences.

Use a small role model:

- `platform-admin`: Rancher global administration and local cluster administration.
- `cluster-admin`: administrative access to specific downstream clusters.
- `project-admin`: management of namespaces and applications inside assigned Rancher projects.
- `developer`: workload read/write inside assigned projects, without cluster-level administration.
- `read-only`: observability, troubleshooting, and audit access without mutation.

Prefer group-to-role mapping:

```text
AD group -> Rancher global role, cluster role, or project role -> Kubernetes RBAC enforcement
```

Avoid assigning `cluster-admin` because it is easy. Kubernetes RBAC best practices emphasize least privilege, minimizing wildcard permissions, limiting access to privileged verbs, and treating impersonation, secret access, and workload creation as sensitive capabilities.

## Fleet Workspace Organization

Fleet uses namespaced `GitRepo` resources. Rancher-created Fleet workspaces commonly include `fleet-local` for the local cluster and `fleet-default` for registered downstream clusters.

Use workspace boundaries intentionally:

- `fleet-local` is for Rancher management-plane resources.
- downstream cluster configuration belongs in workspaces that map cleanly to environment, tenant, or platform ownership.
- GitRepos should have narrow paths and explicit targets.
- credentials for private repositories belong in Kubernetes secrets in the same namespace as the `GitRepo`.
- Git credentials, Helm credentials, and sensitive values should not be stored in plain text Git.

Fleet supports `GitRepo` targeting and namespace behavior, but that flexibility can cause damage if the repository scope is too broad. A GitRepo that points at too much of a monorepo or too many clusters makes blast radius hard to reason about.

## Repository Standards

Each Fleet-managed repository should answer five questions quickly:

- Which clusters does this apply to?
- Which team owns the change?
- Which environment receives it first?
- What validates the rendered manifests before merge?
- What is the rollback path?

Recommended repository layout:

```text
clusters/
  prod/
  nonprod/
platform/
  ingress/
  storage/
  monitoring/
apps/
  team-a/
  team-b/
```

Use labels and naming conventions consistently:

```text
environment=prod|nonprod|dev
region=<region>
cluster=<cluster-name>
owner=<team>
tier=platform|application
```

The exact taxonomy can change, but it should be consistent enough that operators can select clusters safely and answer what a bundle affects.

## Cluster Standards

Every Rancher-managed cluster should have a small baseline before application teams depend on it:

- named owner and escalation path.
- Kubernetes version and upgrade policy.
- node pool roles and labels.
- ingress controller expectation.
- default StorageClass expectation.
- backup and restore expectation.
- monitoring and alert routing.
- namespace and project ownership model.
- Pod Security Admission posture.
- NetworkPolicy provider and default stance.

This baseline should be visible in Git or a platform inventory, not only in someone’s memory.

## Operational Checks

Useful periodic checks:

```bash
kubectl get clusters.management.cattle.io
kubectl get gitrepos -A
kubectl get bundles -A
kubectl get bundledeployments -A
kubectl get users.management.cattle.io
kubectl get globalrolebindings.management.cattle.io
```

Review for:

- stale local users.
- direct user role bindings that should be AD group bindings.
- GitRepos without clear ownership.
- bundles stuck in modified or error state.
- clusters missing labels needed for targeting.
- credentials that are not covered by backup or rotation policy.

## Acceptance Criteria

A Rancher-managed fleet is healthy when:

- normal access comes from AD groups.
- the break-glass account exists, is tested, and is not used casually.
- local cluster access is restricted to trusted platform administrators.
- cluster and project roles are understandable without reverse engineering.
- GitRepos have clear ownership, scope, and target clusters.
- sensitive Git or Helm credentials are stored in Kubernetes secrets, not plain text repositories.
- every cluster has a documented baseline and owner.
- Fleet drift and deployment failures are visible to the platform team.

## References

- Rancher documentation: Configuring Authentication.
- Rancher documentation: Managing Role-Based Access Control.
- Fleet documentation: Create a GitRepo Resource.
- Kubernetes documentation: RBAC Good Practices.
