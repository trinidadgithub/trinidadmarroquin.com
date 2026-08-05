+++
title = 'Vault PKI Secrets Engine For Internal Certificates'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Operational field note for using HashiCorp Vault PKI secrets engine to issue internal certificates with clear roles, TTLs, revocation, and audit boundaries.'
tags = ['vault', 'pki', 'certificates', 'tls', 'secrets', 'security', 'operations']
categories = ['field-notes']
+++

Vault PKI is useful when internal certificate issuance needs policy, auditability, and short-lived credentials instead of manual certificate handling.

It is not just a place to mint certificates. It becomes part of the trust path for services, workloads, operators, and automation.

This note focuses on operating the PKI secrets engine safely for internal certificates.

## Define The PKI Boundary

Start by deciding what this PKI should and should not issue.

Write down:

- issuing use case.
- allowed domains.
- allowed common names.
- allowed subject alternative names.
- maximum TTL.
- renewal expectation.
- revocation process.
- certificate consumer.
- owner of the issuing role.

Example boundary:

```text
PKI mount: pki_internal/
Purpose: internal service TLS
Allowed domains: svc.internal.example, platform.internal.example
Max TTL: 24h for workloads, 720h for platform services
Owner: platform-security
Excluded: public internet certificates, user certificates, unmanaged wildcard issuance
```

If the boundary is unclear, Vault can become a convenient way to create unmanaged trust.

## Root And Intermediate Design

Avoid using a long-lived root directly for day-to-day issuance.

A common pattern is:

```text
offline or tightly controlled root CA
-> Vault intermediate CA
-> short-lived service certificates
```

Operational review questions:

- Where is the root key stored?
- Who can generate or rotate the intermediate?
- How is the intermediate certificate backed up?
- How are CRL and issuing certificate URLs published?
- What happens if the intermediate is compromised?

For lab environments, Vault can generate the root. For production, keep the root decision deliberate and documented.

## Enable And Configure A PKI Mount

Example commands for an internal intermediate mount:

```bash
vault secrets enable -path=pki_internal pki
vault secrets tune -max-lease-ttl=8760h pki_internal
```

Generate an intermediate CSR:

```bash
vault write -format=json pki_internal/intermediate/generate/internal \
  common_name="internal-platform-intermediate" \
  ttl=8760h > intermediate.csr.json
```

Then sign that CSR with the chosen root process and import the signed intermediate:

```bash
vault write pki_internal/intermediate/set-signed certificate=@intermediate.crt
```

The exact signing process depends on whether the root is another Vault mount, an offline CA, or an enterprise CA workflow.

## Configure Issuing URLs And CRL URLs

Certificates should contain reachable URLs for issuer and revocation information.

```bash
vault write pki_internal/config/urls \
  issuing_certificates="https://vault.example.internal/v1/pki_internal/ca" \
  crl_distribution_points="https://vault.example.internal/v1/pki_internal/crl"
```

Use real internal URLs in production. The important part is that clients and operators know where issuer and revocation data live.

## Create Narrow Roles

Roles are the control point for issuance.

Example service role:

```bash
vault write pki_internal/roles/platform-services \
  allowed_domains="svc.internal.example,platform.internal.example" \
  allow_subdomains=true \
  allow_bare_domains=false \
  allow_wildcard_certificates=false \
  max_ttl=24h \
  key_type=rsa \
  key_bits=2048
```

Review role settings carefully:

- `allowed_domains` should be narrow.
- wildcard issuance should be intentional.
- TTL should match consumer reload behavior.
- role names should map to owners or use cases.
- role policies should not be shared across unrelated teams.

The role is where PKI policy becomes enforceable.

## Issue A Certificate

Example:

```bash
vault write pki_internal/issue/platform-services \
  common_name="api.platform.internal.example" \
  alt_names="api.svc.internal.example" \
  ttl=8h
```

For automation, prefer machine identity and narrow policies over human tokens.

The policy should grant only the needed role path:

```hcl
path "pki_internal/issue/platform-services" {
  capabilities = ["update"]
}
```

Do not give broad `pki_internal/*` access to application deployment automation.

## Renewal And Reload

Short-lived certificates reduce long-term exposure, but they require reliable reload behavior.

For each consumer, document:

- how the certificate is requested.
- where it is stored.
- how the process reloads it.
- how renewal failure is detected.
- how much time remains before expiration when alerts fire.

Vault can issue the certificate, but the platform still owns whether the workload uses the new certificate.

For Kubernetes workloads, consider whether cert-manager, Vault Agent, CSI drivers, or external secret controllers are responsible for delivery. Do not mix delivery mechanisms without a clear ownership model.

## Revocation And CRL Operations

Revocation should be tested before it is needed.

```bash
vault write pki_internal/revoke serial_number="39:dd:2e:..."
vault read pki_internal/crl
```

Review:

- how serial numbers are captured.
- who can revoke certificates.
- whether clients check CRLs.
- how CRL size is monitored.
- whether revoked certificates are still accepted by important clients.

If clients do not check revocation data, revocation may be mostly administrative evidence. Know that before relying on it during an incident.

## Audit And Evidence

Vault audit logs should show certificate issuance activity without exposing private key material.

Review audit events for:

- issuing path.
- role name.
- token or entity identity.
- requested common name.
- requested TTL.
- source address.

Do not paste raw audit logs into public notes or tickets without sanitizing hostnames, paths, tokens, and workload identifiers.

## Common Failure Modes

### Role Allows Too Much

A broad role can issue certificates for names outside the intended service boundary.

### TTL Exceeds Consumer Reality

A short TTL is good only if renewal and reload are reliable. A one-hour certificate with no reload path creates outages.

### Intermediate Rotation Is Not Tested

The team can issue certificates but has never rotated the intermediate or verified clients trust the new chain.

### Revocation Is Assumed But Not Enforced

Certificates are revoked in Vault, but clients do not check revocation information.

### Automation Uses Human Tokens

Certificate issuance automation should use workload identity or tightly scoped machine auth, not copied operator tokens.

## Review Checklist

- PKI mount purpose is documented.
- Root and intermediate ownership is clear.
- issuing and CRL URLs are configured.
- roles are narrow and owner-mapped.
- wildcard issuance is disabled unless justified.
- automation policy grants only the required role path.
- renewal and reload behavior is tested.
- revocation workflow is tested.
- audit logs show expected issuance identity.

## Practical Takeaway

Vault PKI is strongest when it issues short-lived certificates through narrow roles with clear ownership.

Do not stop at successful issuance. Operate the full lifecycle: root and intermediate design, role policy, renewal, reload, revocation, audit, and incident evidence.

## References

- [cert-manager Certificate Lifecycle Field Note](/field-notes/cert-manager-certificate-lifecycle/)
- [Vault Policy Auth And Secrets Engines](/projects/secrets-management-with-vault/policy-auth-secrets-engines/)
- [Vault Token Lease Audit And Recovery Practices](/projects/secrets-management-with-vault/token-lease-audit-recovery/)
