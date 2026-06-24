+++
title = 'DNS Drift Detector Calico Overlay False Positives'
date = 2026-06-24T00:00:00-05:00
draft = false
description = 'Field note for filtering Calico overlay links from resolvectl domain output and parsing DNS drift detector CSV reports safely.'
tags = ['dns', 'calico', 'ansible', 'kubernetes', 'rke2', 'audit', 'operations']
categories = ['field-notes']
+++

DNS drift detectors need to distinguish resolver search domains from interface names.

On Kubernetes nodes using Calico, `resolvectl domain` can include link names such as:

```text
Link 3 (caliabc123):
Link 5 (vxlan.calico):
```

Those strings can look domain-like to a naive regex. If the detector treats `vxlan.calico` as an active DNS search domain, clean nodes appear drifted.

## Symptom

The DNS audit shows expected resolver state:

```text
resolv_conf_search = .
netplan_search     = []
resolv_conf_type   = symlink:/run/systemd/resolve/stub-resolv.conf
```

But the detector still marks nodes as drift because `resolved_domains` includes Calico overlay links.

## Filter Overlay Links Before Drift Classification

Filter Calico link lines from `resolvectl domain` before extracting domains:

```bash
RESOLVED_DOMAINS=$(resolvectl domain 2>/dev/null \
  | grep -Ev '^Link [0-9]+ \((cali[^)]*|vxlan\.calico)\):' \
  | sed -E 's/^Global:[[:space:]]*//; s/^Link [0-9]+ \([^)]*\):[[:space:]]*//' \
  | grep -v '^[[:space:]]*$' \
  | tr '\n' ' ' \
  | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')

[ -z "$RESOLVED_DOMAINS" ] && RESOLVED_DOMAINS="NONE"
```

The key is filtering by link name before evaluating whether a remaining value is a real search domain.

## Do Not Parse CSV With `awk -F,`

If the report stores fields like `resolved_domains`, commas or quoted values can break naive parsing.

Avoid this:

```bash
awk -F, '$7 == "drift"' report.csv
```

Use a CSV parser and emit tab-separated output for display:

```bash
python3 - "$OUTPUT_FILE" <<'PY' | column -t -s $'\t'
import csv
import sys

with open(sys.argv[1], newline='', encoding='utf-8') as report:
    reader = csv.reader(report)
    header = next(reader, None)
    if header:
        print('\t'.join(header))
    for row in reader:
        if len(row) >= 7 and row[6] == 'drift':
            print('\t'.join(row))
PY
```

## Suppress Successful Ansible Noise

If the detector captures raw Ansible output, do not print normal success lines as warnings:

```bash
grep -v 'DNS_DRIFT|' "$AUDIT_RAW" \
  | grep -vE '^[^|]+ \| (CHANGED|SUCCESS) \| rc=0 >>$' \
  > "$WARNINGS" || true
```

Warnings should mean something operators need to read.

## Validate The Fix

Run syntax checks:

```bash
bash -n dns-drift-detector.sh
```

If the detector runs in a container, rebuild the local image:

```bash
docker build -t dns-drift-detector:local dns-drift-detector
```

Then run the same inventory audit again:

```bash
docker run --rm \
  -v "$PWD/ansible/inventory/site-a-ops-rke2.yaml:/inventory/inventory.yaml:ro" \
  -v "$PWD/dns-drift-detector/reports:/reports" \
  -v "$HOME/.ssh:/ssh:ro" \
  -e SSH_USER=operator \
  -e ANSIBLE_EXTRA_ARGS='--private-key /ssh/id_rsa' \
  dns-drift-detector:local \
  --inventory /inventory/inventory.yaml \
  --group site_a_ops_rke2
```

Expected result:

```text
resolved_domains = NONE
status           = clean
Drift remaining  = header only
```

## Operating Rule

Audit tools should ignore infrastructure interface names before classifying DNS drift.

Calico overlay links are evidence about networking, not resolver search domains.
