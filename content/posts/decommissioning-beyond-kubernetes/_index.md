+++
title = 'Decommissioning Beyond Kubernetes'
date = 2026-11-20T00:00:00-06:00
draft = false
description = 'A three-part series on residual storage after Kubernetes decommissioning, snapshot investigation, and evidence-driven cleanup automation.'
+++

Turning off a Kubernetes cluster ends one lifecycle. Storage objects, snapshots, ownership decisions, and capacity accounting still need their own closure.

For the preceding cluster-retirement operation, see [Retiring Rancher-Managed Kubernetes](/posts/retiring-rancher-managed-kubernetes/), covering Rancher cleanup, workload quiescence, storage exceptions, and node shutdown.

This series follows an HPE Nimble cleanup that began with 1,209 array volumes named like Kubernetes PVCs. The investigation moved from offline-volume inventory through controlled deletion, nine online-volume exceptions, and two volumes containing 2,040 snapshots collectively. Along the way, the automation itself became part of the investigation.

Each installment asks a different question: what remained, why it remained, and what evidence supports saying the work is complete?

## Posts in This Series

1. [The Cluster Was Gone. The Storage Wasn't.](/field-notes/the-cluster-was-gone-the-storage-wasnt/) — the operational account: ownership, provisioned size versus reported usage, canary and bulk cleanup, and independent inventory reconciliation.
2. [Two Volumes, 2,040 Snapshots: Following the Metadata](/field-notes/nimble-snapshot-metadata-pre-shrink-investigation/) — the exceptions that led to snapshot metadata describing a pre-shrink purpose, and the boundary between a useful clue and a proven root cause.
3. [The Script Said Success. What Did the Array Say?](/posts/decommissioning-beyond-kubernetes/verified-cleanup/) — the engineering model for cleanup automation: explicit scope, live checks, uncertain outcomes, journals, and unique-object reconciliation.

The first two installments are field notes; the third develops the reusable engineering principles. The original field note keeps its existing URL and serves as Part 1.

## Companion Investigation Toolkit

[Investigating Residual Kubernetes Storage: A Command and Script Index](/field-notes/nimble-storage-investigation-command-index/) indexes the read-only array commands and local evidence-analysis recipes by operational question. It includes a downloadable Python helper for inventory summaries, snapshot timelines, journal analysis, and unique-volume reconciliation.

## The Evidence Behind the Story

The initial cleanup and November 4 two-volume checkpoint are supported by the inventory and journal reconciliation described in Part 1. The later snapshot investigation draws on terminal output preserved in the *Check PVC Volume Status* conversation export. That export ends with an operator report that cleanup was complete, without reproducing the final zero-volume inventory.

The series preserves those distinctions. A provisioned-size reduction is not a physical-space measurement. A missing name is not automatically a deletion by the current run. A snapshot description is not a record of who requested the operation.

Decommissioning is complete when the remaining state has been accounted for, its disposition established, and the evidence distinguishes verified outcomes from reported ones.
