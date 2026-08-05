+++
title = 'Vault Transit Engine For Application Encryption'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Operational field note for using Vault transit secrets engine for application encryption, key policy, rotation, auditability, and failure modes.'
tags = ['vault', 'transit', 'encryption', 'secrets', 'security', 'operations']
categories = ['field-notes']
+++

Vault transit gives applications cryptographic operations without handing them raw encryption keys.

That is the main value: applications can encrypt, decrypt, sign, verify, or generate data keys through Vault while key material stays inside Vault's trust boundary.

Transit is not magic encryption. It is an operational contract between the application, Vault, policy, latency, audit logging, and recovery planning.

## Decide What Transit Owns

Start with a clear use case.

Good transit candidates:

- encrypting sensitive fields before database storage.
- signing internal payloads.
- verifying signatures.
- centralizing encryption policy for a service.
- rotating encryption keys without distributing raw key material.

Poor candidates:

- high-volume encryption where every request cannot tolerate a Vault call.
- secrets that should be generated dynamically instead of encrypted at rest.
- data where the application cannot handle Vault unavailability.
- workflows with no owner for key rotation or recovery.

Transit protects keys. It does not remove the need for application design.

## Enable Transit

```bash
vault secrets enable transit
```

Create a key for one service or data boundary:

```bash
vault write -f transit/keys/customer-profile
```

Prefer key names that map to ownership and data purpose, not vague names like `app-key` or `prod-key`.

Example boundary:

```text
Key: customer-profile
Owner: identity-platform
Purpose: encrypt selected profile fields before storage
Consumers: profile-api production workload identity
Rotation cadence: quarterly or after incident review
```

## Policy Boundaries

Applications should receive the minimum transit capabilities they need.

Encrypt-only policy:

```hcl
path "transit/encrypt/customer-profile" {
  capabilities = ["update"]
}
```

Encrypt and decrypt policy:

```hcl
path "transit/encrypt/customer-profile" {
  capabilities = ["update"]
}

path "transit/decrypt/customer-profile" {
  capabilities = ["update"]
}
```

Admin policy for key management should be separate:

```hcl
path "transit/keys/customer-profile" {
  capabilities = ["read", "update"]
}
```

Do not give application workloads key management rights unless that is explicitly part of the design.

## Encrypt And Decrypt Flow

Vault transit expects base64 plaintext for encryption.

```bash
PLAINTEXT=$(printf 'sensitive value' | base64)

vault write transit/encrypt/customer-profile plaintext="$PLAINTEXT"
```

The result is a ciphertext value with Vault metadata:

```text
vault:v1:...
```

Decrypt:

```bash
vault write -field=plaintext transit/decrypt/customer-profile ciphertext="vault:v1:..." | base64 --decode
```

Applications should store the ciphertext, not the plaintext.

## Key Rotation

Transit supports key rotation while preserving decrypt ability for older ciphertext versions.

```bash
vault write -f transit/keys/customer-profile/rotate
```

Review after rotation:

```bash
vault read transit/keys/customer-profile
```

Important settings:

- current key version.
- minimum decryption version.
- minimum encryption version.
- deletion allowance.
- exportability.

Do not raise `min_decryption_version` casually. Old ciphertext may become unreadable if the application still stores data encrypted with older versions.

## Rewrapping Ciphertext

Rewrap updates ciphertext to the latest key version without exposing plaintext to the caller.

```bash
vault write transit/rewrap/customer-profile ciphertext="vault:v1:..."
```

Rewrap is useful when:

- the key has rotated.
- stored ciphertext should be migrated forward.
- applications can process records safely over time.

Plan rewrap like a data migration. It needs retry behavior, metrics, and a way to prove progress.

## Availability And Latency

Transit adds a runtime dependency on Vault.

Before adopting it, decide:

- Can the application fail closed if Vault is unavailable?
- Is local caching allowed?
- What operations need decrypt versus encrypt only?
- What is the acceptable latency budget?
- Does every request call Vault, or only specific write/read paths?

For high-throughput services, measure transit latency under realistic load. Security architecture that breaks service reliability will eventually be bypassed.

## Audit Expectations

Vault audit logs should show:

- auth identity.
- transit path.
- operation type.
- key name.
- source address.
- timestamp.

They should not expose plaintext.

Use audit logs to answer:

```text
Which identity decrypted this data class?
When did key rotation occur?
Which workloads still use old policy paths?
Did a non-application identity attempt decrypt operations?
```

## Common Failure Modes

### One Key For Everything

A single transit key across unrelated services makes ownership, rotation, and incident response harder.

### Application Has Admin Rights

The app should usually encrypt and decrypt, not rotate, delete, export, or change key config.

### Rotation Is Confused With Re-Encryption

Rotating the key changes future encryption. Existing ciphertext remains on older versions until rewrapped or rewritten.

### Vault Latency Is Ignored

Every decrypt call is now part of the application path. Measure it.

### Minimum Decryption Version Breaks Old Data

Raising minimum decryption version can make older ciphertext unreadable.

## Review Checklist

- Each transit key has one clear owner.
- Application policy excludes key administration.
- rotation and rewrap expectations are documented.
- Vault availability behavior is defined.
- latency impact is measured.
- audit logs are enabled and reviewed.
- minimum decryption version changes require explicit approval.
- ciphertext migration has retry and verification behavior.

## Practical Takeaway

Vault transit is a strong pattern when applications need cryptographic operations without managing raw keys.

Operate it like a production dependency: narrow policies, owner-mapped keys, tested rotation, understood rewrap behavior, latency monitoring, and audit review.

## References

- [Vault Policy Auth And Secrets Engines](/projects/secrets-management-with-vault/policy-auth-secrets-engines/)
- [Vault Token Lease Audit And Recovery Practices](/projects/secrets-management-with-vault/token-lease-audit-recovery/)
- [Secrets Rotation Patterns With Vault](/field-notes/secrets-rotation-patterns-with-vault/)
