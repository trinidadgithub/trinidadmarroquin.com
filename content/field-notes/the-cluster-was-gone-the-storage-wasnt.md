+++
title = "The Cluster Was Gone. The Storage Wasn't."
date = 2026-10-26T00:00:00-05:00
draft = false
description = 'An HPE Nimble PVC cleanup after an RKE2 decommission, reconciled across canary, earlier-batch, bulk-deletion, and array inventory evidence.'
tags = ['kubernetes', 'rke2', 'rancher', 'hpe', 'storage', 'csi', 'decommissioning', 'operations']
categories = ['field-notes']
+++

The Rancher-managed RKE2 cluster had already been shut down. On the HPE Nimble array, I could still list 1,209 volumes named like Kubernetes PVCs. Nine were online; 1,200 were offline. Powering down the VMs had ended the cluster's ability to reconcile storage, but it had not removed the storage objects themselves.

This was a decommission, not a temporary maintenance shutdown. Even so, `offline` was a description of a volume's current state, not permission to erase it. A volume could still belong to another consumer of the array, be needed for recovery, or carry snapshots. With the retired Kubernetes API unavailable, I had to work from retained ownership and approval records plus the array's own inventory, then check the array again after each stage.

## The Number That Looked Bigger Than the Data

I started with the array's `vol --list` output and grouped the `pvc-` rows by online state. The initial capture contained 1,209 such rows: nine online and 1,200 offline with reason `User`. Their sizes totaled 23.24 TiB provisioned, of which 22.64 TiB belonged to the offline set. The listing's reported usage for all PVC volumes was about 1.44 TiB. These figures come from summing the listing's size and usage columns in MiB and dividing by 1,048,576 to obtain TiB.

The 22.64 TiB was a sum of provisioned volume sizes, not a forecast of physical space to recover. An inspected example was thinly provisioned with compression and deduplication enabled. Mapped usage is a different measure from provisioned size, and neither tells me how much free physical array space will increase when snapshots or shared blocks still reference data. I used the size and usage totals to characterize the inventory, not to promise a capacity return.

## An Array Record Is Evidence, Not an Ownership Decision

The Nimble CLI accepted `vol --info`, rather than `vol info`. For an individual candidate, the useful questions were visible directly:

```text
Nimble OS $ vol --list
Nimble OS $ vol --info pvc-<uuid>

State: offline                 Online: No
Offline reason: User          Number of connections: 0
Snapshot count: 0             Protected: No
Volume collection: none       Access Control List:
Connected Initiators:         Application identifier: ContainerVolume-..._DELETED
```

That is a redacted shape of the inspected canary's output, not a template for every volume. The `_DELETED` suffix on an application identifier suggested prior CSI lifecycle activity; it did not prove that the Kubernetes PVC had been deleted or that retention had expired. Zero initiators and an empty ACL were helpful current-state evidence, but a shut-down cluster would also have no active writer. Ownership and the decision to discard data required a separate human check.

I kept an offline-volume manifest distinct from the approval list. The manifest recorded volume name, size, usage, online state, and offline reason from an inventory snapshot. The approval list contained only names cleared for deletion after ownership and retention review. A dry run queried live `vol --info` for each selected name; it was not a deletion. The first approval contained one volume, so the first execution could affect only that canary.

## The SSH Failure Was Not a Storage Failure

The initial Python utility failed its first dry run with SSH exit 255 and `Permission denied`. Interactive SSH and a manual remote `vol --list` worked when a password was supplied. Inspecting the original utility explained the difference: it invoked SSH with `BatchMode=yes`, which prevented that password prompt. The working copy used `BatchMode=no`; a second one-volume dry run recorded a pass. This was an authentication-mode failure, not evidence that the PVC was absent or unsafe.

Executing the canary then required four separate password prompts for the utility's remote calls. The operator adopted an SSH alias with OpenSSH connection multiplexing for later work, reusing an authenticated connection instead of embedding a password in the script. A subsequent 25-volume dry run completed successfully through that alias.

The canary's execution journal recorded one `delete,success` row. A separate `vol --list` check returned no entry for that name. The independent listing mattered: the original canary utility's internal post-delete test caught *any* `vol --info` error and treated it as absence, even though an SSH error could have produced the same exception. Its success row alone was not sufficient proof.

## Twenty-Five Missing Names Had Their Own History

The operation then had a distinct 25-volume batch, with its own `delete-batch-001.csv`: 25 `delete,success` records. A later full dry run of the remaining candidate list called those same 25 names `missing`. I matched all 25 dry-run `missing` names to that earlier batch journal and to their absence from the later inventory. They were **previously deleted in a separate batch**, not deleted by the later bulk utility and not unexplained bulk failures. The PDF discussion briefly left their origin uncertain; the separate journal resolves that point in the files available here.

The full dry-run journal accounted for 1,199 entries after excluding the canary: 1,172 passed live checks, 25 were already missing, and two were skipped for snapshots. The two skipped volumes were offline, but `vol --info` showed **1,020 snapshots on each**—2,040 collectively. They had no `_DELETED` suffix in the inspected application identifiers. I did not infer what workload produced the snapshots or why they were retained. Those volumes were excluded from the final approved bulk list and left for a separate ownership and retention investigation.

The bulk utility processed only the 1,172 approved names. Its journal has a `delete_intent,started` and a `delete,success` record for each one; the reported run had no skips or failures. For each target the code checked a fresh per-batch listing, queried `vol --info` immediately before deletion, and required a successful new listing in which that name was absent afterward. These are useful controls, but the final check still had to come from an inventory collected outside the utility.

## What the Final Inventory Established

I reconciled the independent before-and-after listings against all three execution journals and the approval list:

| PVC inventory | Before | After |
| --- | ---: | ---: |
| Total volumes | 1,209 | 11 |
| Online | 9 | 9 |
| Offline | 1,200 | 2 |
| Provisioned size | 23.24 TiB | 0.64 TiB |
| Reported volume usage | 1.44 TiB | about 0.01 TiB |

Exactly 1,198 names in the first listing were absent in the final one: **one canary**, **25 from the earlier batch**, and **1,172 from the bulk run**. None of the 1,172 final approved targets remained. The same nine online PVC names remained, and the only two offline PVCs left were the snapshot-bearing exceptions. This reconciles the count change without crediting the bulk utility for the earlier batch.

The roughly 22.60 TiB reduction in provisioned PVC size and roughly 1.43 TiB difference in reported volume usage compare two inventory snapshots. They are not measurements of physical array space reclaimed. The outstanding work is to identify the owners, dependencies, and retention rules for the two preserved volumes and their snapshots; their offline state does not answer those questions.

What stayed with me was the handoff between lifecycles. Shutting down Kubernetes did not run its CSI deletion workflow. The array could tell me whether volumes existed, were presented, or carried snapshots; it could not grant data-disposal authority. Approval, live validation, a recorded deletion attempt, and independent inventory reconciliation were each a different piece of the decommission—and all four were needed to say what actually happened.
