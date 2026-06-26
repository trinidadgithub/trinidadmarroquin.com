+++
title = 'Remediation Audits With NotReady Nodes And Calico Checks'
date = 2026-06-26T00:00:00-05:00
draft = false
description = 'Field note for running node remediation safely when inventory generation, DNS cleanup, Calico IP audits, and a NotReady node overlap.'
tags = ['kubernetes', 'rke2', 'calico', 'ansible', 'inventory', 'notready', 'operations']
categories = ['field-notes']
+++

Node remediation scripts often fail in boring ways: wrong inventory group, hidden Vault dependency, or one unreachable node that makes the final audit look stuck. Those failures matter because they can turn a clean remediation into a false incident, or worse, hide the one node that still needs attention.

Use this workflow when cleaning Kubernetes node drift across a whole RKE2 cluster and validating Calico state at the same time.

## Start With A Per-Cluster Inventory

The remediation target should be the cluster group, not a hand-written list of hosts. Generate inventory from the kubeconfig so the source of truth is Kubernetes node state:

```bash
./generate-inventory.sh \
  --kubeconfig ~/.kube/config \
  --environment cluster-a-prod \
  --output inventory/cluster-a-prod.yaml
```

The generated inventory should preserve enough runtime facts to help operators interpret remediation output:

```yaml
all:
  children:
    cluster_a_prod:

rke2_servers:
  children:
    etcd:
    mstr:

rke2_agents:
  children:
    wrkr:

cluster_a_prod:
  children:
    wrkr:
      hosts:
        worker-1:
          ansible_host: 192.0.2.10
          rke2_node_ready: true
        worker-2:
          ansible_host: 192.0.2.11
          rke2_node_ready: false
```

`rke2_node_ready` is not a fix by itself. It is evidence. It tells the person reading Ansible output that a missing or slow host may already be unhealthy from Kubernetes' point of view.

## Verify The Target Group

A common failure is targeting the Kubernetes context name when Ansible inventory normalized the group name.

Bad signal:

```text
[WARNING]: Could not match supplied host pattern, ignoring: cluster-a-prod
[WARNING]: No hosts matched, nothing to do
```

Fix the wrapper or command so it resolves the inventory group name before running Ansible:

```bash
ansible-inventory -i inventory/cluster-a-prod.yaml --graph
```

Then run the remediation against the real group:

```bash
ansible cluster_a_prod \
  -i inventory/cluster-a-prod.yaml \
  -u ubuntu \
  -b \
  -m ping
```

Do not proceed until the target count matches expectations.

## Avoid Local Vault Lookup Failures

If ad-hoc Ansible uses `group_vars/all.yaml`, local credential lookups can fail before any remote host is touched:

```text
The lookup plugin 'community.hashi_vault.vault_kv2_get' failed to load
Failed to import the required Python library (hvac)
```

For emergency audits or remediation, pass explicit operator credentials or an override file rather than letting local workstation Vault dependencies decide whether the cluster can be checked:

```bash
ansible cluster_a_prod \
  -i inventory/cluster-a-prod.yaml \
  -u ubuntu \
  -b \
  -e ansible_user=ubuntu \
  -m shell \
  -a 'hostname -s'
```

This does not replace proper secret management. It keeps a local tooling gap from being misread as node remediation failure.

## Interpret A Hung Final Audit

After DNS or resolver cleanup, a final audit that appears stuck may not mean the script is broken. It may mean one host is unreachable while the others completed.

Useful checks:

```bash
ps -ef | grep '[a]nsible'

kubectl --context cluster-a-prod get nodes -o wide
```

If interrupted output says something like this, treat it as partial success:

```text
WARNING: audited 10 of 11 hosts. Check warnings/failures above.
```

Then compare with Kubernetes node state:

```text
NAME       STATUS     ROLES    INTERNAL-IP
worker-1   Ready      worker   192.0.2.10
worker-2   NotReady   worker   192.0.2.11
worker-3   Ready      worker   192.0.2.12
```

At that point the remediation result is not simply pass or fail. It is:

- 10 nodes remediated and audited.
- 1 node needs separate NodeNotReady triage.
- the final cluster declaration must wait until the missing node is recovered or explicitly excluded.

## Separate NodeNotReady From Remediation Drift

For the NotReady node, switch from cluster-wide remediation to node triage:

```bash
kubectl --context cluster-a-prod describe node worker-2

kubectl --context cluster-a-prod get events -A \
  --field-selector involvedObject.kind=Node,involvedObject.name=worker-2 \
  --sort-by=.lastTimestamp
```

On the node or through out-of-band access, check the local services:

```bash
sudo systemctl status rke2-agent --no-pager
sudo journalctl -u rke2-agent --since '1 hour ago'
sudo crictl ps
```

Common causes include kubelet/RKE2 agent failure, expired node certificates, host networking drift, disk pressure, or a node that is reachable by Kubernetes API metadata but not reachable by SSH.

Do not rerun broad remediation repeatedly until the NotReady node is understood. Repeated retries can hide which changes already succeeded.

## Run Calico Audits With Human Evidence

Calico IP audit scripts often emit only mismatches into remediation target files. That is good for automation, but weak for human confidence.

Use two outputs:

- mismatch-only files for remediation.
- all-node files for audit evidence.

Example command:

```bash
./audit-calico-ip.sh \
  --dc site-a \
  --ctx-regex '^(cluster-a-prod|cluster-a-uat|cluster-a-qa)$' \
  --show-all
```

The all-node report should include a status column:

```text
CONTEXT         NODE      NODE_INTERNAL_IP  CALICO_IPV4ADDRESS  STATUS
cluster-a-prod  worker-1  192.0.2.10        192.0.2.10/24       MATCH
cluster-a-prod  worker-2  192.0.2.11        198.51.100.11/24    MISMATCH
cluster-a-prod  worker-3  192.0.2.12        NONE                MISSING_ANNOTATION
cluster-a-qa    -         -                 -                   UNREACHABLE_CONTEXT
```

Keep existing automation files mismatch-only:

```text
calico-ip-audit/site-a/mismatches.tsv
calico-ip-audit/site-a/targets.tsv
calico-ip-audit/site-a/targets-prod.tsv
```

Add human evidence separately:

```text
calico-ip-audit/site-a/all-nodes.tsv
```

This prevents a clean audit from looking empty while preserving safe remediation inputs.

## Decision Rules

- `No hosts matched` means inventory targeting is wrong, not that drift is clean.
- Vault lookup errors are local execution failures until proven otherwise.
- `audited 10 of 11 hosts` is partial success and requires explicit accounting.
- `NotReady` nodes should stay visible in inventory and reports.
- Calico `0 targets` means no mismatches only if all-node evidence proves nodes were checked.
- Remediation should not patch Calico annotations one by one unless the platform runbook explicitly calls for that. Prefer fixing autodetection policy and rolling Calico components safely.

The operational goal is not just to change settings. It is to prove which nodes were targeted, which nodes changed, which nodes were skipped, and why.
