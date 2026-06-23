+++
title = 'RKE2 Per-Cluster Inventory Generation From Kubeconfig'
date = 2026-06-22T00:00:00-05:00
draft = false
description = 'Field note for generating repo-compatible Ansible inventory from RKE2 kubeconfig contexts, including group names, API load balancers, node readiness, and test fixtures.'
tags = ['ansible', 'kubernetes', 'rke2', 'inventory', 'automation', 'operations']
categories = ['field-notes']
+++

Inventory generation is only useful if the output matches the repo's actual inventory contract.

A script can successfully read `kubectl get nodes` and still generate inventory that the playbooks cannot use. The important details are usually group names, expected child groups, node roles, load balancer entries, and local conventions around readiness metadata.

## Problem

A per-cluster RKE2 inventory workflow needed output like:

```text
site_a_ops_rke2
rke2_servers
rke2_agents
api_lb
```

But the generator output did not match the checked-in inventory shape. Common breaks included:

- kube context names with dashes where Ansible group vars expected underscores.
- missing `rke2_servers` and `rke2_agents` groups.
- missing API load balancer inventory entries.
- missing or inconsistent `rke2_node_ready` values.
- requiring explicit kubeconfig and environment flags even when the output filename already identified the target.

## Inputs

Use Kubernetes as the live source for nodes:

```bash
kubectl --context site-a-ops-rke2 get nodes -o wide
```

Extract the facts the inventory actually needs:

```text
node name
internal IP
Kubernetes roles
Ready or NotReady condition
cluster/context name
environment inferred from output path or context
```

## Output Contract

For a per-cluster inventory, generate stable groups first:

```yaml
all:
  children:
    site_a_ops_rke2:
      children:
        rke2_servers:
        rke2_agents:
        api_lb:
```

Then classify nodes by role:

```text
control-plane / master / etcd -> rke2_servers
worker                         -> rke2_agents
API load balancers             -> api_lb
```

Include readiness as metadata, not as a reason to silently omit the node:

```yaml
site-a-worker-2:
  ansible_host: 192.0.2.20
  rke2_node_ready: false
```

That lets downstream tasks decide whether to skip, remediate, or alert.

## Filename-Based Inference

If the caller writes to a per-cluster inventory path, infer what can be safely inferred:

```bash
./ansible/generate-inventory.sh \
  ~/.kube/config \
  --output ansible/inventory/site-a-ops-rke2.yaml
```

The script can derive:

```text
context:     site-a-ops-rke2
group name:  site_a_ops_rke2
environment: ops
```

Do not require redundant flags unless ambiguity remains.

## Test With A Fake kubectl

Inventory generators should have tests because small formatting changes break downstream playbooks.

A simple fixture pattern:

```bash
TMPDIR=$(mktemp -d)
mkdir -p "$TMPDIR/bin"

cat > "$TMPDIR/bin/kubectl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  *"config get-contexts"*)
    printf 'site-a-ops-rke2\n'
    ;;
  *"get nodes"*)
    cat ./testdata/nodes-site-a-ops.json
    ;;
  *)
    exit 1
    ;;
esac
EOF

chmod +x "$TMPDIR/bin/kubectl"
PATH="$TMPDIR/bin:$PATH" ./ansible/generate-inventory.sh --output /tmp/site-a-ops-rke2.yaml
```

Then assert the output contains required groups and fields:

```bash
grep -q 'site_a_ops_rke2:' /tmp/site-a-ops-rke2.yaml
grep -q 'rke2_servers:' /tmp/site-a-ops-rke2.yaml
grep -q 'rke2_agents:' /tmp/site-a-ops-rke2.yaml
grep -q 'api_lb:' /tmp/site-a-ops-rke2.yaml
grep -q 'rke2_node_ready:' /tmp/site-a-ops-rke2.yaml
```

## Validation

After generation, validate Ansible can parse the file:

```bash
ansible-inventory -i ansible/inventory/site-a-ops-rke2.yaml --graph
```

Then verify host counts against Kubernetes:

```bash
kubectl --context site-a-ops-rke2 get nodes --no-headers | wc -l
ansible site_a_ops_rke2 -i ansible/inventory/site-a-ops-rke2.yaml --list-hosts
```

The counts do not need to match if inventory includes API load balancers, but the difference should be explainable.

## Operating Rule

Do not generate inventory as a loose YAML export.

Generate the exact shape expected by playbooks and `group_vars`, test that shape with a fake `kubectl`, and keep NotReady nodes visible as inventory facts instead of hiding them.
