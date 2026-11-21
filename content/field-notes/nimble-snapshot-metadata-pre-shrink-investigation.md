+++
title = 'Two Volumes, 2,040 Snapshots: Following the Metadata'
date = 2026-11-20T00:00:00-06:00
draft = false
description = 'Part 2 of Decommissioning Beyond Kubernetes: investigating 1,020 snapshots on each of two HPE Nimble volumes and separating pre-shrink metadata from root-cause attribution.'
tags = ['kubernetes', 'hpe', 'nimble', 'storage', 'csi', 'snapshots', 'decommissioning', 'operations']
categories = ['field-notes']
series = ['Decommissioning Beyond Kubernetes']
+++

Part 2 of [Decommissioning Beyond Kubernetes](/posts/decommissioning-beyond-kubernetes/).

After the main cleanup, the array inventory had narrowed from 1,209 PVC-named volumes to two. Both were offline. Neither had active connections. Each had 1,020 snapshots.

Those two volumes had been excluded deliberately. The original cleanup process required zero snapshots; changing that condition just to finish the list would have erased the distinction that made the exception useful.

[Part 1](/field-notes/the-cluster-was-gone-the-storage-wasnt/) explains the volume cleanup and unique-name reconciliation. This investigation began with the remaining question: what were those snapshots?

## Equal Counts Were a Clue

The parent-volume information showed the following state. Names are replaced with aliases here; the values are from the recorded output.

| Property | Volume A | Volume B |
| --- | ---: | ---: |
| Provisioned size | 19,073 MiB | 19,073 MiB |
| Snapshot count | 1,020 | 1,020 |
| Mapped volume usage | 1,561 MiB | 12,805 MiB |
| Connections | 0 | 0 |
| Online | No | No |
| Protected | No | No |
| Has locked snapshots | No | No |
| Volume collection | none | none |

Both parent volumes had the same recorded creation date. Their application identifiers lacked the `_DELETED` suffix seen on an earlier cleanup candidate. These were useful differences to preserve, but none identified a snapshot creator or a retention requirement.

Equal counts could reflect a common workflow, a platform constraint, or separate histories arriving at the same count. The number 1,020 alone did not select an explanation.

## The Listing Changed the Question

I collected per-volume snapshot listings. The read-only command shape was:

```text
snap --list --vol pvc-<uuid>
```

The preserved terminal record includes a summary of the captured listings:

```text
Volume A
Snapshot count: 1020
Online states: {'No': 1020}
Statuses: {'Okay': 1020}

Volume B
Snapshot count: 1020
Online states: {'No': 1020}
Statuses: {'Okay': 1020}
```

That established the reported count and online/status fields across the parsed inventory. `Okay` was the array's status label; it was not a restore test or proof that each snapshot had no dependencies.

The visible names included timestamp sequences such as:

```text
2024-09-18::19:47:40.473
2024-09-18::19:47:38.880
2024-09-18::19:47:37.274
2024-09-18::19:47:35.660
```

Those adjacent suffixes were roughly 1.6 seconds apart. That did not resemble the hourly or daily backup cadence I might otherwise have assumed. It gave me a more specific next step: inspect an individual snapshot's description and creation metadata.

The conversation's initial summary code also had a reporting flaw: `rsplit("-", 1)` stripped the year and month from a timestamp-bearing name. Its printed “first” and “last” suffixes were not reliable full chronological bounds. The full visible names and individual `Created` fields were better evidence. A future timeline analysis should extract the complete timestamp and parse it as a date before sorting.

## The Description Was More Useful Than the Prefix

I inspected one snapshot from each volume:

```text
snap --info <snapshot-name> --vol pvc-<uuid>
```

Both returned:

```text
Description: Automatic snap taken before volume resize-shrink case
```

The inspected records also showed `Online: No`, zero connections, `Protected: No`, `Is replica: No`, an empty schedule, and `Locked for: N/A`.

The description changed the working explanation. The two inspected snapshots were described by the array as safeguards taken before a resize-shrink case. Their names alone had not established that purpose. Nor had the empty schedule explained why they existed.

Only two detailed snapshot records were shown. I could report their metadata directly; I could not extend every field to all 2,040 snapshots on the strength of that sample.

## What I Could Establish—and What I Could Not

| Observation | Supported conclusion | Still unresolved |
| --- | --- | --- |
| Both parsed listings contain 1,020 entries | The recorded inventory totals 2,040 snapshots | Why both counts are exactly 1,020 |
| Visible adjacent names have rapid timestamp spacing | Some visible sequences warrant investigation as bursts | Whether retries, repeated successful requests, or another process caused them |
| Two inspected descriptions name a pre-shrink case | Those records identify an array-reported pre-shrink purpose | Whether every snapshot has that purpose |
| Inspected snapshots have no schedule value | Those records do not identify a schedule | The initiating caller and historical workflow |

A Kubernetes CSI-managed volume is not proof that Kubernetes initiated every array operation against it. Kubernetes does not support shrinking PVC capacity as a normal resize workflow. The metadata did not establish that somebody successfully shrank a PVC, or even that an array shrink completed.

An HPE integration, an administrator, another automation, or repeated calls involving capacity handling remained possibilities. Distinguishing them would require historical array audit records, relevant controller logs, deployed versions, and request details. The retained conversation did not supply those records.

The narrow conclusion was still valuable: the investigation had moved from “thousands of unexplained snapshots” to two concrete pre-shrink descriptions and a better question about their initiating workflow.

## Disposal Closure and Historical Explanation

The final phase proposed preserving the snapshot evidence, checking remaining dependencies and retention, then deleting each parent volume through the supported procedure and checking the resulting array state. Parent-volume deletion behavior and dependency restrictions need to be checked against the actual Array OS version before turning that proposal into a reusable procedure.

I later reported that the work was done and the Nimble cleanup chapter was closed. The export contains that completion confirmation, but not the final parent-deletion output or a fresh zero-PVC inventory. The last reproduced inventory-backed volume checkpoint remains the two exceptions. Final removal is operator-reported in this source.

That distinction also applies to capacity: removing the volumes and their snapshot references does not establish a measured physical-space return. No before-and-after physical array capacity counters were provided.

The disposal work could close while the historical cause remained unresolved. The retained metadata was the useful engineering result: it recorded what the array said those inspected snapshots were for, without inventing who requested them.

## Evidence and Reading Order

For the commands, corrected timestamp analysis, and snapshot reporting helper, see the [companion investigation command and script index](/field-notes/nimble-storage-investigation-command-index/).

Source: *Check PVC Volume Status*, 138-page conversation export. Parent metadata appears on pages 46–48; snapshot listing excerpts on pages 120–124; parsed inventory totals and two detailed records on pages 128–130; final operator confirmation on page 137. Conversation interpretations and expected command output are not additional terminal evidence.

- **Previous:** [The Cluster Was Gone. The Storage Wasn't.](/field-notes/the-cluster-was-gone-the-storage-wasnt/)
- **Next:** [The Script Said Success. What Did the Array Say?](/posts/decommissioning-beyond-kubernetes/verified-cleanup/)
- [Series overview](/posts/decommissioning-beyond-kubernetes/)
