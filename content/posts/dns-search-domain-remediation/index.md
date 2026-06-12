+++
title = 'Removing DNS Search Domain Drift Across Multi-Site RKE2 Clusters'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'A production walkthrough of auditing, diagnosing, and remediating DNS search domain drift across five RKE2 cluster sites, including netplan staging, systemd-resolved link-level debugging, and a Subiquity YAML indentation trap.'
tags = ['dns', 'netplan', 'systemd-resolved', 'ansible', 'rke2', 'kubernetes', 'sre']
categories = ['notes']
+++

RKE2 clusters across five sites had DNS search domains leaking into Kubernetes name resolution. Hostnames that should have resolved as-is were getting suffix expansion, and the behavior was inconsistent across data centers.

The fix required understanding which layer was injecting the search domain — and it was not always the same layer.

This post covers the audit, the diagnostics, the remediation script, and the edge cases that made it interesting.

## The Audit

The desired state was simple: netplan should have `search: []`, and the active resolver should show `.` (which means no search domain in systemd-resolved).

The first step was to audit every node across all sites, comparing the netplan config against the active resolver state:

```bash
OUT="dns-search-audit-$(date +%Y%m%d-%H%M%S).csv"
echo 'inventory_host,actual_hostname,resolv_conf_search,netplan_search' > "$OUT"
ANSIBLE_NOCOLOR=1 \
ANSIBLE_STDOUT_CALLBACK=default \
ANSIBLE_HOST_KEY_CHECKING=False \
ansible all \
  -i inventory/prod.yaml \
  -u operator -b -kK \
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
column -s, -t "$OUT"
```

The output revealed three distinct patterns:

| Pattern | Sites | `resolv_conf_search` | `netplan_search` |
|---|---|---|---|
| Already clean | Site-A | `.` | `[]` |
| Staged but not applied | Site-B, Site-D | `internal.corp.example` | `[]` |
| Dynamic link-level injection | Site-C | `dc.corp.example` | `NONE` |

Sites B and D had already been "fixed" — the netplan files had `search: []` — but the change had never been applied. The active resolver was still serving the old search domain.

Site C was different. `netplan_search` showed `NONE`, meaning netplan was not the source. The domain was being injected somewhere else.

## The Netplan Remediation Playbook

For sites where netplan was the authority, the fix was straightforward. The playbook backed up existing netplan files, ensured `search: []` was present, and staged the config:

```yaml
- name: Back up existing netplan files
  copy:
    src: "{{ item }}"
    dest: "{{ backup_dir }}/"
    remote_src: yes
  loop: "{{ query('file_glob', '/etc/netplan/*.yaml') + query('file_glob', '/etc/netplan/*.yml') }}"

- name: Set DNS search to empty in netplan
  ansible.builtin.lineinfile:
    path: "{{ item }}"
    regexp: '^\s+search:'
    line: '      search: []'
  loop: "{{ query('file_glob', '/etc/netplan/*.yaml') + query('file_glob', '/etc/netplan/*.yml') }}"
```

Key production decision: the playbook ran `netplan generate` to validate, but did **not** run `netplan apply`. Applying was deferred to a maintenance window, keeping the runtime resolver unchanged until a controlled rollout.

### Drift Detection

After staging, a quick awk filter identified remaining drift:

```bash
awk -F, 'NR==1 || $3!="." || $4!="[]"' "$OUT" | column -s, -t
```

Drift showing `internal.corp.example` / `[]` was expected — netplan was clean, runtime was stale. That was the staging signal.

## The Site-C Puzzle: Link-Level DNS Injection

Site C did not respond to any netplan changes because netplan was never the source. The audit showed:

```text
netplan_search = NONE
resolv_conf_search = dc.corp.example
```

Initial attempts to clear the domain at runtime failed:

```bash
# This did NOT work
resolvectl domain ""
systemctl restart systemd-resolved
```

The search domain came back every time. Restarting systemd-resolved re-read the link-level config and reapplied the domain.

### The Diagnosis

Inspecting the resolver state revealed the source:

```bash
resolvectl domain
```

Output:

```text
Global:
Link 2 (eth0): dc.corp.example
```

The domain was on **Link 2 (eth0)**, not in the global scope. It was being injected at the interface level, probably via DHCP or systemd-networkd.

The fix was per-interface:

```bash
resolvectl domain eth0 ""
```

And crucially: **do not restart systemd-resolved afterward**. Restarting re-reads the link config and reapplies the domain.

### The Production Run

The runtime fix for Site C, scoped to exclude worker nodes:

```bash
ANSIBLE_NOCOLOR=1 \
ANSIBLE_STDOUT_CALLBACK=default \
ansible 'site-c_prod_rke2:!site-c_prod_rke2_wrkr' \
  -i inventory/prod.yaml \
  -u operator -b -kK \
  -m shell -a '
set -e
echo "Before:"
resolvectl domain
grep "^search" /etc/resolv.conf || echo "no search line"
resolvectl domain eth0 ""
sleep 1
echo "After:"
resolvectl domain
grep "^search" /etc/resolv.conf || echo "no search line"
'
```

The critical detail: `set -e` and `set -u` are safe in Ansible's `/bin/sh`, but `set -o pipefail` is not — `/bin/sh` on Ubuntu rejects it silently.

## The Production Maintenance Window

Site D was remediated during a fifteen-minute maintenance window. The script had a bug: it used `set -o pipefail` at the top, which worked fine in local Bash but failed when Ansible executed it remotely via `/bin/sh`.

The error was cryptic:

```text
/bin/sh: 2: set: Illegal option -o pipefail
```

Fix: change `set -euo pipefail` to `set -eu` inside Ansible shell tasks. Keep `set -euo pipefail` only in the local script wrapper.

After the fix, the remediation ran cleanly:

```text
== Drift remaining ==
inventory_host actual_hostname resolv_conf_search netplan_search resolv_conf_type
```

Header only — no drift. All nodes across Site D now showed `.` / `[]`.

## The Subiquity YAML Trap

During the Site-E audit, a precheck failed on all Longhorn nodes:

```bash
sudo netplan generate
```

Failed with a YAML error. The offending file:

```yaml
network:
  ethernets:
    ens160:
      addresses:
        - 192.0.2.15/24
      gateway4: 192.0.2.1
      nameservers:
        addresses:
          - 198.51.100.2
          - 198.51.100.3
      search: []
  version: 2
```

The `search: []` line was misaligned — indented at the `nameservers` level but not nested under it. This is a known behavior of Subiquity (the Ubuntu Server installer): it sometimes writes `search:` with inconsistent indentation.

The fix:

```bash
cp -a /etc/netplan/00-installer-config.yaml /etc/netplan/00-installer-config.yaml.bak.$(date +%s)
python3 - <<PY
from pathlib import Path
p = Path("/etc/netplan/00-installer-config.yaml")
text = p.read_text()
text = text.replace("\nsearch:", "\n      search:")
p.write_text(text)
PY
netplan generate
```

The same indentation bug had appeared earlier on other sites — it is worth adding a YAML normalization step to any netplan automation that runs across Subiquity-provisioned nodes.

## The Three-Layer Model

The most useful mental model from this work is that DNS search domains on Ubuntu with systemd-resolved come from three independent layers:

| Layer | Inspect With | Source |
|---|---|---|
| Netplan (static) | `netplan get`, `grep search: /etc/netplan/*.yaml` | Static config |
| systemd-resolved (global) | `resolvectl domain` (Global section) | `resolvectl domain ""` |
| systemd-resolved (per-link) | `resolvectl domain` (Link sections) | DHCP, systemd-networkd |

A fix that clears the wrong layer will appear to work but will not survive a reboot or service restart.

## Key Takeaways

1. **Audit before acting.** Without the CSV audit, we would have assumed all sites had the same root cause. They did not.

2. **`search .` means no search domain.** This is systemd-resolved behavior, not a bug. Do not try to "fix" it.

3. **Do not manually edit `/etc/resolv.conf` when it is a symlink.** On modern Ubuntu, it points to `/run/systemd/resolve/stub-resolv.conf`. Changes will be overwritten.

4. **`set -o pipefail` breaks Ansible shell tasks.** `/bin/sh` on Ubuntu does not support it. Use `set -eu` inside remote commands.

5. **Subiquity writes inconsistent YAML.** If a `netplan generate` precheck fails after a fresh Ubuntu install, check the indentation of `search:`.

6. **Stage configs, defer application.** Running `netplan generate` validates the config without disrupting the runtime resolver. Apply during a maintenance window.

7. **Count patterns, not nodes.** The awk command `awk -F, 'NR>1 {print $3 "|" $4}' "$OUT" | sort | uniq -c | sort -nr` quickly shows how many distinct resolver states exist in the fleet.
