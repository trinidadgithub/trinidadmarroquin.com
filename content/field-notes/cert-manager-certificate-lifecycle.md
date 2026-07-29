+++
title = 'cert-manager Certificate Lifecycle Field Note'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'Operational field note for managing Kubernetes certificate lifecycle with cert-manager, including issuers, renewals, ACME challenges, alerts, and failure modes.'
tags = ['kubernetes', 'cert-manager', 'tls', 'certificates', 'acme', 'letsencrypt', 'platform-engineering', 'operations']
categories = ['field-notes']
+++

Certificate automation is not finished when the first certificate is issued.

The operational work is the lifecycle: issuer health, renewal timing, DNS or HTTP challenge reliability, secret ownership, expiration alerts, and safe rotation.

This field note focuses on cert-manager as a Kubernetes platform component, not just as an application dependency.

## Define Certificate Ownership

Every production certificate should have a clear owner.

Track:

- hostname.
- namespace.
- owning application or platform team.
- `Certificate` resource name.
- `Issuer` or `ClusterIssuer`.
- challenge type.
- backing secret.
- renewal policy.
- alert route.

If a certificate expires and nobody knows who owns it, the platform has an ownership problem, not only a TLS problem.

## Resource Model

cert-manager usually flows through these resources:

```text
Certificate
-> CertificateRequest
-> Order
-> Challenge
-> Secret
```

Useful checks:

```bash
kubectl get clusterissuer,issuer -A
kubectl get certificates -A
kubectl get certificaterequests -A
kubectl get orders,challenges -A
kubectl get secrets -A --field-selector type=kubernetes.io/tls
```

When troubleshooting, avoid looking only at the final secret. The failed state is often visible in `CertificateRequest`, `Order`, or `Challenge`.

## Issuer Health

Check issuer readiness before blaming an application ingress.

```bash
kubectl describe clusterissuer letsencrypt-prod
kubectl describe issuer -n app-namespace app-issuer
```

Confirm:

- issuer is `Ready=True`.
- ACME account registration succeeded.
- referenced secrets exist.
- DNS provider credentials are valid for DNS-01.
- ingress class or solver path is correct for HTTP-01.
- staging and production issuers are not confused.

Use Let's Encrypt staging for testing. Production rate limits are not a validation tool.

## Renewal Windows

Certificate renewal should be boring.

Review:

- certificate duration.
- `renewBefore` setting.
- alert threshold.
- owner notification path.
- rollback plan if renewal fails.

Example certificate shape:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: app-example-com
  namespace: app-namespace
spec:
  secretName: app-example-com-tls
  dnsNames:
    - app.example.com
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  duration: 2160h
  renewBefore: 360h
```

Do not set renewal so close to expiration that one bad DNS provider outage creates an emergency.

## ACME Challenge Checks

For HTTP-01, confirm:

- public DNS points to the ingress edge.
- port `80` is reachable from the internet.
- solver ingress uses the correct ingress class.
- redirects do not break the challenge path.
- NetworkPolicy does not block the solver pod.

For DNS-01, confirm:

- DNS provider credentials are valid.
- credentials can write the required zone.
- delegated zones are understood.
- propagation time is accounted for.
- stale TXT records are not confusing validation.

Useful commands:

```bash
kubectl describe challenge -A
kubectl describe order -A
dig TXT _acme-challenge.app.example.com
```

## Secret Rotation

Applications consume the generated TLS secret in different ways.

Ingress controllers usually reload automatically. Some workloads mount certificates directly and may need restart or reload behavior.

Review:

- which pods consume the secret.
- whether the controller reloads on secret update.
- whether application pods need restart.
- whether old certificates remain cached by external load balancers.
- whether monitoring confirms the presented certificate changed.

Check the live certificate, not only the Kubernetes secret:

```bash
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null
```

## Expiration Alerting

Expiration alerts should page early enough to fix the cause during business hours.

Alert on:

- certificate expiration within warning window.
- certificate expiration within critical window.
- `Certificate` not ready.
- failed ACME challenge.
- issuer not ready.
- cert-manager controller errors.

The alert should include hostname, namespace, certificate name, issuer, and owner.

An alert that says "certificate expiring" without ownership is a scavenger hunt.

## Common Failure Modes

### Wrong Issuer

A certificate references staging instead of production, or a namespace issuer that no longer exists.

### HTTP-01 Solver Not Reachable

The solver pod exists, but DNS, ingress class, redirects, firewall policy, or network policy prevents validation.

### DNS-01 Credentials Too Narrow

The secret exists, but the DNS token cannot modify the required zone.

### Secret Name Collision

Two certificates or workloads expect different certificates in the same secret name. Keep naming deliberate.

### Wildcard Scope Drift

Wildcard certificates are convenient but can hide ownership. Document who owns the wildcard and which services depend on it.

### Renewal Succeeds But Edge Still Presents Old Cert

The Kubernetes secret updated, but the ingress controller, external load balancer, or application process did not reload.

## Review Checklist

Use this checklist before considering certificate lifecycle healthy:

- Every production certificate has an owner.
- Issuers are ready and monitored.
- ACME challenge type is documented.
- Renewal happens well before expiration.
- Expiration alerts include hostname, namespace, secret, and owner.
- Presented certificates are checked from outside the cluster.
- Secret consumers are known.
- Wildcard certificate scope is reviewed.
- Production issuers are not used for repeated testing.

## Practical Takeaway

cert-manager automates certificate issuance, but the platform team still owns lifecycle reliability.

Monitor the issuer, the challenge path, the renewal window, the secret, and the certificate actually presented to users. TLS is only healthy when the live edge presents the expected certificate and the team knows who owns the next renewal.

## References

- [Kubernetes Ingress Operations Checklist](/field-notes/kubernetes-ingress-operations-checklist/)
- [Concourse Ingress DNS And TLS Cutover](/field-notes/concourse-ingress-dns-tls-cutover/)
