+++
title = 'Secrets Rotation Patterns With Vault'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Operational field note for rotating secrets with HashiCorp Vault, including static secrets, dynamic credentials, PKI, transit keys, leases, rollout safety, and evidence.'
tags = ['vault', 'secrets', 'rotation', 'security', 'operations', 'incident-response']
categories = ['field-notes']
+++

Secret rotation is not one operation.

It is a lifecycle pattern that depends on the secret type, the consumer, the reload behavior, the rollback path, and the evidence the team needs afterward.

Vault helps, but it does not remove the need to design rotation safely.

## Classify The Secret First

Start by identifying what kind of secret is being rotated.

| Secret Type | Rotation Pattern |
|---|---|
| Static KV secret | write new value, roll consumers, verify, remove old value if applicable |
| Dynamic database credential | reduce TTL, revoke leases, let Vault issue new credentials |
| PKI certificate | issue new certificate, reload consumer, verify live certificate |
| Transit key | rotate key version, rewrap or rewrite old ciphertext if needed |
| API token | create replacement, update consumers, revoke old token |
| Kubernetes Secret | update source, sync or rollout consumers, verify pod behavior |

Do not use one generic rotation runbook for every secret type.

## Define Rotation Ownership

Every rotation needs:

- secret owner.
- consumer owner.
- approving authority.
- change window if needed.
- rollback plan.
- verification command.
- evidence location.

Example:

```text
Secret: kv/data/payments/api/database
Owner: payments-platform
Consumers: payment-api deployment
Rotation type: static credential replacement
Verification: application connects with new credential and old credential is rejected
Rollback: restore previous credential only if old credential has not been revoked
```

If the owner and consumer are different teams, coordinate before changing the value.

## Static KV Rotation

Static secrets are simple to store and easy to mishandle.

General flow:

```text
1. Create or obtain replacement secret.
2. Write replacement to Vault.
3. Roll or reload consumers.
4. Verify consumers use the replacement.
5. Revoke or disable old credential at the upstream system.
6. Confirm old credential no longer works.
```

KV v2 write example:

```bash
vault kv put kv/payments/api/database username="payment_api" password="replacement-value"
```

Avoid storing `old_password` and `new_password` together unless a controlled dual-secret migration requires it.

## Dynamic Credential Rotation

Dynamic secrets should rely on leases.

Check leases:

```bash
vault list sys/leases/lookup/database/creds/payment-api
vault lease lookup <lease-id>
```

Revoke a specific lease:

```bash
vault lease revoke <lease-id>
```

Revoke a prefix when intentionally forcing replacement credentials:

```bash
vault lease revoke -prefix database/creds/payment-api
```

Use prefix revocation carefully. It can break every consumer using that role at once.

## PKI Certificate Rotation

Certificate rotation is successful only when the live endpoint presents the new certificate.

Flow:

```text
1. Issue or renew certificate.
2. Deliver it to the consumer.
3. Reload or restart the service if required.
4. Check the presented certificate externally.
5. Revoke old certificate if needed.
6. Confirm expiration alerts are clear.
```

Live check:

```bash
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null
```

Kubernetes object state is not enough. Verify the edge.

## Transit Key Rotation

Transit rotation changes the key version used for new encryption.

```bash
vault write -f transit/keys/customer-profile/rotate
```

Existing ciphertext remains decryptable through older key versions unless policy prevents it.

If old ciphertext should move forward, plan a rewrap migration:

```bash
vault write transit/rewrap/customer-profile ciphertext="vault:v1:..."
```

Do not raise `min_decryption_version` until the team proves old ciphertext no longer depends on that version.

## Kubernetes Consumer Rotation

Kubernetes adds another delivery layer.

Check how the secret reaches the pod:

- Vault Agent file rendering.
- CSI secret mount.
- External Secrets syncing into Kubernetes Secrets.
- application direct Vault calls.
- Helm or pipeline injection.

Each delivery model has different reload behavior.

Review:

- Does the pod need restart?
- Does the application reload files?
- Does the controller sync quickly enough?
- Is secret material copied into etcd?
- Are old pods still running with old values?

For deployments, verify rollout:

```bash
kubectl rollout status deployment/payment-api -n payments
kubectl get pods -n payments -o wide
```

## Rotation Evidence

Capture enough evidence to prove the rotation worked.

Useful evidence:

- Vault path or role, sanitized if needed.
- timestamp of new version or lease.
- consumer rollout timestamp.
- application health after rollout.
- old credential revocation result.
- live certificate check for TLS.
- audit event reference.
- incident or change ticket.

Do not capture raw secret values in evidence bundles.

## Common Failure Modes

### New Secret Written But Consumer Not Reloaded

Vault has the new value, but the application still uses the old value from memory, file cache, or an old pod.

### Old Credential Not Revoked

Rotation reduces little risk if the old credential still works.

### Dynamic Lease Revocation Too Broad

Prefix revocation breaks more workloads than intended.

### Transit Rotation Misunderstood

The key rotates, but stored ciphertext remains on older versions. That may be fine, but it must be understood.

### Evidence Leaks Secrets

Rotation logs, shell history, screenshots, and tickets accidentally include secret values.

## Review Checklist

- Secret type is classified before rotation.
- owner and consumer are known.
- delivery mechanism is documented.
- reload or rollout behavior is tested.
- old credential revocation is part of the plan.
- verification checks prove the consumer uses the new secret.
- evidence excludes raw secret values.
- audit logs can show who rotated or accessed the secret.
- rollback is possible or explicitly not allowed.

## Practical Takeaway

Vault makes rotation easier to control, but the real work is consumer lifecycle.

Successful rotation means the new secret is issued, delivered, consumed, verified, and the old secret is revoked or made irrelevant. Anything less is only a partial rotation.

## References

- [Vault Token Lease Audit And Recovery Practices](/projects/secrets-management-with-vault/token-lease-audit-recovery/)
- [Vault PKI Secrets Engine For Internal Certificates](/field-notes/secrets/vault-pki-secrets-engine-internal-certificates/)
- [Vault Transit Engine For Application Encryption](/field-notes/secrets/vault-transit-engine-application-encryption/)
- [Vault Kubernetes Auth Method Deep Dive](/field-notes/secrets/vault-kubernetes-auth-method-deep-dive/)
