+++
title = 'PostgreSQL Operator Backup And Failover Readiness'
date = 2026-08-25T00:00:00-05:00
draft = false
description = 'Field note for validating PostgreSQL operator readiness in Kubernetes: backups, WAL/archive health, replica lag, failover behavior, client reconnection, and restore proof.'
tags = ['database-operators', 'postgresql', 'kubernetes', 'backup', 'failover', 'operations']
categories = ['field-notes']
+++

PostgreSQL operators make cluster lifecycle easier, but they do not remove the need to prove backup and failover behavior.

A healthy operator can still manage a database whose backups are stale, replicas lag, clients cannot reconnect, or restores have never been tested.

## Backup Readiness

For PostgreSQL, backup readiness has two parts: a base backup and the ability to recover to an accepted point using WAL or the operator's equivalent archive mechanism.

Validate:

- last successful base backup time.
- WAL or archive shipping health.
- backup destination outside the cluster failure domain.
- retention policy and deletion behavior.
- restore credentials separate from normal application credentials.
- alerting when backup or archive status stops advancing.

Do not accept "backup object exists" as proof. The useful proof is a restored database that reaches a known recovery point.

## Replica And Failover Signals

Replica health should be visible before an incident.

Track:

- current primary.
- replica count and readiness.
- replication lag.
- timeline changes.
- synchronous versus asynchronous replication mode.
- failover trigger and promotion policy.
- endpoint or Service used by writers.

Application teams need to know whether failover is automatic, manual, or intentionally disabled for a given environment.

## Client Behavior

PostgreSQL failover is not done when a new primary exists.

Validate the client path:

- write endpoint moves to the new primary.
- DNS or Service selection follows the promoted instance.
- connection pools reconnect without manual pod restarts, or the restart procedure is documented.
- in-flight writes are handled according to the accepted RPO.
- read replicas do not continue serving stale assumptions to applications.

If every application requires a different manual reconnect sequence, the failover plan is incomplete.

## Restore Rehearsal

Run restores into a disposable target.

Capture:

```text
source cluster
backup identifier
target namespace or cluster
requested recovery point
restore start and finish time
database readiness check
application-level validation query
```

The application-level query matters. PostgreSQL accepting connections is weaker than proving the expected database, schema, and recent business row exist.

## Failure Model

The quiet failure is backup confidence without restore evidence:

```text
operator reports backups -> primary fails -> restore begins
-> WAL gap or credential issue appears -> RPO/RTO are missed
```

The operating rule: a PostgreSQL operator is production-ready only when backup freshness, failover behavior, and restore proof are visible before the incident.
