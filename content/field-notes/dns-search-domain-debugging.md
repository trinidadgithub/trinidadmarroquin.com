+++
title = 'DNS Search Domain Debugging With systemd-resolved'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Commands for identifying which layer is injecting a DNS search domain — netplan, systemd-resolved global, or per-link — and how to fix each at runtime.'
tags = ['dns', 'netplan', 'systemd-resolved', 'linux', 'kubernetes']
categories = ['field-notes']
+++

## Check Which Layer Is Injecting The Search Domain

```bash
# 1. Is /etc/resolv.conf managed by systemd-resolved?
ls -l /etc/resolv.conf
# Expected: /etc/resolv.conf -> /run/systemd/resolve/stub-resolv.conf

# 2. Show all search domains (global and per-link)
resolvectl domain
# Look for "Link <N> (<iface>): <domain>" — not just Global section

# 3. What does the active resolver actually show?
grep '^search' /etc/resolv.conf || echo "no search line"

# 4. Which interface is injecting the domain?
resolvectl domain | grep -B1 '\.'

# 5. Is DHCP the source?
networkctl status eth0 | grep -i domain
```

## The Three Layers

| Layer | Inspect With | Fix |
|---|---|---|
| Netplan | `grep -R "search:" /etc/netplan/` | Edit yaml, `netplan generate`, `netplan apply` |
| systemd-resolved (global) | `resolvectl domain` (Global:) | `resolvectl domain ""` |
| systemd-resolved (per-link) | `resolvectl domain` (Link N:) | `resolvectl domain eth0 ""` |

## Runtime Fix (Per-Link Domain)

Clearing a per-link search domain without restarting systemd-resolved:

```bash
sudo resolvectl domain eth0 ""
```

**Do not restart systemd-resolved after this.** Restarting re-reads the link config and reapplies the domain.

Safe alternative if you need to flush caches:

```bash
sudo resolvectl flush-caches
```

## Verify The Fix

```bash
resolvectl domain
cat /etc/resolv.conf
grep '^search' /etc/resolv.conf || echo "no search line"
```

Expected clean state:

```text
resolvectl domain -> (no domains listed)
/etc/resolv.conf   -> search .
```

`search .` is expected — it means "no search domain" in systemd-resolved.

## Netplan Inspection

```bash
# Show effective netplan config
sudo netplan get

# Find search domain in all netplan files
grep -R "search:" /etc/netplan/

# Validate without applying
sudo netplan generate
```

## Ansible Audit (CSV Output)

```bash
OUT="dns-search-audit-$(date +%Y%m%d-%H%M%S).csv"
echo 'inventory_host,actual_hostname,resolv_conf_search,netplan_search' > "$OUT"
ANSIBLE_NOCOLOR=1 \
ANSIBLE_STDOUT_CALLBACK=default \
ansible all -i inventory/prod.yaml -u operator -b -kK \
  -m shell -a '
ACTUAL_HOSTNAME=$(hostname -s)
RESOLV_SEARCH=$(awk "/^search/{\$1=\"\"; sub(/^ /,\"\"); print; exit} /^domain/{print \$2; exit}" /etc/resolv.conf)
[ -z "$RESOLV_SEARCH" ] && RESOLV_SEARCH="NONE"
NETPLAN_SEARCH=$(grep -R "search:" /etc/netplan/*.yaml /etc/netplan/*.yml 2>/dev/null | sed "s/.*search:[[:space:]]*//" | paste -sd ";" -)
[ -z "$NETPLAN_SEARCH" ] && NETPLAN_SEARCH="NONE"
printf "CSV|{{ inventory_hostname }}|%s|%s|%s\n" "$ACTUAL_HOSTNAME" "$RESOLV_SEARCH" "$NETPLAN_SEARCH"
' \
| sed -n 's/.*CSV|//p' \
| awk -F'|' '{print $1 "," $2 "," $3 "," $4}' \
| sort -t, -k1,1 \
>> "$OUT"
```

Do not rely on the CSV alone. If the pipeline only keeps `CSV|...` rows, failed or unreachable hosts are filtered out. Capture raw Ansible output, print non-CSV warnings/failures, and compare targeted host count to CSV data rows.

See [DNS Search Domain Audit Failure Visibility](/field-notes/dns-search-domain-audit-failure-visibility/) for the safer audit pattern.

## Drift Detection

Show anything not matching desired baseline (`.` / `[]`):

```bash
awk -F, 'NR==1 || $3!="." || $4!="[]"' "$OUT" | column -s, -t
```

Count distinct resolver patterns:

```bash
awk -F, 'NR>1 {print $3 "|" $4}' "$OUT" | sort | uniq -c | sort -nr
```

## Important Shell Detail

Ansible `shell` module runs under `/bin/sh` by default. `set -o pipefail` is not available on Ubuntu's `/bin/sh` and will fail silently or with:

```text
/bin/sh: 2: set: Illegal option -o pipefail
```

Use `set -eu` instead of `set -euo pipefail` inside Ansible shell tasks.

## Troubleshooting Flow

1. `grep '^search' /etc/resolv.conf` — observe the active value
2. `resolvectl domain` — check if it is global or per-link
3. `grep -R "search:" /etc/netplan/` — check netplan
4. `networkctl status eth0` — check DHCP domain injection
5. `resolvectl domain eth0 ""` — clear per-link at runtime (no restart)
6. `echo 'search .' | diff - /etc/resolv.conf` — confirm clean state
