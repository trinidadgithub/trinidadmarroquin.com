+++
title = 'DNS Search Domain Hygiene Across Multi-Site Clusters'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Operating pattern for maintaining consistent DNS search domain state across RKE2 clusters: audit, stage, runtime fix, and drift detection across three resolver layers.'
tags = ['dns', 'netplan', 'systemd-resolved', 'ansible', 'rke2', 'kubernetes']
categories = ['projects']
+++

RKE2 clusters across multiple sites had inconsistent DNS search domain behavior. Some nodes appended internal domains to all lookups, some appended data center-specific domains, and a few were clean. In a Kubernetes cluster, uncontrolled search domain expansion causes:

- Pod DNS lookups that should resolve as-is getting unexpected suffix expansion.
- Inconsistent behavior across sites for the same service name.
- Debugging sessions that waste time on DNS before finding the real issue.

## Desired State

| Layer | Target |
|---|---|
| Netplan | `search: []` |
| systemd-resolved | No per-link or global domains |
| Active resolver (`/etc/resolv.conf`) | `search .` |

`search .` is systemd-resolved shorthand for "no search domains" and is the correct end state.

## Operating Pattern

### 1. Audit

Run against all nodes to produce a CSV of current state:

```bash
./scripts/fix-dns-search.sh --audit-only <site> <env> <inventory>
```

Example output:

| `resolv_conf_search` | `netplan_search` | Meaning |
|---|---|---|
| `.` | `[]` | Clean |
| `internal.corp.example` | `[]` | Netplan staged, not applied |
| `dc.corp.example` | `NONE` | Link-level injection (DHCP/systemd-networkd) |

### 2. Stage

For netplan-managed nodes, validate configs without applying:

```bash
./scripts/fix-dns-search.sh --stage <site> <env> <inventory>
```

Uses `netplan generate` only — no runtime impact.

### 3. Runtime Fix (If Needed)

For nodes with per-link injection (netplan shows `NONE`):

```bash
resolvectl domain eth0 ""
```

Do not restart systemd-resolved afterward.

### 4. Apply (Maintenance Window)

```bash
./scripts/fix-dns-search.sh --apply <site> <env> <inventory>
```

### 5. Verify Drift

```bash
awk -F, 'NR==1 || $3!="." || $4!="[]"' <audit-csv> | column -s, -t
```

Header-only output = clean.

## Edge Cases Encountered

- **Subiquity YAML indentation**: Ubuntu installer sometimes writes `search:` at wrong indentation. Add a YAML normalization step to any netplan automation.
- **`set -o pipefail` in Ansible**: `/bin/sh` on Ubuntu does not support it. Use `set -eu` inside shell tasks.
- **stale `/etc/resolv.conf`** after netplan fix: If the file is a symlink to `stub-resolv.conf`, do not edit it directly. The change comes from systemd-resolved, not the file.

## Related

- [DNS Search Domain Debugging With systemd-resolved](/field-notes/dns-search-domain-debugging/) — field note with commands and troubleshooting flow.
