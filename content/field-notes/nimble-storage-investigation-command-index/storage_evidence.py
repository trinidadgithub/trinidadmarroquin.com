#!/usr/bin/env python3
"""Analyze saved Nimble CLI listings and cleanup journals. No remote operations."""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PVC = re.compile(r"pvc-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
STAMP = re.compile(r"(\d{4}-\d{2}-\d{2}::\d{2}:\d{2}:\d{2}\.\d+)$")


def text(path):
    value = Path(path).read_text(encoding="utf-8")
    if not value.strip() or re.search(r"(?im)^\s*(ERROR:|Permission denied)", value):
        raise ValueError(f"{path}: empty capture or error response")
    return value


def listing(path):
    raw = text(path)
    if not re.search(r"Name\s+Size\s+Online", raw) or "(MiB)" not in raw:
        raise ValueError(f"{path}: expected vol --list header with MiB units")
    result = {}
    for line in raw.splitlines():
        if not line.lstrip().startswith("pvc-"):
            continue
        fields = line.split()
        if (len(fields) != 8 or not PVC.fullmatch(fields[0])
                or fields[2] not in {"Yes", "No"}
                or any(not fields[i].isdigit() for i in (1, 4, 5, 6))):
            raise ValueError(f"{path}: malformed/wrapped PVC row: {line}")
        name = fields[0]
        if name in result:
            raise ValueError(f"{path}: duplicate volume {name}")
        result[name] = dict(size_mib=int(fields[1]), usage_mib=int(fields[4]),
                            online=fields[2], offline_reason=fields[3])
    return result


def inventory(path):
    volumes = listing(path)
    groups = {}
    for label, state in (("online", "Yes"), ("offline", "No"), ("total", None)):
        rows = [v for v in volumes.values() if state is None or v["online"] == state]
        groups[label] = {"count": len(rows)}
        for metric in ("size", "usage"):
            mib = sum(v[f"{metric}_mib"] for v in rows)
            groups[label].update({f"{metric}_mib": mib,
                                  f"{metric}_gib": mib / 1024,
                                  f"{metric}_tib": mib / 1048576})
    return {"summary": groups, "volumes": volumes}


def names(path):
    values = [line.strip() for line in text(path).splitlines() if line.strip()]
    if any(not PVC.fullmatch(name) for name in values) or len(set(values)) != len(values):
        raise ValueError(f"{path}: invalid or duplicate PVC name")
    return set(values)


def journals(paths):
    events = Counter()
    successes, missing, intents = set(), set(), set()
    per_file = {}
    required = {"timestamp_utc", "action", "volume", "result", "detail"}
    for path in paths:
        text(path)
        file_successes = set()
        with Path(path).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames is None or set(reader.fieldnames) != required or len(reader.fieldnames) != 5:
                raise ValueError(f"{path}: unexpected journal schema")
            for number, row in enumerate(reader, 2):
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"{path}:{number}: incomplete/extra CSV fields")
                if not row["action"] or not row["result"]:
                    raise ValueError(f"{path}:{number}: missing action/result")
                datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
                name, action, outcome = row["volume"], row["action"], row["result"]
                # Historical halt records may have no per-volume identifier.
                if not PVC.fullmatch(name) and not (action == "batch" and not name):
                    raise ValueError(f"{path}:{number}: invalid volume identifier")
                events[f"{action},{outcome}"] += 1
                if (action, outcome) == ("delete", "success"):
                    successes.add(name)
                    file_successes.add(name)
                if (action, outcome) == ("check", "missing"):
                    missing.add(name)
                if (action, outcome) == ("delete_intent", "started"):
                    intents.add(name)
        per_file[str(path)] = file_successes
    overlaps = {}
    for left, a in per_file.items():
        for right, b in per_file.items():
            if left < right and a & b:
                overlaps[f"{left} | {right}"] = sorted(a & b)
    return {"events": dict(events), "unique_successes": sorted(successes),
            "missing_with_prior_or_other_success": sorted(missing & successes),
            "missing_without_success": sorted(missing - successes),
            "intents_without_any_success": sorted(intents - successes),
            "success_overlap_between_files": overlaps}


def snapshots(path, volume):
    raw = text(path)
    if "Snapshot" not in raw or "Online" not in raw or "(MiB)" not in raw:
        raise ValueError(f"{path}: expected snap --list header")
    states, statuses, seen, stamps = Counter(), Counter(), set(), []
    for line in raw.splitlines():
        if not line.lstrip().startswith("pvc-"):
            continue
        fields = line.split()
        if (len(fields) != 7 or fields[0] != volume or fields[3] not in {"Yes", "No"}
                or not fields[2].isdigit() or not fields[5].isdigit()):
            raise ValueError(f"{path}: malformed/wrong-volume snapshot row: {line}")
        name = fields[1]
        if name in seen:
            raise ValueError(f"{path}: duplicate snapshot {name}")
        seen.add(name)
        states[fields[3]] += 1
        statuses[fields[4]] += 1
        match = STAMP.search(name)
        if match:
            stamps.append(datetime.strptime(match[1], "%Y-%m-%d::%H:%M:%S.%f"))
    stamps.sort()
    intervals = [(b - a).total_seconds() for a, b in zip(stamps, stamps[1:])]
    return {"count": len(seen), "online_states": dict(states), "statuses": dict(statuses),
            "timestamped_names": len(stamps), "names_without_timestamp": len(seen) - len(stamps),
            "earliest_name_timestamp": stamps[0].isoformat() if stamps else None,
            "latest_name_timestamp": stamps[-1].isoformat() if stamps else None,
            "adjacent_intervals_seconds": intervals,
            "adjacent_intervals_at_most_2_seconds": sum(v <= 2 for v in intervals)}


def reconcile(args):
    original, final, approved = set(listing(args.original)), set(listing(args.final)), names(args.approved)
    audit = journals(args.journals)
    successful = set(audit["unique_successes"])
    return {"original_count": len(original), "final_count": len(final),
            "original_names_absent": sorted(original - final),
            "new_names_in_final": sorted(final - original),
            "approved_still_present": sorted(approved & final),
            "approved_outside_original": sorted(approved - original),
            "successes_still_present": sorted(successful & final),
            "successes_outside_approved": sorted(successful - approved),
            "absent_original_without_success": sorted((original - final) - successful),
            "approved_absent_without_success": sorted((approved - final) - successful),
            "journal_analysis": audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("inventory", help="classify saved vol --list output")
    p.add_argument("listing")
    p = commands.add_parser("snapshots", help="summarize saved snap --list output and name timestamps")
    p.add_argument("listing")
    p.add_argument("--volume", required=True)
    p = commands.add_parser("journals", help="count events and compare unique success/missing sets")
    p.add_argument("journals", nargs="+")
    p = commands.add_parser("reconcile", help="compare inventories, approved names, and journals")
    p.add_argument("--original", required=True)
    p.add_argument("--final", required=True)
    p.add_argument("--approved", required=True)
    p.add_argument("journals", nargs="+")
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            result = inventory(args.listing)
        elif args.command == "snapshots":
            if not PVC.fullmatch(args.volume):
                raise ValueError("invalid --volume identifier")
            result = snapshots(args.listing, args.volume)
        elif args.command == "journals":
            result = journals(args.journals)
        else:
            result = reconcile(args)
        json.dump(result, sys.stdout, indent=2)
        print()
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
