+++
title = 'Full-Site Disaster Recovery Planning For Platform Teams'
date = 2026-08-23T00:00:00-05:00
draft = false
description = 'Field note for platform disaster recovery planning: service tiers, RTO/RPO ownership, dependency mapping, restore order, failover authority, and proof of recovery.'
tags = ['disaster-recovery', 'platform-engineering', 'kubernetes', 'vsphere', 'operations']
categories = ['field-notes']
+++

A full-site disaster recovery plan is not a backup inventory. It is a decision model for operating when the normal platform boundary is gone.

Backups answer whether data exists somewhere else. DR answers whether the organization can restore service in the right order, with the right authority, inside an agreed failure window.

## Start With Service Tiers

Do not plan every system as if it has the same recovery objective.

Define tiers first:

```text
Tier 0: identity, DNS, network access, secrets, observability control plane
Tier 1: customer-facing or revenue-critical services
Tier 2: internal platform dependencies and batch systems
Tier 3: development, reporting, and rebuildable environments
```

The exact labels do not matter. The ranking does.

Each tier should have:

- service owner.
- RTO and RPO.
- minimum viable restore target.
- hard dependencies.
- validation signal.
- decision owner for failover.

If no one can say which service restores first, the DR plan is not ready.

## Map Dependencies Before The Incident

Full-site recovery fails when hidden dependencies are discovered during restore.

Map dependencies across layers:

- identity and access.
- DNS and certificates.
- network routes, VPNs, firewall rules, and load balancers.
- vCenter, templates, datastores, and backup repositories.
- Kubernetes control planes and etcd snapshots.
- workload backups and persistent volume recovery.
- external APIs, registries, package mirrors, and secret stores.

This map should show restore order, not only architecture. A diagram that looks correct but cannot tell an operator what to restore first is incomplete.

## Define Restore Order

A practical full-site sequence usually looks like this:

```text
declare disaster -> freeze writes where possible
-> prove backup/replica freshness -> restore platform control plane
-> restore identity/secrets/DNS paths -> restore data services
-> restore application workloads -> validate user path
-> communicate steady-state or rollback
```

Component runbooks still matter. The existing etcd and Velero procedures answer specific restore mechanics. The site DR plan decides when those runbooks are invoked and what evidence is required before moving to the next layer.

## Assign Failover Authority

Failover is a business and operations decision, not only a technical step.

Record:

- who can declare a site disaster.
- who can authorize failover.
- who can stop recovery and return to primary.
- who owns external communication.
- who owns data-loss acceptance when RPO is exceeded.

Without those decisions, operators either wait too long or improvise under pressure.

## Validation Criteria

Recovery is not complete when resources exist.

Recovery is complete when the minimum service path is proven:

- identity works for operators and services.
- DNS resolves to the intended recovery endpoint.
- certificates are valid for the recovery path.
- control planes are healthy.
- data restore matches the accepted recovery point.
- application health checks pass from a user-representative network.
- monitoring and paging cover the recovered environment.

Successful object restore is not the same as service recovery.

## Failure Model

The common failure is a plan that is complete on paper but unsequenced:

```text
backups exist -> site fails -> restore starts everywhere
-> dependencies are missing -> teams block each other
-> RTO is missed while the plan is being interpreted
```

The operating rule: a DR plan should tell the next operator what to restore first, what proves it worked, and who can make the next decision.
