+++
title = 'Kubernetes Egress Control Operating Model'
date = 2026-08-28T00:00:00-05:00
draft = false
description = 'Field note for designing Kubernetes egress controls with ownership for DNS, NAT, proxies, network policy, allowlists, observability, and incident exceptions.'
tags = ['kubernetes-networking', 'egress', 'networkpolicy', 'kubernetes', 'security', 'operations']
categories = ['field-notes']
+++

Egress control is where platform security, application dependencies, DNS, and network operations collide.

The goal is not simply to block outbound traffic. The goal is to make allowed outbound paths reviewable, observable, and recoverable when a dependency changes.

## Define The Egress Path

For each cluster, document the path:

```text
pod -> CNI policy -> node routing -> NAT gateway or firewall -> proxy, if used -> external service
```

Track ownership for:

- DNS resolution.
- Kubernetes NetworkPolicy or CNI-specific policy.
- node route tables.
- NAT gateway or firewall rule.
- HTTP proxy configuration.
- external service allowlist.
- audit logs.

If the team cannot tell where a denied connection was blocked, troubleshooting becomes guesswork.

## Egress Inventory

Build an inventory before enforcement:

- container registries.
- package mirrors.
- cloud APIs.
- identity providers.
- certificate authorities and OCSP endpoints.
- SaaS dependencies.
- backup targets.
- observability endpoints.
- webhook receivers.

Separate startup dependencies from steady-state dependencies. A workload may only need registry or package access at rollout time, while cloud APIs or SaaS endpoints are used continuously.

## DNS Is Part Of Egress

Do not write egress policy without a DNS decision.

Confirm:

- which resolver pods use.
- whether node-local DNS is present.
- whether FQDN policy is supported by the CNI.
- how DNS cache behavior affects policy changes.
- whether split-horizon DNS changes the target address.

IP allowlists are brittle when the dependency is a cloud service with changing addresses. FQDN-aware policy helps only if the platform understands its limitations and failure modes.

## Exception Handling

Create an exception workflow before enforcement:

```text
request -> owner review -> allowed destination -> expiration -> monitoring -> removal
```

Every exception should include:

- requesting team.
- destination hostname or network.
- business reason.
- environment.
- expiration or review date.
- evidence that traffic is still needed.

Permanent emergency exceptions become the real policy if they are never reviewed.

## Observability

Egress controls need visibility:

- denied connection count.
- source namespace and workload.
- destination hostname or IP.
- policy that denied traffic.
- firewall or proxy decision logs.
- top talkers by namespace.
- stale allowlist entries.

This evidence prevents every outage from becoming "the network is blocking us" without proof.

## Failure Model

The common failure is enforcing egress before dependency ownership exists:

```text
deny-by-default enabled -> app cannot reach identity provider
-> no one owns the allowlist -> broad exception added
-> egress policy exists but does not reduce risk
```

The operating rule: egress control is useful only when allowed paths, exceptions, DNS behavior, and denial evidence are operationally visible.
