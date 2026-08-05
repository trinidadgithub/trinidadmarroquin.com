+++
title = 'Vault Kubernetes Auth Method Deep Dive'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Operational field note for Vault Kubernetes auth method design, service account binding, policies, token lifetimes, failure modes, and review checks.'
tags = ['vault', 'kubernetes', 'authentication', 'secrets', 'security', 'platform-engineering', 'operations']
categories = ['field-notes']
+++

Vault Kubernetes auth lets workloads authenticate to Vault using Kubernetes service account identity.

That makes it a powerful bridge between platform identity and secret access. It also means mistakes in service account binding, namespace scoping, policy mapping, or token lifetime can become production secret exposure.

This note focuses on operating the auth method safely.

## The Auth Contract

For every workload using Kubernetes auth, document:

- cluster.
- namespace.
- service account.
- Vault auth mount.
- Vault role.
- attached policies.
- token TTL.
- secret paths allowed.
- owner.

Example:

```text
Cluster: prod-rke2-a
Namespace: payments
Service account: payment-api
Vault auth mount: auth/kubernetes-prod-a
Vault role: payment-api
Policies: payment-api-read
TTL: 1h
Owner: payments-platform
```

If this mapping only exists in a pipeline variable or a Helm value, it will be difficult to review during an incident.

## Configure The Auth Mount

Enable a dedicated mount per trust boundary.

```bash
vault auth enable -path=kubernetes-prod-a kubernetes
```

Configure it with the Kubernetes API endpoint, CA certificate, and token reviewer JWT according to your platform model.

```bash
vault write auth/kubernetes-prod-a/config \
  kubernetes_host="https://kubernetes.default.svc" \
  kubernetes_ca_cert=@ca.crt \
  token_reviewer_jwt="$TOKEN_REVIEWER_JWT"
```

Production platforms often use explicit cluster-specific mounts instead of one generic `auth/kubernetes` mount for every cluster. That makes ownership, audit review, and decommissioning clearer.

## Bind Roles Narrowly

Vault roles should bind to specific service accounts and namespaces.

```bash
vault write auth/kubernetes-prod-a/role/payment-api \
  bound_service_account_names="payment-api" \
  bound_service_account_namespaces="payments" \
  policies="payment-api-read" \
  ttl="1h"
```

Avoid broad bindings like:

```text
bound_service_account_names="*"
bound_service_account_namespaces="*"
```

Wildcard bindings may be useful in tightly controlled automation patterns, but they should be rare, documented, and reviewed.

## Policy Design

The role authenticates the workload. The policy decides what it can read or do.

Example KV read policy:

```hcl
path "kv/data/payments/payment-api/*" {
  capabilities = ["read"]
}
```

Example PKI issuance policy:

```hcl
path "pki_internal/issue/payments-services" {
  capabilities = ["update"]
}
```

Do not map many unrelated service accounts to one broad policy. Policy reuse should follow ownership and data boundaries, not convenience.

## Token Lifetimes

Vault tokens issued through Kubernetes auth should be short-lived enough to reduce exposure but long-lived enough to avoid unnecessary churn.

Review:

- role `ttl`.
- role `max_ttl`.
- workload renewal behavior.
- Vault Agent or sidecar behavior.
- what happens during Vault outage.

Short TTLs require reliable renewal. Long TTLs increase exposure when a workload identity is compromised.

## Delivery Patterns

Common delivery models:

- application calls Vault directly.
- Vault Agent renders secrets to files.
- CSI driver mounts secrets.
- external secret controller syncs secrets into Kubernetes Secrets.

Each model has different risk.

Direct application calls keep Kubernetes Secrets out of the path but add application complexity.

Vault Agent centralizes retrieval and renewal but introduces file permissions and reload behavior.

Syncing into Kubernetes Secrets improves application compatibility but copies secret material into the Kubernetes API and etcd trust boundary.

Pick the model deliberately.

## Operational Checks

List auth mounts:

```bash
vault auth list
```

Read a role:

```bash
vault read auth/kubernetes-prod-a/role/payment-api
```

Check policies:

```bash
vault policy read payment-api-read
```

Review Kubernetes service accounts:

```bash
kubectl get serviceaccount -n payments payment-api -o yaml
```

The Vault role, Kubernetes service account, and deployment manifest should agree.

## Common Failure Modes

### Namespace Wildcards Leak Access

A role allows the same service account name in every namespace. Another team creates a matching service account and receives unintended Vault policy.

### Broad Policy Defeats Narrow Auth

The role is tightly bound, but the attached policy grants access to unrelated paths.

### Token Reviewer Breaks

Kubernetes API, CA, token reviewer JWT, or RBAC changes prevent Vault from validating service account tokens.

### Secret Delivery Copies Data Too Widely

External secret sync writes sensitive data into Kubernetes Secrets across namespaces without clear ownership or cleanup.

### Workload Cannot Renew

The workload receives a token but does not renew it, causing periodic failures that look like application bugs.

## Audit Review

Vault audit logs should identify:

- auth mount.
- role.
- service account identity.
- namespace.
- policy.
- requested secret path.

Use audit review to answer:

```text
Which Kubernetes workload accessed this secret?
Did access come from the expected namespace?
Was the requested path allowed by a narrow policy?
Did a decommissioned service account continue authenticating?
```

## Review Checklist

- Each cluster has an intentional auth mount strategy.
- roles bind to specific service accounts and namespaces.
- wildcard bindings are documented and rare.
- policies match workload ownership.
- token TTL and renewal behavior are tested.
- secret delivery model is documented.
- Kubernetes Secrets are avoided or justified for sensitive material.
- audit logs can tie access back to workload identity.
- decommissioning removes Vault roles and Kubernetes service accounts.

## Practical Takeaway

Vault Kubernetes auth is strongest when service account identity maps to narrow Vault roles and policies.

Treat the mapping as production access control. Review auth mounts, role bindings, policies, token lifetimes, delivery patterns, and audit logs together.

## References

- [Vault PKI Secrets Engine For Internal Certificates](/field-notes/secrets/vault-pki-secrets-engine-internal-certificates/)
- [Secrets Rotation Patterns With Vault](/field-notes/secrets/secrets-rotation-patterns-with-vault/)
- [Kubernetes Maintenance Evidence Bundles](/field-notes/kubernetes-maintenance-evidence-bundles/)
