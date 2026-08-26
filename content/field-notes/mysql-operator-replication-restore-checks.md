+++
title = 'MySQL Operator Replication And Restore Checks'
date = 2026-08-25T00:00:00-05:00
draft = false
description = 'Field note for operating MySQL database operators in Kubernetes: replication topology, backup consistency, restore rehearsals, binlog assumptions, and application cutover validation.'
tags = ['database-operators', 'mysql', 'kubernetes', 'replication', 'restore', 'operations']
categories = ['field-notes']
+++

MySQL operators can hide a lot of useful machinery behind a simple custom resource. That is convenient until replication or restore becomes an incident.

The operating goal is not just a Running primary. It is a database service whose replication, backup, and restore behavior are understood before the outage.

## Know The Topology

Before trusting the operator, record the topology it creates:

- primary instance.
- replica instances.
- writer endpoint.
- reader endpoint, if used.
- replication mode.
- binlog retention or archive behavior.
- backup schedule and target.
- failover policy.

The topology should be visible to operators without reading the operator source code.

## Replication Checks

Replication health is not only pod readiness.

Review:

- replica lag.
- replication thread status.
- binlog position or GTID progress where applicable.
- whether replicas can be promoted.
- whether read traffic tolerates lag.
- whether backups run from primary or replica.

A replica can be Ready and still be unsafe as a recovery target if lag, errors, or binlog retention are unknown.

## Backup Consistency

MySQL backup checks should answer:

- Was the backup transactionally consistent for the engine and workload?
- Was it coordinated with replication state?
- Does the backup include users, grants, routines, and required metadata?
- Is the backup stored outside the cluster failure domain?
- Can restore credentials access the target?
- Does retention satisfy the data owner's RPO?

If the operator abstracts the backup job, inspect the resulting status and retained artifacts anyway. Abstraction is not evidence.

## Restore And Cutover

Restore rehearsal should prove more than object creation.

Record:

```text
backup ID
restore target
replication or binlog point
schema/version check
application validation query
writer endpoint after cutover
rollback decision
```

After restore, validate the application path. Some applications cache writer endpoints, hold stale connections, or require a controlled restart after database failover.

## Failure Model

The common failure is treating MySQL replication as a black box:

```text
operator deploys replicas -> primary fails -> promotion happens
-> app writes hit wrong endpoint or stale state -> recovery becomes data triage
```

The operating rule: if the operator owns MySQL orchestration, the platform must still own topology evidence, restore proof, and application cutover validation.
