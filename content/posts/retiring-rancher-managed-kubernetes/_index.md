+++
title = 'Retiring Rancher-Managed Kubernetes'
date = 2026-11-21T00:00:00-06:00
draft = false
description = 'A four-part series on Rancher registration, admission-blocked cleanup, workload reconciliation, CSI exceptions, and dependency-ordered RKE2 retirement.'
+++

A replacement cluster can be ready while its predecessor still owns storage, advertises endpoints, runs controllers, and depends on a management proxy for operator access. Retirement means unwinding those relationships deliberately.

This series follows two legacy RKE2 environments registered with Rancher. The UAT inventory contained 19 Kubernetes nodes, including three dedicated etcd members; production contained 18 nodes, including five etcd members. Their shutdown principles were similar. Their storage exceptions and access sequence were not.

The recurring question is: **which control loop or verification path do we still need alive?**

## Posts in This Series

1. [Shutting Down Kubernetes Is Not the Same as Decommissioning It](/field-notes/rancher-rke2-decommissioning-field-note/) — the existing operational overview, updated with the complete export's final operator report.
2. [The Cluster Was Unregistered. The Agents Were Still Running.](/posts/retiring-rancher-managed-kubernetes/management-cleanup/) — lifecycle ownership, direct access, and the admission policy that prevented Rancher's cleanup pod from starting.
3. [Zero Replicas Is Not a Shutdown Plan](/posts/retiring-rancher-managed-kubernetes/reconciliation-and-storage/) — operator-owned workloads, returning replica counts, retained claims, and three storage attachments that remained exceptions.
4. [Keep the API Until Its Last Useful Check](/posts/retiring-rancher-managed-kubernetes/shutdown-and-handoff/) — recovery material, endpoint boundaries, guest runtime checks, quorum, VM inventory, and the handoff after Kubernetes is gone.

## Companion Investigation Toolkit

[Rancher Retirement: An Investigation Command Index](/field-notes/rancher-retirement-investigation-command-index/) provides read-only recipes organized by operational question. It includes a downloadable local `jq` report joining Pods, PVCs, PVs, and VolumeAttachments while preserving missing mappings and unknown attachment status.

**[Download storage-map.jq](/field-notes/rancher-retirement-investigation-command-index/storage-map.jq)** · [Usage instructions](/field-notes/rancher-retirement-investigation-command-index/#7-build-the-storage-map)

The existing [decommissioning runbook](https://github.com/trinidadgithub/trinidadmarroquin.com/blob/main/notes/rancher-rke2-decommissioning-runbook.md) remains the phase-oriented procedure. The command index is the investigation reference; the installments explain the decisions behind it.

## Evidence Map

The primary source is the complete JSON conversation export titled *Rancher Cluster Decommission Guide*. It contains 275 indexed messages, including assistant summaries and internal export placeholders. The table below refers to the numbered user messages containing observations or explicit operator reports, not assistant declarations of success.

| Topic | Message numbers | Evidence boundary |
| --- | --- | --- |
| Ownership and direct UAT access | 20, 24, 28 | Sparse provisioning spec, one node's service state, direct API node listing |
| UAT cleanup admission and completion checks | 60, 64, 68, 79, 83 | Job denial, absent namespace enforcement label, pod progress, downstream checks, label restoration |
| Workload ownership and UAT storage | 95, 100, 153, 156 | Custom-resource owners, seven StatefulSets at zero, no listed attachments, Grafana desired-state return |
| Guest runtime and retirement scope | 125, 130, 135, 159, 162, 165 | Failed service state, residual runtime, cleanup output, non-node load balancers, shutdown report |
| Production recovery and access | 187, 190, 196, 199, 202, 205, 211 | Snapshot/token transfer checks, upgrade controller, registration report, direct access established afterward |
| Production cleanup | 217, 220, 223, 226 | Repeated admission rejection, still-running agents, later absence checks and enforcement-label restoration |
| Production exceptions and closure | 235, 238, 241, 244, 253, 256, 259, 262, 265, 268 | Endpoint and replica checks, three attached volumes, old deletion timestamps, shutdown and VM-deletion reports |

The export references screenshots by attachment identifiers; the JSON does not supply their pixels. No complete final vCenter export, restore rehearsal, or array-side resolution of the three attachments is reproduced. The final user report confirms etcd power-off and remaining VM deletion, with Nimble storage cleanup still outstanding at that point.

## The Next Chapter

The storage handoff becomes [Decommissioning Beyond Kubernetes](/posts/decommissioning-beyond-kubernetes/): residual volumes, snapshot investigation, and independently checked cleanup results. The two series cover adjacent lifecycle stages. A cluster shutdown report does not itself settle the storage disposition.
