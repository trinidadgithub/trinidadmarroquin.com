+++
title = 'DNS Search Domain Audit Failure Visibility'
date = 2026-06-19T00:00:00-05:00
draft = false
description = 'Field note for making Ansible-based DNS search-domain audits report unreachable hosts, sudo failures, and CSV row-count mismatches instead of silently dropping nodes.'
tags = ['dns', 'ansible', 'audit', 'netplan', 'systemd-resolved', 'operations']
categories = ['field-notes']
+++

A DNS audit can select the right hosts and still produce a misleading report.

The failure mode is usually a pipeline like this:

```bash
ansible "$GROUP" ... \
  | sed -n 's/.*CSV|//p' \
  | awk -F'|' '{print $1 "," $2 "," $3 "," $4}' \
  >> "$OUT"
```

That captures successful `CSV|...` markers, but it hides everything else. If half the hosts fail SSH or sudo, the CSV simply has fewer rows. The audit looks clean only because failed hosts disappeared.

## Symptom

The host list is correct:

```text
hosts (13):
  cluster-a-cp-1
  cluster-a-cp-2
  cluster-a-cp-3
  cluster-a-worker-1
  ...
  cluster-a-worker-10
```

But the audit CSV has fewer data rows:

```text
targeted hosts: 13
csv rows:       6
```

That is not partial success. That is an incomplete audit.

## Fix The Pipeline

Capture raw Ansible output first:

```bash
AUDIT_RAW="$(mktemp)"

set +e
ANSIBLE_NOCOLOR=1 \
ANSIBLE_STDOUT_CALLBACK=default \
ANSIBLE_HOST_KEY_CHECKING=False \
ansible "$GROUP" \
  -i "$INVENTORY" \
  -u "$ANSIBLE_USER" \
  -b -kK \
  -m shell -a '
ACTUAL_HOSTNAME=$(hostname -s)
RESOLV_SEARCH=$(awk "/^search/{\$1=\"\"; sub(/^ /,\"\"); print; exit} /^domain/{print \$2; exit}" /etc/resolv.conf)
[ -z "$RESOLV_SEARCH" ] && RESOLV_SEARCH="NONE"
NETPLAN_SEARCH=$(grep -R "search:" /etc/netplan/*.yaml /etc/netplan/*.yml 2>/dev/null | sed "s/.*search:[[:space:]]*//" | paste -sd ";" -)
[ -z "$NETPLAN_SEARCH" ] && NETPLAN_SEARCH="NONE"
if [ -L /etc/resolv.conf ]; then
  RESOLV_TYPE="symlink:$(readlink -f /etc/resolv.conf)"
else
  RESOLV_TYPE="static_file"
fi
printf "CSV|{{ inventory_hostname }}|%s|%s|%s|%s\n" "$ACTUAL_HOSTNAME" "$RESOLV_SEARCH" "$NETPLAN_SEARCH" "$RESOLV_TYPE"
' > "$AUDIT_RAW" 2>&1
AUDIT_RC=$?
set -e
```

Then parse CSV rows from the raw file:

```bash
sed -n 's/.*CSV|//p' "$AUDIT_RAW" \
  | awk -F'|' '{print $1 "," $2 "," $3 "," $4 "," $5}' \
  | sort -t, -k1,1 \
  >> "$OUT"
```

## Print Failures Explicitly

Do not discard the non-CSV output. Show it as audit evidence:

```bash
if grep -v 'CSV|' "$AUDIT_RAW" | grep -q '[^[:space:]]'; then
  echo
  echo "== Ansible warnings/failures =="
  grep -v 'CSV|' "$AUDIT_RAW"
fi
```

This exposes errors such as:

```text
UNREACHABLE! => Permission denied (publickey,password,keyboard-interactive)
Missing sudo password
Failed to connect to the host via ssh
```

## Compare Targeted Hosts To CSV Rows

Count targeted hosts before the audit:

```bash
TARGETED_HOSTS=$(ansible "$GROUP" -i "$INVENTORY" --list-hosts \
  | awk '/hosts \([0-9]+\):/ {gsub(/[():]/, "", $2); print $2}')
```

Count CSV data rows after the audit:

```bash
CSV_ROWS=$(awk 'NR > 1 {count++} END {print count + 0}' "$OUT")
```

Warn on mismatch:

```bash
if [ "$CSV_ROWS" -lt "$TARGETED_HOSTS" ]; then
  echo
  echo "WARNING: audit produced $CSV_ROWS CSV rows for $TARGETED_HOSTS targeted hosts"
  echo "Some hosts failed before returning DNS state. Treat this audit as incomplete."
fi
```

## Interpret SSH And Become Flags

For Ansible audit scripts, auth flags matter:

```text
-k  ask for SSH password
-K  ask for sudo/become password
-b  enable become/sudo
```

Useful combinations:

```text
password SSH + password sudo:       -b -kK
SSH key + password sudo:            -b -K
SSH key + passwordless sudo:        -b
```

If `-u ubuntu` appears ignored, check inventory or group variables for `ansible_user`. A group var can force the remote user unless explicitly overridden with an extra var:

```bash
ansible "$GROUP" -i "$INVENTORY" -e ansible_user=ubuntu -m ping
```

## Audit Finish Criteria

A DNS search-domain audit is complete only when:

```text
selected host count matches expected inventory
CSV data row count equals selected host count
raw Ansible output has no unreachable or failed hosts
drift output is reviewed after row-count validation
```

If the row count is short, fix SSH/bootstrap/sudo access first. Do not treat the DNS state as clean just because missing hosts did not write CSV rows.

Related: [DNS Search Remediation With Per-Cluster Ansible Inventory](/field-notes/dns-search-remediation-per-cluster-inventory/) covers per-cluster inventory arguments, local credential overrides for Vault-backed Ansible vars, and final-audit handling after remediation.
