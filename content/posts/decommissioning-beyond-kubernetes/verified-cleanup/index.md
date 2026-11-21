+++
title = 'The Script Said Success. What Did the Array Say?'
date = 2026-11-20T00:00:00-06:00
draft = false
description = 'Part 3 of Decommissioning Beyond Kubernetes: designing cleanup automation around explicit scope, live validation, uncertain outcomes, journals, and independent reconciliation.'
tags = ['automation', 'storage', 'kubernetes', 'python', 'operations', 'decommissioning', 'reliability']
categories = ['posts']
series = ['Decommissioning Beyond Kubernetes']
+++

Part 3 of [Decommissioning Beyond Kubernetes](/posts/decommissioning-beyond-kubernetes/).

A cleanup utility can print `success` without proving that the target disappeared. It can also find an object already missing and accidentally claim credit for deleting it. Both errors produce reassuring summaries while weakening the operational record.

The HPE Nimble cleanup in [Part 1](/field-notes/the-cluster-was-gone-the-storage-wasnt/) exposed both problems. Its early utility had a post-delete check that interpreted any query exception as absence. A later dry run found 25 names missing because an earlier batch had already removed them. Those were different conditions requiring different evidence.

The useful design question is: what must be true before automation is allowed to say what happened?

## Inventory Describes a Moment; Approval Defines Scope

The operation started with 1,209 PVC-named array volumes. Of those, 1,200 were offline and nine were online. A filter could produce an offline list quickly. It could not establish that the listed data belonged exclusively to the retired cluster or that its retention period had ended.

Three artifacts served different purposes:

| Artifact | Question it answers |
| --- | --- |
| Inventory | What did the system report at collection time? |
| Candidate manifest | Which objects match the investigation's selection criteria? |
| Approved scope | Which exact objects have been cleared for this operation? |

A dry-run pass adds a fourth fact: an object met the implemented live checks at that time. It neither grants ownership nor freezes the array until execution.

For future tooling, scope should include the array's identity and an immutable object identifier where available, rather than only a name and size. Bind the reviewed manifest and approval set to the run. Otherwise a changed input file, a different SSH alias target, or a recreated object can silently alter what the operation means.

## Make Uncertainty an Explicit Outcome

The early utility contained this post-delete logic, reproduced conceptually from the reviewed code:

```python
try:
    after = remote(host, f"vol --info {name}")
except RuntimeError:
    after = ""
```

An empty result then allowed the utility to record deletion success. The exception could have meant “volume not found,” but it could also have meant authentication failure, transport loss, or another CLI error.

The missing distinction was between **negative evidence from a successful observation** and **failure to observe**.

| Observation | Appropriate result | Next action |
| --- | --- | --- |
| Successful complete inventory lacks the target before deletion | Already missing | Reconcile earlier records; do not count as deleted now |
| Live object fails an eligibility check | Excluded | Record the reason and review separately |
| Authentication or transport fails before deletion | State unknown | Halt and restore reliable observation |
| Delete may have reached the array, but confirmation is unavailable | Outcome uncertain | Reconcile that target before retrying |
| Successful post-delete observation confirms absence | Verified absent after attempt | Record the observation with the attempt |

This is a state model, not just a choice of exception messages. A transport error during a delete request may leave the object gone even though the client received no successful response. Retrying immediately is not reconciliation.

## A Listing Must Be Trustworthy Before Absence Means Anything

The later bulk wrapper improved verification by fetching a fresh listing after deletion and checking that the target was absent. That is stronger than interpreting an arbitrary exception as absence.

It still depends on a complete response and a correct parser. A parser that silently drops malformed rows can turn “I did not understand this row” into “the object is gone.” A truncated listing can do the same thing.

The existing source review also found an important multiline parsing problem. Three saved pre-offline volume captures contained indented ACL entries under an empty-looking header. The parser read unindented `key: value` lines, so it could interpret the ACL as empty while ignoring its entries. Zero active connections and an empty ACL are different facts.

A stronger observer preserves raw output, checks command status, validates response structure, rejects unparsed target-like rows, and distinguishes empty collections from missing fields. Where the interface supports it, structured responses reduce dependence on terminal formatting, though they still require schema and completeness checks.

The successful operational result does not retroactively make an incomplete parser reliable.

## Journal Intent Before Mutation, Then Record the Observation

The bulk journal recorded `delete_intent,started` before issuing a delete, followed by `delete,success` after its verification. That made interrupted execution more understandable than a log containing only final successes.

A useful conceptual progression is:

```text
approved
  -> live checks passed
  -> delete intent recorded
  -> delete requested
  -> absence verified
```

Any failure after the request may require an `uncertain` result. A crash between mutation and the final journal write leaves an unfinished intent, not proof that the mutation failed.

On resume, reconcile unfinished intents against the system before selecting more work. Preserve the original journal. A previous success row is historical evidence; it should not silently substitute for a current final-state check.

Future implementations also need a clear policy for malformed journal rows, duplicate events, exclusive execution, and durable writes. Flushing a CSV stream improves visibility but does not create a transaction with the array. The design must tolerate those two systems disagreeing temporarily.

These are improvements derived from the operation, not a claim that the historical utilities implemented every one of them.

## Count Objects Separately from Events

The bulk dry run had 1,199 entries:

```text
1,172 passed
   25 missing
    2 skipped for snapshots
```

The 25 missing names matched an earlier 25-volume batch. Counting both that earlier batch and the later `missing` observations as separate removals inflated the result.

The archived reconciliation described in Part 1 instead used disjoint name sets:

| Disposition at the November 4 checkpoint | Unique volumes |
| --- | ---: |
| Initial scripted canary | 1 |
| Earlier scripted batch | 25 |
| Later scripted bulk run | 1,172 |
| Reported manual online-volume removal | 1 |
| Final scripted online-volume batch | 8 |
| Preserved snapshot exceptions | 2 |
| **Original inventory accounted for** | **1,209** |

The journals account for 1,206 unique scripted deletion successes. One additional removal is supported by the operator account and inventory transitions. The last inventory-backed checkpoint therefore has 1,207 original names absent and two present. The later removal of those last two is operator-reported, as explained in [Part 2](/field-notes/nimble-snapshot-metadata-pre-shrink-investigation/).

Even this arithmetic needs set checks: were the targets in the original inventory, do the categories overlap, and are any approved names still present? Counts alone cannot answer those questions. For systems that permit name reuse, reconcile immutable IDs as well.

## Authentication and Input Handling Affect Evidence Collection

Two smaller problems mattered because they affected whether the automation could observe the array at all.

First, the original utility used SSH `BatchMode=yes`, while the working manual connection needed a password prompt. Changing the authentication mode and using connection multiplexing addressed that operational mismatch. Reusing a connection reduced prompts; it did not validate subsequent responses.

Second, an operator-side inspection loop processed only the first name because SSH could read from the same standard input as the loop. The corrected read-only pattern was:

```bash
while IFS= read -r vol; do
    ssh -n array-alias "vol --info $vol" || exit 1
done < reviewed-volume-names.txt
```

Here `-n` disconnects SSH from the loop's input. The file must contain validated volume names, and each response must match its requested name. Check that all expected names were inspected; a loop ending without a visible error does not establish completeness.

## Close the Operation with an Independent Observation

The operator captured inventories outside the cleanup utility and compared them with the approved targets. That separate observation was essential because it could challenge the utility's success logic.

It was independent of the deletion code path, not independent of the array itself. It established reported object presence, not application recoverability or physical space reclaimed.

An effective closure report separates:

- Objects deleted during this run and verified absent afterward.
- Objects already missing, with their earlier history reconciled.
- Objects deliberately excluded and why.
- Uncertain attempts still requiring investigation.
- Current observed inventory and its collection time.
- Capacity metrics actually measured, with provisioned size, mapped usage, and physical free space labeled separately.

The strongest cleanup automation leaves enough evidence for another engineer to reconstruct its scope, attempts, exceptions, and observed results. Its final message should be a concise rendering of that evidence, not the only reason to believe the work succeeded.

## Continue the Series

- **Companion reference:** [Investigation command and script index](/field-notes/nimble-storage-investigation-command-index/), including local CSV and unique-object reconciliation recipes.

- [Part 1: The Cluster Was Gone. The Storage Wasn't.](/field-notes/the-cluster-was-gone-the-storage-wasnt/)
- **Previous:** [Two Volumes, 2,040 Snapshots: Following the Metadata](/field-notes/nimble-snapshot-metadata-pre-shrink-investigation/)
- [Series overview](/posts/decommissioning-beyond-kubernetes/)
