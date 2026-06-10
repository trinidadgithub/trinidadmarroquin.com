+++
title = 'Vault Policy Auth And Secrets Engines'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial standards for Vault policy design, authentication methods, identity mapping, and secrets engine organization.'
tags = ['vault', 'secrets', 'security']
categories = ['projects']
+++

Vault policies are path-based and deny by default. That makes policy design powerful, but it also makes messy path design painful.

Start by organizing secrets engines and paths around ownership and consumption patterns.

## Policy Design

Policies should be small, named clearly, and mapped to roles or groups.

Good policy names describe intent:

```text
team-a-kv-read
platform-transit-admin
ci-prod-db-read
```

Avoid broad wildcard policies unless the path is already tightly scoped.

## Auth Methods

Use auth methods that match the consumer:

- LDAP or OIDC for humans.
- Kubernetes auth for pods.
- AppRole for controlled machine workflows.
- cloud auth methods for provider-native workloads.

Map external identity groups to Vault policies rather than assigning policies one user at a time.

## Secrets Engines

Organize mounts by lifecycle and ownership:

- `kv/` for static secrets with clear owners.
- `database/` for dynamic database credentials.
- `pki/` for certificate issuance.
- `transit/` for cryptographic operations.

Do not mix unrelated teams or environments in the same path if policy boundaries will become confusing.

## Review Checklist

- Does the policy grant only needed capabilities?
- Is `list` safe, or would key names leak sensitive information?
- Are dynamic credentials preferred where practical?
- Are human and machine auth paths separated?
- Is there a revocation path?

## References

- Vault documentation: Policies.
- Vault documentation: Authentication.
- Vault documentation: Secrets Engines.
