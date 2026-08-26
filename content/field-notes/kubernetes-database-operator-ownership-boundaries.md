+++
title = 'Kubernetes Database Operator Ownership Boundaries'
date = 2026-08-25T00:00:00-05:00
draft = false
description = 'Field note for operating PostgreSQL and MySQL database operators in Kubernetes without blurring ownership between the operator, storage, backup tooling, applications, and platform teams.'
tags = ['database-operators', 'kubernetes', 'postgresql', 'mysql', 'platform-engineering', 'operations']
categories = ['field-notes']
+++

A database operator is not a database team in a container.

It can reconcile StatefulSets, users, backups, replicas, failover, and certificates. It cannot decide your recovery objective, storage class risk, schema migration policy, or when data loss is acceptable. Those boundaries need to be explicit before production data lands in the cluster.

## Draw The Ownership Model

Write down what each layer owns:

```text
database operator -> database cluster lifecycle and reconciliation
storage layer      -> persistent volume provisioning and attach/mount behavior
backup system      -> backup storage, retention, and restore mechanics
application team   -> schema migrations, connection behavior, and query load
platform team      -> node capacity, security policy, networking, and observability
data owner         -> RPO/RTO, retention, and data-loss acceptance
```

If every issue is "the operator is broken," the ownership model is not useful enough.

## Operator Scope

Different operators expose different abstractions, but the operational questions are similar:

- Which custom resources define the database cluster?
- Which Kubernetes objects are owned by the operator?
- Which fields are safe to edit directly, if any?
- How does failover happen?
- How are backups scheduled and retained?
- How is restore tested?
- What happens when storage attach, DNS, or node placement fails?

Do not patch generated StatefulSets or Services first. Inspect the custom resource and operator status before changing child objects the controller may overwrite.

## State Is Not Just The PVC

A database workload includes more than a volume:

- primary and replica identity.
- replication slot or binlog state.
- users and privileges.
- secrets and certificates.
- backup metadata.
- connection endpoints.
- schema migration history.
- application connection pool behavior.

Velero can restore Kubernetes objects. CSI can attach volumes. The database operator may reconcile pods back into shape. None of that proves the database is transactionally healthy.

## Pre-Production Checks

Before accepting a database operator as production-ready, prove:

- a new database cluster can be created from declared state.
- backups run on schedule and land outside the cluster failure domain.
- restore has been rehearsed into a disposable namespace or cluster.
- failover behavior is understood and observable.
- application clients can reconnect after primary movement.
- storage class behavior matches the database write profile.
- alerts exist for backup failure, replication lag, disk pressure, and unavailable primaries.

The acceptance test is not "the operator pod is Running." It is "the data service can fail, restore, and be explained."

## Failure Model

The common failure is misplaced trust:

```text
operator installed -> database cluster created -> backups assumed
-> restore not rehearsed -> failure occurs -> operator status is green but data path is unclear
```

The operating rule: the operator owns reconciliation. The platform still owns recovery evidence.
