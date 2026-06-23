+++
title = 'DNS Search Remediation With Per-Cluster Ansible Inventory'
date = 2026-06-22T00:00:00-05:00
draft = false
description = 'Field note for hardening a DNS search-domain remediation wrapper so it handles per-cluster inventories, Vault-backed Ansible variables, local credentials, and incomplete final audits.'
tags = ['dns', 'ansible', 'rke2', 'inventory', 'systemd-resolved', 'operations']
categories = ['field-notes']
+++

A DNS remediation script that works for environment-wide inventory can break when the workflow moves to per-cluster inventory files.

The script needs to solve four separate problems:

- target the right Ansible group.
- name audit output correctly.
- avoid local Vault dependencies during password-based testing.
- report incomplete final audits instead of pretending the cluster is clean.

## Per-Cluster Targeting

If the command accepts either an environment or an inventory path, parse the second argument carefully:

```bash
./scripts/fix-dns-search-domain.sh --audit-only site-a ./ansible/inventory/site-a-ops-rke2.yaml
```

For that input, derive:

```text
inventory:  /repo/ansible/inventory/site-a-ops-rke2.yaml
group:      site_a_ops_rke2
audit file: dns-search-audit-site-a-ops-rke2-<timestamp>.csv
```

Do not generate duplicate site names in the audit filename, and do not target the old environment group by accident.

## Vault-Backed Inventory Variables

Ansible inventory may define credentials through Vault-backed group vars:

```yaml
ansible_user: "{{ _vault_node_ssh.secret.username }}"
ansible_password: "{{ _vault_node_ssh.secret.password }}"
ansible_become_password: "{{ ansible_password }}"
```

That is fine in AWX or a fully prepared operator shell, but it can break a local wrapper if the Python environment does not have the Vault client libraries installed.

For a local password-based remediation wrapper, collect credentials directly and pass them as high-precedence extra vars:

```bash
read -rsp 'SSH password: ' SSH_PASSWORD
read -rsp 'BECOME password[defaults to SSH password]: ' BECOME_PASSWORD
```

Write a temporary extra-vars file with restrictive permissions:

```bash
credentials_file=$(mktemp)
chmod 600 "$credentials_file"
```

Quote YAML values because passwords can contain punctuation:

```bash
  local value="$1"
  value=${value//\'/\'\'}
  printf "'%s'" "$value"
}
```

Then pass the file to Ansible:

```bash
ansible "$GROUP" \
  -i "$INVENTORY" \
  -u "$SSH_USER" \
  -b \
  -e "@$credentials_file" \
  -m shell \
  -a '<audit or remediation command>'
```

Remove the file on exit:

```bash
trap 'rm -f "$credentials_file"' EXIT
```

## Remediation Shape

For resolver search-domain drift where netplan has no search entry but systemd-resolved still exposes one, remediation should clear resolved domains explicitly:

```text
/etc/systemd/resolved.conf.d/99-clear-search-domains.conf
Domains=
```

Then restart `systemd-resolved`, apply or generate netplan as appropriate, and audit again.

Expected clean state:

```text
resolv_conf_search: .
netplan_search: [] or NONE, depending file presence
resolv_conf_type: symlink:/run/systemd/resolve/stub-resolv.conf
```

## Final Audit Can Hang

After remediation, a second full audit may stall on one host. That does not always mean remediation is still running.

Check whether the script already reached final audit:

```text
== Final audit ==
```

If so, the mutating phase is done and the current Ansible process is only collecting evidence.

If interrupted, the audit should still report the partial result:

```text
WARNING: ansible audit command exited with status 99
WARNING: audited 10 of 11 hosts. Check warnings/failures above.
```

That row-count guardrail matters. Ten clean rows out of eleven is not a clean cluster.

## NotReady Nodes

If one host is missing from the final audit, compare with Kubernetes readiness:

```bash
kubectl --context site-a-ops-rke2 get nodes -o wide
```

A NotReady node may still be present in inventory and targeted by Ansible. Keep it visible, but do not let it block interpretation of reachable hosts.

Recommended follow-up:

```bash
kubectl describe node site-a-worker-2
kubectl get node site-a-worker-2 -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'
```

## Operating Rule

DNS remediation is not complete until the final audit covers every targeted host.

If a host is unreachable or NotReady, record the partial success, isolate the missing host, and rerun audit with an explicit limit or after node recovery.
