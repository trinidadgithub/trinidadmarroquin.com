+++
title = 'Calico IP Audit Zero Targets Does Not Mean Zero Nodes'
date = 2026-06-22T00:00:00-05:00
draft = false
description = 'Field note for interpreting Calico node IP audit scripts that only print mismatches, and for confirming whether Kubernetes node InternalIP matches projectcalico.org/IPv4Address.'
tags = ['calico', 'kubernetes', 'rke2', 'networking', 'audit', 'operations']
categories = ['field-notes']
+++

An audit script can find contexts and still print zero rows. That may be success, not a parser failure.

For Calico node IP audits, many scripts intentionally emit only mismatches between a Kubernetes node's `InternalIP` and the Calico node annotation:

```text
projectcalico.org/IPv4Address
```

If there are no mismatches, the target files can be empty.

## Symptom

The audit finds contexts:

```text
Contexts: site-a-ops-rke2 site-a-prod-rke2 site-a-uat-rke2
```

But reports zero targets:

```text
Counts for DC=site-a:
all: 0
prod: 0
uat: 0
qa: 0
dev: 0
unknown: 0
```

Before assuming the node query broke, inspect the selection logic.

## Common Mismatch Filter

The script may only print rows matching this condition:

```jq
.calico != "" and (.calico | split("/")[0]) != .nodeIP
```

That means it ignores:

- nodes with no Calico IPv4 annotation.
- nodes where the Calico IPv4 host portion matches the Kubernetes InternalIP.

So `0` can mean:

```text
no remediation targets
```

not:

```text
no nodes checked
```

## Confirm The Raw Node Data

Use a direct query to print every node:

```bash
kubectl --context site-a-ops-rke2 get nodes -o json \
  | jq -r '.items[]
      | [
          .metadata.name,
          (.status.addresses[]? | select(.type == "InternalIP") | .address),
          (.metadata.annotations["projectcalico.org/IPv4Address"] // "NONE"),
          (.metadata.annotations["projectcalico.org/IPv4VXLANTunnelAddr"] // "NONE")
        ]
      | @tsv' \
  | column -t
```

Healthy shape:

```text
node-a  192.0.2.10  192.0.2.10/24  192.0.2.50
node-b  192.0.2.11  192.0.2.11/24  192.0.2.51
```

The host portion of `projectcalico.org/IPv4Address` matches `InternalIP`.

## When It Is A Problem

Investigate if you see:

```text
node-a  192.0.2.10  198.51.100.10/24
```

That means Calico selected a different interface or subnet than Kubernetes considers the node InternalIP.

Typical remediation is not to patch every node annotation by hand. Prefer fixing the Tigera `Installation` autodetection policy so Calico selects the intended CIDR, then restart or roll the affected Calico components according to the platform runbook.

## Improve Audit Output

Mismatch-only scripts are useful for automation, but confusing for humans. Add an optional verbose mode that prints all checked nodes with status:

```text
MATCH
MISMATCH
MISSING_ANNOTATION
UNREACHABLE_CONTEXT
```

Example output:

```text
context          node     internal_ip  calico_ipv4     status
site-a-ops-rke2  node-a   192.0.2.10   192.0.2.10/24   MATCH
site-a-ops-rke2  node-b   192.0.2.11   198.51.100.10   MISMATCH
```

That keeps machine-readable target files small while giving operators confidence that the audit actually checked nodes.

## Operating Rule

For mismatch-only audits, `zero targets` is not enough evidence by itself.

Confirm at least once that contexts are reachable and raw node annotations match the intended relationship:

```text
Kubernetes InternalIP == Calico IPv4Address host portion
```
