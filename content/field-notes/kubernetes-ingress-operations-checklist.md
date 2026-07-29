+++
title = 'Kubernetes Ingress Operations Checklist'
date = 2026-07-28T00:00:00-05:00
draft = false
description = 'A practical Kubernetes ingress operations checklist for DNS, TLS, controller health, routing, observability, and incident response.'
tags = ['kubernetes', 'ingress', 'rke2', 'nginx', 'tls', 'dns', 'platform-engineering', 'operations']
categories = ['field-notes']
+++

Ingress is where Kubernetes platform problems become visible to users.

The application may be healthy, pods may be ready, and services may have endpoints, but a bad ingress change can still break the user path. Treat ingress as a production edge, not just another manifest.

This checklist is for platform teams operating ingress controllers, DNS records, TLS certificates, and application routes across Kubernetes clusters.

## Define The Ingress Contract

Before troubleshooting an ingress issue, write down the expected path.

```text
client
-> DNS
-> load balancer or VIP
-> ingress controller
-> Kubernetes Service
-> endpoint pod
```

For each production hostname, track:

- DNS owner.
- load balancer or VIP owner.
- ingress class.
- namespace.
- Kubernetes Service.
- TLS secret or certificate source.
- application owner.
- rollback path.

If the team cannot name the owner at each layer, ingress incidents will turn into routing debates.

## Pre-Change Checklist

Run this before changing ingress rules, certificates, controller configuration, or load balancer routing.

```bash
kubectl get ingress -A
kubectl get ingressclass
kubectl get svc -A | grep -i ingress
kubectl get pods -A -o wide | grep -i ingress
kubectl get endpoints -A
kubectl get certificaterequests,certificates,orders,challenges -A
```

Confirm:

- target hostname resolves to the expected address.
- ingress object uses the intended `ingressClassName`.
- service selector matches running pods.
- endpoints exist for the service.
- TLS secret exists in the same namespace as the ingress.
- certificate is valid for the hostname.
- controller pods are healthy before the change.
- rollback manifest or previous release is available.

Do not start an ingress change from an unknown baseline.

## DNS Checks

DNS is the first dependency in the user path.

Check resolution from more than one place:

```bash
dig app.example.com
dig app.example.com @1.1.1.1
dig app.example.com @8.8.8.8
```

Confirm:

- record type is expected.
- returned address is the intended load balancer or VIP.
- TTL is appropriate for the change window.
- old records are not still returned by public resolvers.
- split-horizon DNS is understood if internal and external answers differ.

For cutovers, lower TTL before the migration window. Raising TTL after validation is safer than discovering stale resolvers during rollback.

## TLS Checks

TLS failures are often mistaken for application failures.

Check the certificate presented at the edge:

```bash
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null
```

Confirm:

- certificate subject or SAN includes the hostname.
- certificate chain is complete.
- certificate is not expired.
- ingress uses the expected TLS secret.
- cert-manager or external certificate automation owns renewal.
- wildcard certificates are intentionally scoped.

If cert-manager is used, also check the certificate resources:

```bash
kubectl describe certificate -n app-namespace app-example-com
kubectl get secret -n app-namespace app-example-com-tls
```

## Controller Health

Ingress controller health matters before application debugging.

Check controller pods and events:

```bash
kubectl get pods -n ingress-nginx -o wide
kubectl describe pod -n ingress-nginx -l app.kubernetes.io/component=controller
kubectl get events -n ingress-nginx --sort-by=.lastTimestamp
```

Review:

- pod restarts.
- failed readiness or liveness probes.
- config reload errors.
- admission webhook failures.
- resource pressure.
- node placement.
- recent controller upgrades.

If the controller is unhealthy, do not spend the first thirty minutes debugging the application.

## Route Validation

Validate from outside and inside the cluster.

External path:

```bash
curl -vk https://app.example.com/healthz
```

Internal service path:

```bash
kubectl run curl-test --rm -it --image=curlimages/curl --restart=Never -- \
  curl -sv http://app-service.app-namespace.svc.cluster.local:8080/healthz
```

Endpoint path:

```bash
kubectl get endpoints -n app-namespace app-service -o wide
```

If internal service calls work but ingress fails, focus on ingress rules, TLS, controller logs, network policy, or load balancer behavior.

If service calls fail, ingress is only the messenger.

## Observability Panels

Ingress dashboards should show:

- request rate by host.
- status code rate by host and path.
- `4xx` and `5xx` trends.
- latency percentiles.
- controller reload count.
- controller pod restarts.
- upstream response time.
- active connections.
- TLS certificate expiration.

For incident response, keep the first screen focused on user impact and routing health. Detailed controller internals can live lower on the dashboard.

## Common Failure Modes

### Wrong Ingress Class

The ingress object may be valid but ignored by the intended controller.

Check:

```bash
kubectl get ingress -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,CLASS:.spec.ingressClassName,HOSTS:.spec.rules[*].host
```

### Missing Endpoints

The ingress routes to a service with no ready endpoints.

Check selectors and pod readiness before changing ingress again.

### TLS Secret In Wrong Namespace

Ingress TLS secrets are namespace-scoped. A valid secret in another namespace does not help the current ingress.

### DNS Points To Old Edge

The Kubernetes objects may be correct while DNS still points to the previous load balancer.

### Controller Reload Failed

Ingress controllers can reject or fail to apply generated configuration. Check controller logs when symptoms do not match the manifest.

### NetworkPolicy Blocks The Controller

If NetworkPolicy is enforced, ingress controller pods need allowed paths to application pods. A route can be correct and still blocked.

## Rollback Checks

A rollback is not complete until the user path is verified.

After rollback, confirm:

- DNS resolves to the intended address.
- TLS certificate is valid.
- ingress controller accepted the configuration.
- service has ready endpoints.
- external `curl` succeeds.
- error rate returned to baseline.
- latency returned to baseline.
- customer-facing checks pass.

Do not declare recovery from Kubernetes object state alone.

## Review Questions

Use these during ingress design or post-incident review:

```text
Can the team identify the ingress owner in under one minute?
Is DNS ownership documented?
Are certificate renewal and expiration alerts in place?
Does each production ingress specify an ingress class?
Can the team validate external, service, and endpoint paths separately?
Are ingress controller logs and metrics available during incidents?
Is rollback tested for DNS and TLS, not only manifests?
```

## Practical Takeaway

Ingress operations are edge operations.

Treat DNS, TLS, controller health, service endpoints, and observability as one user path. A clean Kubernetes manifest is not enough. The only successful ingress change is one that preserves or restores the route users actually take.

## References

- [Concourse Ingress DNS And TLS Cutover](/field-notes/concourse-ingress-dns-tls-cutover/)
- [Network Saturation Evidence Checklist](/field-notes/network-saturation-evidence-checklist/)
- [cert-manager Certificate Lifecycle Field Note](/field-notes/cert-manager-certificate-lifecycle/)
