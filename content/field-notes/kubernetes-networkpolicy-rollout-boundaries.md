+++
title = 'Kubernetes NetworkPolicy Rollout Boundaries'
date = 2026-08-28T00:00:00-05:00
draft = false
description = 'Field note for rolling out Kubernetes NetworkPolicy safely with namespace ownership, default deny sequencing, DNS allowances, policy tests, and rollback evidence.'
tags = ['kubernetes-networking', 'networkpolicy', 'kubernetes', 'security', 'operations']
categories = ['field-notes']
+++

NetworkPolicy is production access control. Roll it out like a platform change, not a formatting cleanup.

The risk is not only blocking traffic. The risk is blocking traffic without knowing which dependency the workload actually needed.

## Start With Namespace Ownership

Before applying default deny, confirm:

- namespace owner.
- workload owner.
- expected ingress sources.
- expected egress destinations.
- DNS dependency.
- metrics and log scrape paths.
- admission webhook or sidecar dependencies.
- emergency rollback path.

If the namespace owner cannot name the required network paths, observe first and enforce later.

## Rollout Sequence

A safe sequence is:

```text
inventory -> observe -> allow known dependencies -> apply default deny -> test -> expand
```

Avoid starting with a broad deny in a busy namespace unless the workload has already been modeled. Shared namespaces make this harder because one policy can affect several teams.

## DNS And Platform Allows

Most workloads need DNS before anything else.

Common platform paths to review:

- CoreDNS or node-local DNS.
- kube-apiserver access for controllers.
- metrics scraping.
- log shipping.
- service mesh control plane.
- certificate manager webhooks.
- external secret operators.
- image registry egress during startup, if nodes do not pre-pull.

Do not assume these are all required for every workload. Do confirm which ones will break readiness, rotation, or observability if blocked.

## Test Evidence

Keep a repeatable test pod or job for policy validation:

```bash
kubectl -n app-ns get networkpolicy
kubectl -n app-ns describe networkpolicy <policy>
kubectl -n app-ns run net-test --rm -it --image=curlimages/curl -- sh
```

Validate both sides:

- allowed traffic succeeds.
- denied traffic fails.
- DNS still resolves.
- readiness probes still pass.
- telemetry still reaches the monitoring stack.

Policy is not proven if you only test the happy path.

## Review Policy Shape

Prefer policies that are readable under pressure:

- small selectors.
- named ports where practical.
- clear namespace selectors.
- explicit DNS allowance.
- comments in Git around non-obvious dependencies.
- one policy purpose per manifest where possible.

A policy that only one person can mentally evaluate is risky even if it is technically valid.

## Failure Model

The common failure is default deny without dependency evidence:

```text
default deny merged -> app starts failing health checks
-> DNS or webhook path is blocked -> rollback is unclear
-> teams disable policy instead of fixing ownership
```

The operating rule: NetworkPolicy rollout is complete when allowed paths, denied paths, DNS, observability, and rollback are all tested.
