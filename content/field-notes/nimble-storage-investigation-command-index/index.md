+++
title = 'Investigating Residual Kubernetes Storage: A Command and Script Index'
date = 2026-11-20T00:00:00-06:00
draft = false
description = 'An intent-indexed HPE Nimble investigation toolkit: inventory capture, volume metadata, snapshot timelines, CSV journal analysis, and unique-volume reconciliation.'
tags = ['kubernetes', 'hpe', 'nimble', 'storage', 'csi', 'python', 'ssh', 'operations', 'decommissioning']
categories = ['field-notes']
series = ['Decommissioning Beyond Kubernetes']
+++

Companion reference for [Decommissioning Beyond Kubernetes](/posts/decommissioning-beyond-kubernetes/).

During the Nimble cleanup, the useful unit of investigation was usually a question: which volumes remained, which records had snapshots, why a later run reported missing names, or whether the approved targets were actually gone. This note indexes the commands and small analysis scripts by those questions.

The examples are sanitized adaptations of the operation recorded in *Check PVC Volume Status*. They include corrections learned during the investigation. The downloadable helper below is newly written for this reference; it is not the historical deletion utility. It reads saved local evidence and prints JSON. It performs no SSH calls or array changes.

## Quick Index by Intent

| Question | Recipe | Evidence produced |
| --- | --- | --- |
| What does the array currently report? | [1. Capture an inventory](#1-capture-an-inventory) | Raw volume listing and stderr |
| Which PVC-named volumes are online or offline, and how large are they? | [2. Classify and measure](#2-classify-and-measure) | Grouped counts, provisioned size, reported usage |
| Which names need further investigation? | [3. Build candidate sets](#3-build-candidate-sets) | Offline and online name lists |
| What dependencies does a volume show? | [4. Inspect one volume](#4-inspect-one-volume) | Full metadata, including multiline fields |
| Did I inspect every selected volume? | [5. Collect and check inspection coverage](#5-collect-and-check-inspection-coverage) | Matching per-volume captures |
| Does Kubernetes still reference this storage? | [6. Preserve Kubernetes mappings](#6-preserve-kubernetes-mappings) | PV identities, claim references, CSI handles |
| What snapshots exist, and what are they for? | [7. Collect snapshot evidence](#7-collect-snapshot-evidence) | Snapshot listing and detailed metadata |
| Were snapshots created in bursts? | [8. Analyze snapshot state and timestamps](#8-analyze-snapshot-state-and-timestamps) | Counts, full timestamp bounds, adjacent intervals |
| What did each automation phase report? | [9. Summarize journals](#9-summarize-journals) | Action/result counts and unique-success sets |
| Why is a target already missing? | [10. Explain missing names](#10-explain-missing-names) | Names with and without other success evidence |
| Did the approved cleanup finish? | [11. Reconcile unique objects](#11-reconcile-unique-objects) | Remaining targets, unexplained absences, overlaps |
| What did the original utilities do? | [12. Historical utility index](#12-historical-utility-index) | Roles, inputs, and known limitations |

## Shared Setup and Helper

Use Bash on an authorized workstation, Python 3.9 or later, and `jq` for the JSON selection examples. Configure `array-alias` in your own SSH configuration for the intended array. Establish the connection and verify the endpoint before collecting evidence. Password prompts may use the controlling terminal even when commands use `ssh -n`.

Create a new evidence directory for this collection session:

```bash
mkdir nimble-investigation-2026-11-20
cd nimble-investigation-2026-11-20
```

Use a different directory name for a later collection. Keep captures together with their collection times and array identity in your operational records.

Download [storage_evidence.py](storage_evidence.py) into that directory. It has four local-analysis commands:

```bash
python3 storage_evidence.py --help
python3 storage_evidence.py inventory --help
python3 storage_evidence.py snapshots --help
python3 storage_evidence.py journals --help
python3 storage_evidence.py reconcile --help
```

The helper expects the **unwrapped CLI formats shown in the operation**, with MiB units. It validates headers and rejects malformed PVC rows and duplicate names. It does not reconstruct rows broken by terminal wrapping or PDF extraction. Use original text captures, not text copied out of the PDF.

Validation cannot prove a listing is complete: truncation at a row boundary can still look valid. A header-only listing produces zero PVC rows, but that count needs corroboration from a successful, complete array query. Keep the raw captures and inspect unexpected results.

## 1. Capture an Inventory

**Intent:** Save what the array reports before applying filters. This queries the array read-only and writes local files.

```bash
if ssh -n array-alias 'vol --list' > volumes-before.txt.partial 2> volumes-before.stderr; then
    mv volumes-before.txt.partial volumes-before.txt
else
    printf '%s\n' 'Inventory capture failed; inspect volumes-before.stderr.' >&2
fi
```

Only the successful SSH path promotes the capture to `volumes-before.txt`. On failure, retain the partial response and stderr for diagnosis; do not analyze them as a complete inventory. Use each capture filename once in a new collection directory.

A successful transport is necessary but not sufficient: inspect the header, any CLI error text, and whether the response plausibly covers the intended array. Filtering a failed query down to no matching rows is not evidence of absence.

## 2. Classify and Measure

**Intent:** Count PVC-named volumes by state and label capacity measurements correctly. This reads a local listing and writes a local report.

```bash
python3 storage_evidence.py inventory volumes-before.txt > inventory-before.json
jq '.summary' inventory-before.json
```

The report contains `online`, `offline`, and `total` groups. Each includes count, `size_mib`, `size_gib`, `size_tib`, and the corresponding `usage` values. The source columns are provisioned size and array-reported volume usage.

```text
GiB = MiB / 1,024
TiB = MiB / 1,048,576
```

In the original inventory, the offline set contained 1,200 volumes and approximately 22.64 TiB provisioned. That was not 22.64 TiB of physical space waiting to be recovered. Physical reclamation needs separate array capacity measurements and an understanding of snapshots, compression, deduplication, and shared blocks.

The helper selects syntactically valid `pvc-<uuid>` names. The prefix is a discovery convention, not proof of cluster ownership.

## 3. Build Candidate Sets

**Intent:** Extract names for inspection, preserving online volumes as a distinct set. These commands only read and write local files.

```bash
jq -r '.volumes | to_entries[]
  | select(.value.online == "No" and .value.offline_reason == "User")
  | .key' inventory-before.json | sort > offline-candidates.txt

jq -r '.volumes | to_entries[]
  | select(.value.online == "Yes")
  | .key' inventory-before.json | sort > online-volumes.txt

wc -l offline-candidates.txt online-volumes.txt
comm -12 offline-candidates.txt online-volumes.txt
```

The intersection should be empty because the two sets come from one parsed inventory. This is a consistency check, not independent verification or a deletion approval. Keep the reviewed approval scope in a separate file.

Run these selections only after the inventory command succeeds. A JSON file created by shell redirection can be empty if its producer fails.

## 4. Inspect One Volume

**Intent:** Read the complete record behind an inventory row.

```bash
VOL='pvc-00000000-0000-0000-0000-000000000001'
ssh -n array-alias "vol --info $VOL"
```

Replace the synthetic UUID with the selected volume. At the Nimble prompt, the command is `vol --info <name>`, not `vol info <name>`.

Read these fields together:

| Field | Investigative use |
| --- | --- |
| Name, serial number, size | Confirm the requested object and preserve identity evidence |
| State, Online, Offline reason | Describe current availability state |
| Number of connections, Connected Initiators | Identify reported current sessions |
| Access Control List | Inspect presentation permissions, including indented entries |
| Snapshot count, Has locked snapshots | Identify snapshot exceptions |
| Protected, Volume collection | Identify protection associations |
| Clone, Parent volume, Base snapshot | Identify parentage requiring further dependency review |
| Application identifier | Preserve CSI-related metadata as a clue |

An empty-looking ACL header can have entries on subsequent indented lines. Keep the full output. A header-only `grep` report concealed those entries during this operation. Likewise, `Clone: No` describes the inspected volume; it is not an exhaustive reverse-dependency search for every object that might depend on it.

## 5. Collect and Check Inspection Coverage

**Intent:** Inspect all selected names without SSH consuming the loop's input. Use a new output directory and a reviewed, nonempty name list.

```bash
mkdir volume-info
(
    count=0
    while IFS= read -r vol || [[ -n "$vol" ]]; do
        [[ "$vol" =~ ^pvc-[[:xdigit:]]{8}(-[[:xdigit:]]{4}){3}-[[:xdigit:]]{12}$ ]] || exit 1
        ssh -n array-alias "vol --info $vol" \
          > "volume-info/$vol.info.partial" \
          2> "volume-info/$vol.stderr" || exit 1
        grep -Fxq "Name: $vol" "volume-info/$vol.info.partial" || exit 1
        mv "volume-info/$vol.info.partial" "volume-info/$vol.info"
        count=$((count + 1))
    done < offline-candidates.txt
    (( count > 0 )) || exit 1
    printf 'Collected %d matching volume records\n' "$count"
)
```

`ssh -n` redirects SSH's standard input from `/dev/null`; otherwise the first command can drain the list being read by the loop. The subshell makes `exit 1` stop collection without closing the operator's parent shell.

Independently check coverage from the requested list:

```bash
python3 - <<'PY'
from pathlib import Path
names = Path('offline-candidates.txt').read_text().splitlines()
if not names or len(names) != len(set(names)):
    raise SystemExit('Empty or duplicate inspection scope')
missing = []
for name in names:
    path = Path('volume-info') / f'{name}.info'
    if not path.is_file() or f'Name: {name}' not in path.read_text().splitlines():
        missing.append(name)
print(f'Requested: {len(names)}; matching captures: {len(names) - len(missing)}')
if missing:
    raise SystemExit('Missing/mismatched captures: ' + ', '.join(missing))
PY
```

Coverage establishes matching captures, not that every field was understood or every dependency cleared. Review full records separately.

## 6. Preserve Kubernetes Mappings

**Intent:** Save the Kubernetes side of the identity mapping while its API is available.

```bash
kubectl --context cluster-a get pv -o json > cluster-a-pvs.json
jq -r '.items[] | [
  .metadata.name, .metadata.uid, .status.phase,
  (.spec.claimRef.namespace // ""), (.spec.claimRef.name // ""),
  (.spec.csi.driver // ""), (.spec.csi.volumeHandle // ""),
  (.spec.persistentVolumeReclaimPolicy // "")
] | @tsv' cluster-a-pvs.json
```

Use the actual context, verify the export succeeded, and repeat for each cluster sharing the array. Preserve relevant PVC and VolumeAttachment exports where available. CSI handles are driver-specific: do not assume the array volume name appears inside the handle or that substring matching establishes identity. Retain the driver-specific mapping and array serial/ID evidence.

A decommissioned cluster may no longer have an API. An unavailable API does not return an authoritative empty ownership set; use retained exports and owner records.

## 7. Collect Snapshot Evidence

**Intent:** Save a volume's snapshot inventory, then inspect a specific snapshot to explain its metadata. Both array commands are read-only.

```bash
VOL='pvc-00000000-0000-0000-0000-000000000001'
if ssh -n array-alias "snap --list --vol $VOL" \
    > snapshots.txt.partial 2> snapshots.stderr; then
    mv snapshots.txt.partial snapshots.txt
else
    printf '%s\n' 'Snapshot inventory failed; inspect snapshots.stderr.' >&2
fi
```

Select a real name from the successful capture rather than assuming the first row is newest:

```bash
SNAP='replace-with-exact-snapshot-name'
ssh -n array-alias "snap --info $SNAP --vol $VOL"
```

The investigation's two detailed records included `Description: Automatic snap taken before volume resize-shrink case`. Inspect description, `Created`, online state, protection, locking, replication, schedule, and presentation fields. A sample explains that sample; it does not establish identical metadata across the complete inventory.

The transcript also proposed `snap --list --vol <name> --manually_managed`, but shows no returned result for that classification check. Confirm that option against the installed Array OS help before using it; do not report the expected count as an observed classification.

## 8. Analyze Snapshot State and Timestamps

**Intent:** Summarize the saved rows and investigate cadence using complete name timestamps.

```bash
python3 storage_evidence.py snapshots snapshots.txt --volume "$VOL" > snapshot-summary.json
jq '{count, online_states, statuses, timestamped_names, names_without_timestamp,
  earliest_name_timestamp, latest_name_timestamp,
  adjacent_intervals_at_most_2_seconds}' snapshot-summary.json
```

The helper extracts a full trailing `YYYY-MM-DD::HH:MM:SS.fraction`, parses it, sorts timestamps, and calculates adjacent intervals. It reports names without that suffix separately. Unlike the transcript's original `rsplit('-', 1)` expression, it keeps the year and month.

To inspect the intervals:

```bash
jq '.adjacent_intervals_seconds' snapshot-summary.json
```

The two-second count is a descriptive threshold for exploring the roughly 1.6-second sequences seen in this investigation. It is not an anomaly detector or a diagnosis. Name timestamps have no timezone in this format and can differ from authoritative creation metadata; corroborate selected entries with `snap --info`. An `Okay` status is not a restore test.

## 9. Summarize Journals

**Intent:** Count action/result pairs and distinguish unique deletion successes from events. This reads local CSV files.

```bash
python3 storage_evidence.py journals \
  delete-001.csv delete-batch-001.csv remaining-delete.csv \
  final-eight-delete.csv > journal-summary.json
jq '.events, (.unique_successes | length), .success_overlap_between_files' journal-summary.json
```

Supply the actual retained files explicitly, once each. The expected schema is:

```text
timestamp_utc,action,volume,result,detail
```

The helper uses `csv.DictReader` so quoted commas in `detail` remain part of that field. It rejects unexpected headers and incomplete rows. It counts distinct action/result pairs, including unfamiliar ones, for review rather than silently dropping them.

`delete_intent,started` and `delete,success` are two events for potentially one object. `dry_run,pass` is eligibility at check time, not deletion. Duplicate success events remain visible in event totals while `.unique_successes` deduplicates names.

## 10. Explain Missing Names

**Intent:** Compare later missing observations with other successful deletion records.

```bash
python3 storage_evidence.py journals \
  remaining-dry-run.csv delete-001.csv delete-batch-001.csv \
  remaining-delete.csv > missing-analysis.json
jq '.missing_with_prior_or_other_success,
  .missing_without_success,
  .intents_without_any_success' missing-analysis.json
```

In this operation, all 25 later missing names matched the earlier 25-volume batch. This helper reports set overlap; it does not establish event chronology. Check timestamps and the corresponding inventory transitions before calling a matching success “prior.”

Similarly, `intents_without_any_success` identifies names with no success anywhere in the supplied files. A name with a later unresolved retry can still have an older success and will not appear in that set. Inspect the event sequence for interrupted operations; this summary is not a resume controller.

## 11. Reconcile Unique Objects

**Intent:** Compare the original and final inventories with the approved scope and journaled successes.

Collect a fresh `vol --list` outside the cleanup utility using Recipe 1's capture pattern and a new filename, `volumes-after.txt`. Then run local analysis:

```bash
python3 storage_evidence.py reconcile \
  --original volumes-before.txt \
  --final volumes-after.txt \
  --approved approved-scope.txt \
  delete-001.csv delete-batch-001.csv remaining-delete.csv \
  final-eight-delete.csv > reconciliation.json

jq '{original_count, final_count,
  approved_still_present, approved_outside_original,
  successes_still_present, successes_outside_approved,
  approved_absent_without_success, new_names_in_final}' reconciliation.json
```

Use the frozen approved scope for the phases represented by those journals. It must contain one valid name per line with no duplicates. A target absent without a script success needs an explanation, such as the separately reported manual removal in this operation; do not manufacture a success record to balance the table.

The helper exits nonzero for invalid input. A valid report can contain discrepancies and still exit zero: inspect its arrays. They are findings, not parsing failures. For an automated local check of the approved-target absence condition only:

```bash
jq -e '.approved_still_present | length == 0' reconciliation.json
```

Also review `.absent_original_without_success`, the nested journal analysis, and any new names in the final inventory. Name-based comparison cannot detect replacement under a reused name; use immutable array identities for stronger reconciliation. Neither an empty target intersection nor a matching count proves that unrelated datastores were untouched or that physical space was reclaimed.

## 12. Historical Utility Index

| Utility | General-purpose intent | Historical inputs and outputs | Boundary |
| --- | --- | --- | --- |
| `nimble_pvc_cleanup.py inventory` | Turn a saved listing into a candidate manifest | Listing → manifest CSV, candidate names, initially empty approval file | Selects candidates; does not establish ownership |
| `nimble_pvc_cleanup.py batch` without execution enabled | Query selected volumes for live preflight | Manifest + approved names → `dry_run` CSV | Historical parser missed indented ACL entries |
| `nimble_pvc_cleanup.py batch` with execution enabled | Execute a selected approved batch | Manifest + approved names → deletion journal | Original postcheck could treat query errors as absence |
| `run_remaining.py` | Coordinate remaining approved work in groups and journal attempts | Manifest + scope + journal → intent/result events | Historical resume logic trusted existing successes; incomplete observation still needed reconciliation |
| `storage_evidence.py` in this note | Analyze saved inventories, snapshot rows, and journals | Local evidence → JSON summaries and name sets | New analysis helper; no remote execution, ownership decisions, or deletion |

The website repository contains the historical [runbook source](https://github.com/trinidadgithub/trinidadmarroquin.com/blob/main/docs/runbooks/hpe-nimble-orphaned-pvc-cleanup.md) and [tooling review](https://github.com/trinidadgithub/trinidadmarroquin.com/blob/main/docs/analysis/nimble-cleanup-tooling-review.md), but not the original cleanup Python files. Their index entries summarize that review, not a fresh validation of deployed copies. Obtain and inspect the exact utilities before reusing their execution interfaces.

## Evidence and Series Links

The PDF's inventory/capacity discussion is on pages 4–8; authentication and canary work on pages 14–28; batch-loop source on pages 34–37; dry-run CSV schema mismatch on pages 49–50; independent inventories on pages 59 and 104–105; SSH stdin diagnosis and corrected collection on pages 84–90; snapshot inventory and metadata on pages 120–130. Expected output in the conversation is not an additional observation.

- [Series overview and reading order](/posts/decommissioning-beyond-kubernetes/)
- [Part 1: The Cluster Was Gone. The Storage Wasn't.](/field-notes/the-cluster-was-gone-the-storage-wasnt/)
- [Part 2: Two Volumes, 2,040 Snapshots: Following the Metadata](/field-notes/nimble-snapshot-metadata-pre-shrink-investigation/)
- [Part 3: The Script Said Success. What Did the Array Say?](/posts/decommissioning-beyond-kubernetes/verified-cleanup/)
