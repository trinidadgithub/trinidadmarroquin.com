+++
title = 'DR Evidence Bundles And Restore Decision Records'
date = 2026-08-23T00:00:00-05:00
draft = false
description = 'Field note for retaining disaster recovery evidence: decision records, backup freshness, restore commands, validation output, redaction boundaries, and post-recovery proof.'
tags = ['disaster-recovery', 'incident-response', 'backup', 'restore', 'operations']
categories = ['field-notes']
+++

Disaster recovery work produces decisions as much as commands. Keep both.

During a real recovery, operators need to know what was restored, from which point, why that point was accepted, who authorized failover, and what proved service recovery. A terminal transcript alone cannot answer those questions.

## Keep The Bundle Shape Predictable

Use a boring bundle structure:

```text
dr-<event>-<date>/
  00-decision-record.md
  01-initial-state.txt
  02-backup-freshness.txt
  03-restore-actions.log
  04-validation-output.txt
  05-open-risks.md
  06-communications.md
```

The exact names are less important than the phase order. A future reviewer should be able to reconstruct the event without reading Slack history.

## Decision Record

The decision record should capture:

- incident or exercise identifier.
- affected site or service tier.
- declaration time.
- failover or restore authority.
- accepted RPO and data-loss statement.
- chosen backup, snapshot, or replica point.
- systems intentionally excluded from recovery.
- rollback or return-to-primary condition.

This is not bureaucracy. It prevents the team from re-litigating the same decision while the clock is running.

## Evidence To Capture

Collect evidence before mutation when possible:

- current health of primary and recovery sites.
- latest backup or snapshot timestamps.
- replication lag or object version evidence.
- DNS and routing state before cutover.
- secrets and identity availability checks.
- restore command output.
- workload readiness and user-path validation.
- monitoring and alert state after recovery.

For Kubernetes, component runbooks such as etcd snapshot restore and Velero workload restore produce part of this evidence. The DR bundle ties those component proofs into the site-level recovery decision.

## Redaction Boundary

DR evidence is sensitive. It can expose topology, hostnames, IP addresses, bucket names, credentials paths, customer names, and recovery weaknesses.

Keep raw evidence in the controlled operations workspace. Redact before copying into tickets, public notes, or vendor cases.

Redact:

- real cluster and site names.
- internal DNS names and IP ranges.
- bucket names and backup repository paths.
- credential or Vault paths.
- customer or tenant identifiers.
- exact firewall or route details unless required for the case.

Do not redact away the operational meaning. Preserve role, phase, timestamp, and outcome.

## Post-Recovery Proof

After recovery, prove the service path:

- users or synthetic checks reach the recovered endpoint.
- data reflects the accepted recovery point.
- writes are either enabled intentionally or blocked intentionally.
- monitoring covers the recovered environment.
- backups resume from the recovered state.
- owners accept remaining risk.

If a service is reachable but backups, monitoring, or ownership are unclear, recovery is not complete. It is only running.

## Failure Model

The quiet failure is undocumented acceptance:

```text
restore works -> service returns -> nobody records recovery point
-> later data question appears -> team cannot prove what was accepted
```

The operating rule: every DR event needs a recoverable service and a recoverable explanation.
