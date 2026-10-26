# HPE Nimble orphaned PVC cleanup after an RKE2 decommission

## Purpose and boundaries

This runbook reconstructs a completed cleanup and provides a procedure for future **approved** decommissions of Rancher-managed RKE2 clusters using HPE Nimble CSI volumes. Commands below are examples for an authorized operator, not commands executed by this documentation task. `vol --delete` permanently removes a volume; no automatic rollback exists. Do not treat a powered-off node, an offline array volume, or a `pvc-` name as proof of orphan status. The retired Kubernetes API may be unavailable, and the array may serve other clusters.

The example utility versions are `nimble_pvc_cleanup.py` and `run_remaining.py` from the operation's working directory. Review the exact deployed copies and their `--help` before reuse. The bulk wrapper imports parsing and inspection functions from `nimble_pvc_cleanup.py`; keep compatible copies together. See [tooling review](../analysis/nimble-cleanup-tooling-review.md) for limitations that matter before another destructive run.

## 1. Prerequisites and ownership

- Identify the array, decommissioned cluster, other consumers of the array, storage owner, change owner, backup/restore owner, and approval record. Establish that the cluster is permanently retired rather than temporarily stopped.
- Retain the pre-shutdown PV/PVC-to-array mapping, CSI handles, reclaim policies, application owner and data-retention decisions. If the retired API cannot be queried, use preserved exports and storage records; do not substitute an absent live API response for proof of no owner.
- Confirm restoration and legal/operational retention needs per volume. An application identifier ending in `_DELETED` is a clue, not authorization. Exclude any volume whose ownership is ambiguous.
- Keep raw inventories, approvals, and journals in a restricted evidence location; do not copy credentials, private addresses, or unredacted array details into publication material. Ensure only one cleanup process owns the approval scope and journal at a time.

## 2. Initial array inventory and classification

On an authorized workstation, `ssh <array-alias> 'vol --list'` is a **read-only** remote array query. In the completed operation its output was saved as `nimble-vol-list.txt`; confirm SSH exit status and a complete, plausible listing before using a capture. If piping through filters, enable `pipefail` or save the listing only after the SSH command succeeds—empty output is not a successful inventory. For an individual record, `ssh <array-alias> 'vol --info pvc-<uuid>'` is also read-only. At the interactive Nimble prompt the syntax is `vol --list` and `vol --info pvc-<uuid>`, not `vol info`.

The listing columns in the captured output are `Name`, `Size (MiB)`, `Online`, `Offline Reason`, and `Usage (MiB)`. For `pvc-` rows, classify `Online=Yes` separately from `Online=No` with `Offline Reason=User`; quarantine malformed or unexpected rows rather than treating them as eligible. To reproduce the *historical* inventory using the inspected parser, with a saved listing:

```bash
python3 nimble_pvc_cleanup.py inventory \
  --listing nimble-vol-list.txt --output nimble-review
```

This **writes local** manifest and candidate files and initializes an approval file if absent; it does not delete an array volume. `inventory()` filters parsed PVC rows to `No`/`User` and writes `offline-pvc-deletion-manifest.csv` with `volume_name,size_mib,usage_mib,online,offline_reason`. The candidate list is *not* an approval list. `--overwrite` deliberately refreshes an existing manifest; retain the old inventory as evidence and reconcile before replacing it. The parser skips lines it cannot parse, so independently check listing completeness and compare counts against the source output.

For capacity reports, sum the listing's size and usage fields for valid PVC rows, grouped by online state; divide MiB by 1,024 for GiB and 1,048,576 for TiB. The operation's initial saved listing yields nine online and 1,200 offline PVCs; all 1,209 total have 23.24 TiB provisioned and about 1.44 TiB reported usage. The offline set has 22.64 TiB provisioned. **Neither metric equals physical array capacity to be reclaimed.** Record array-level free/used counters and snapshot/dedupe dependencies separately if actual physical recovery must be measured.

## 3. Candidate manifest and explicit approval

For each candidate, compare the manifest with retained PV/PVC ownership and retention evidence, then inspect live `vol --info` for `Name`, `State`, `Online`, `Offline reason`, `Size (MiB)`, `Number of connections`, ACL, connected initiators, `Snapshot count`, locked snapshots, `Protected`, `Volume collection`, `Clone`, and CSI application identifier. Do not infer data-disposal permission from any one field. Obtain a named approval list separate from both the inventory manifest and the candidate list; use a unique approved name per line and record approver, scope, and timestamp outside the utility.

The original utility validates name format, membership in the manifest, and no duplicate approval, but does not validate cluster ownership, approval signatures, or retention. The bulk wrapper checks manifest `No`/`User` and numeric size as well. Freeze reviewed inputs and check that the approved set is disjoint from online and snapshot-exception sets. A dry-run pass is a point-in-time storage check, not an approval grant.

## 4. SSH authentication and dry runs

In this operation, interactive/password SSH worked while the original bundled `nimble_pvc_cleanup.py` used `BatchMode=yes` and failed its first dry run with exit 255. The later working copy uses `BatchMode=no`; test both interactive SSH and a single remote `vol --list` before trusting automation. A private OpenSSH alias with `ControlMaster auto`, a protected `ControlPath`, and `ControlPersist` allowed one authenticated master session to serve repeated remote commands; its lifetime and permissions must be managed locally. The scripts do not store a password. Multiplexing is an operational convenience, not proof that an array query succeeded; a dropped master can affect later calls.

For a separately approved one-volume list, this **read-only array preflight** writes a *local* CSV log and performs no deletion:

```bash
python3 nimble_pvc_cleanup.py batch \
  --host nimble-cleanup \
  --manifest nimble-review/offline-pvc-deletion-manifest.csv \
  --approved nimble-review/offline-pvc-delete-approved.txt \
  --batch-size 1 --log dry-run-002.csv
```

Expect `dry_run,pass` only if live checks pass; `dry-run-001.csv` in the source operation instead recorded an SSH authentication error. Do not infer that `--batch-size 25` creates 25 approvals: it limits processing to at most 25 names already in the approved file. A separate 25-name approval list produced a 25/25 preflight (`dry-run-batch-001.csv`) in the recorded operation.

After the canary, the wrapper dry-ran the remaining approved names in batches of 25:

```bash
python3 run_remaining.py \
  --host nimble-cleanup \
  --manifest nimble-review/offline-pvc-deletion-manifest.csv \
  --approved nimble-review/remaining-approved.txt \
  --journal remaining-dry-run.csv --batch-size 25
```

This does not delete volumes. Its actual dry-run results were 1,172 `dry_run,pass`, 25 `check,missing`, and two `check,skipped` for snapshots. All 25 missing names also have `delete,success` rows in an **earlier, separate** `delete-batch-001.csv`; they were not deleted by the later bulk utility. Produce a new, reviewed `final-delete-approved.txt` containing only the 1,172 passing names; verify uniqueness, manifest membership, exclusions and ownership. In the source files the final approval copy is retained in `nimble-cleanup-evidence/`, while earlier working approvals are under `nimble-review/`.

## 5. One-volume canary — destructive, authorized operator only

After the one-volume dry run and owner/retention approval, the recorded command shape was:

```bash
python3 nimble_pvc_cleanup.py batch \
  --host nimble-cleanup \
  --manifest nimble-review/offline-pvc-deletion-manifest.csv \
  --approved nimble-review/offline-pvc-delete-approved.txt \
  --batch-size 1 --execute \
  --confirm DELETE-nimble-cleanup-1 --log delete-001.csv
```

**Effect:** the script issues `vol --delete <approved-volume>` after its live checks. Confirm the approval file contains *exactly one* intended name and that the confirmation string matches the selected host and batch length; the script cannot itself grant disposal authority. It does not force-delete, disassociate collections, or remove snapshots. Do not run an unreviewed `vol --dissoc` or snapshot deletion to bypass a failed preflight.

The canary journal recorded one successful delete. Independently obtain a *successful* fresh `vol --list` and confirm that exact name is absent. A failed SSH command or failed listing is inconclusive. The original script's `vol --info` postcheck treats every `RuntimeError` as absence, so its `success` record needs this independent corroboration.

## 6. Controlled batch deletion — destructive, authorized operator only

The operation also ran a separate 25-volume batch using the original utility, producing 25 successes in `delete-batch-001.csv`. Before any batch, verify its approval file, exact name count, successful dry-run results, current owner decision, journal destination, and no concurrent operator. The wrapper's recorded **destructive** invocation for the separately approved remainder was:

```bash
python3 run_remaining.py \
  --host nimble-cleanup \
  --manifest nimble-review/offline-pvc-deletion-manifest.csv \
  --approved nimble-review/final-delete-approved.txt \
  --journal remaining-delete.csv --batch-size 25 \
  --execute --confirm DELETE-ALL-APPROVED-nimble-cleanup
```

**Effect:** up to the number of approved eligible volumes are permanently deleted, in groups of 25 (supported `--batch-size` range 1–50), subject to preflight. `--batch-size` is grouping, **not** a limit on total deletions in `run_remaining.py`. The confirmation token confirms the host string, not a hash or count of approved names. Use a new execution journal rather than a dry-run journal. For each group the wrapper gets a fresh `vol --list`; for each existing target it checks listing state/size, queries `vol --info`, records `delete_intent`, calls `vol --delete`, then requires a successful fresh listing without that name before recording `delete,success`. `--pause` is supported between successful deletes if a reviewed rate limit requires it. Do not start concurrent copies.

## 7. Journal, error handling and interrupted execution

Both CSV formats have `timestamp_utc,action,volume,result,detail`; parse with a CSV reader rather than splitting on commas in quoted details. `dry_run,pass` means eligible at check time only. `check,missing` means absent before that attempt, not deleted by this run. `check,skipped` means failed a live safety check. `delete_intent,started` records intent **before** the remote delete; `delete,success` follows a successful command and absent-from-list verification in the wrapper. `batch,halted` calls for reconciliation. The recorded final bulk journal has 1,172 intent/success pairs and no skips or halts; the operator's completion output reported `passed=1172 skipped=0 previously_deleted=0` for that journal.

The original `batch` script stops at the first error by default (`--stop-on-error` cannot disable that default), writes an error row, and exits nonzero. The wrapper skips a known-missing volume or one failing a local live check, but halts on recognized SSH transport/auth errors or uncertain post-delete outcomes. Not every array CLI error is classified as infrastructure failure; see the tooling review. Before resuming after an interruption, inspect the last full journal row and the live array: a started intent without success is **uncertain**, not a failed deletion or a reusable approval. Preserve the journal and approved file, reconcile affected names independently, and only then consider a resumed run. The wrapper reads `delete,success` names from the same journal and omits them from a repeat run; it does not re-check those names on resumption. Never edit a journal to manufacture a success.

## 8. Independent verification and disposition

Obtain a new successful `vol --list` outside the deletion utility and preserve it as `nimble-final-inventory.txt`. Parse `pvc-` names, confirm all final approved names are absent, all protected online names remain, and explicitly confirm every exception is still present. Compare full sets rather than trusting a summary count or a grep over a failed SSH pipe. Reconcile initial minus final names against the canary journal, earlier 25-volume batch journal and later bulk journal, with no overlaps or unexplained names. The archived evidence reconciles **1 + 25 + 1,172 = 1,198** absent PVC names. The 25 had already been deleted by the earlier batch; they were only `missing` from the later dry run and never bulk-deletion successes.

The final archived listing contains 11 PVCs: nine online and two offline. Their provisioned sizes total 0.64 TiB and reported usage about 0.01 TiB. The before/after provisioned difference is about 22.60 TiB; the reported-usage difference is about 1.43 TiB. Neither is measured physical capacity reclaimed. Include the collection time, array-level capacity counters if available, and snapshot dependency evidence in any physical-capacity claim.

For a local **read-only** cross-check of the archived files after confirming that the SSH capture succeeded, the following demonstrates the set comparison. It prints counts and stops if the approved bulk set is not the recorded successful bulk set, or if any approved bulk name remains:

```bash
python3 - <<'PY'
import csv
from pathlib import Path

evidence = Path('nimble-cleanup-evidence')
approved = set((evidence / 'final-delete-approved.txt').read_text().split())
with (evidence / 'remaining-delete.csv').open(newline='') as stream:
    deleted = {row['volume'] for row in csv.DictReader(stream)
               if row['action'] == 'delete' and row['result'] == 'success'}
final = {parts[0] for line in (evidence / 'nimble-final-inventory.txt').read_text().splitlines()
         if (parts := line.split()) and parts[0].startswith('pvc-')}
assert approved == deleted, 'Approval and bulk journal disagree'
assert not approved & final, 'Approved volume still present'
print(f'Approved bulk deletions absent: {len(approved)}')
print(f'PVCs remaining: {len(final)}')
PY
```

Reconcile the earlier `delete-batch-001.csv` separately; it is outside the archived `nimble-cleanup-evidence/` directory. Count unique names and inspect all journal result types before interpreting any totals. A failed or incomplete original SSH capture cannot be repaired by a clean set comparison of the captured text.

## 9. Snapshot exceptions, reporting and recovery limits

Two preserved offline volumes each had `Snapshot count: 1020` in inspected `vol --info` output. The later dry run skipped them, and both appear in the final listing. Keep their names and any snapshot metadata in restricted evidence; investigate their owners, retention, clones and dependent data separately. Do not infer the snapshot schedule or purpose from equal counts, and do not delete snapshots just to permit volume removal.

Archive the original and final listings, manifests, signed approvals, canary and earlier-batch journals, bulk dry-run and execution journals, CLI/version information, change record, exceptions, and independent set reconciliation. Report canary, earlier batch, later bulk, and preserved exceptions as separate dispositions. Deleting a volume has no simple rollback: recovery depends on a separately validated backup, snapshot or other restore source, none of which is established by this runbook. A success row is not a substitute for a restore test or an array-level audit of physical reclamation.
