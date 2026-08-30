+++
title = 'Kubernetes Secret Drift Expiry And Evidence'
date = 2026-08-30T00:00:00-05:00
draft = false
description = 'Field note for reviewing Kubernetes Secret drift, expiry, ownership, stale consumers, and rotation evidence without exposing sensitive values.'
tags = ['secrets', 'kubernetes', 'rotation', 'audit', 'operations', 'security']
categories = ['field-notes']
+++

Secret review should answer operational questions without exposing secret values.

The useful evidence is ownership, age, source, consumers, expiry, rollout state, and whether stale credentials still work. Decoding secret data into a ticket or chat channel usually creates a second incident.

## Inventory Without Values

Start with metadata:

```bash
kubectl get secret -A \
  -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,TYPE:.type,AGE:.metadata.creationTimestamp'
```

Then inspect labels and annotations:

```bash
kubectl -n app-ns get secret app-secret -o yaml
```

Review metadata, not `data` values:

- owner label or annotation.
- managed-by label.
- external secret tracking annotation.
- cert-manager annotations.
- Helm release ownership.
- GitOps tracking metadata.
- creation timestamp.
- immutable setting.

## Find Consumers

Before deleting, rotating, or renaming a Secret, find consumers:

```bash
kubectl -n app-ns get deploy,statefulset,daemonset,cronjob -o yaml \
  | grep -n 'secretName\|secretKeyRef'
```

For broader audits, use structured output in a script rather than relying on manual `grep`. The goal is to produce a review list, not raw secret contents.

## Expiry Signals

Kubernetes Secrets do not have a universal expiration field. Expiry may live in:

- a TLS certificate inside `tls.crt`.
- a backend secret manager version or lease.
- an external token provider.
- an annotation maintained by automation.
- an application-specific credential policy.

For TLS Secrets, inspect certificate metadata carefully without publishing the certificate body:

```bash
kubectl -n app-ns get secret tls-secret -o jsonpath='{.data.tls\.crt}' \
  | base64 -d \
  | openssl x509 -noout -subject -issuer -dates
```

For opaque tokens, prefer upstream metadata and audit records instead of printing the token.

## Drift Review

Classify drift before taking action:

- generated Secret from cert-manager.
- target Secret from External Secrets Operator.
- Helm-managed Secret.
- manually created emergency Secret.
- copied Secret from another namespace.
- stale Secret no longer consumed.
- Secret whose source-of-truth is unclear.

The fix depends on the class. Recreating a generated Secret manually can fight the controller. Deleting a stale-looking Secret without consumer review can break the next rollout.

## Evidence Bundle

A safe evidence bundle can include:

```text
secret name and namespace
type
owner metadata
source controller or manager
creation/update timestamp
consumer workloads
rollout timestamp
certificate dates if TLS
backend version or lease ID if available
old credential revocation confirmation
```

It should not include raw values, decoded tokens, private keys, passwords, or screenshots exposing secret material.

## Failure Model

The common failure is value-focused troubleshooting:

```text
app auth fails -> operator decodes Secret into ticket
-> value is stale anyway -> credential leaks into evidence trail
-> rotation must now include the leaked copy
```

The operating rule: collect enough evidence to prove source, freshness, consumers, and rotation result without spreading the secret itself.
