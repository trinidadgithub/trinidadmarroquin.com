+++
title = 'Replacement Node Workflow After Terraform Import Drift'
date = 2026-06-18T00:00:00-05:00
draft = false
description = 'Field note for deciding to replace Kubernetes nodes instead of applying risky vSphere drift after importing legacy VMs into Terraform state.'
tags = ['terraform', 'vsphere', 'kubernetes', 'rke2', 'drift', 'operations']
categories = ['field-notes']
+++

Importing existing vSphere VMs into Terraform can produce a clean source-of-truth checkpoint and still leave a plan that should not be applied.

That is common when legacy Kubernetes nodes were built from an older template or outside the current module conventions.

## Audit Checkpoint

A useful checkpoint looks like this:

```text
NetBox resources: no-op
vSphere resources: update
destroy actions: none
```

This means NetBox ownership is reconciled, but Terraform still sees vSphere drift.

## Drift That Should Trigger Caution

Do not treat `update in-place` as automatically safe.

For existing Kubernetes nodes, review drift such as:

- CPU hot-add changing state.
- memory hot-add changing state.
- datastore ID changes.
- network port group changes.
- imported VM markers changing.
- clone/customize metadata being added.
- cloud-init guestinfo metadata being added.
- timeout setting changes.
- disk label mismatches.
- disk add/remove mismatches.
- extra worker disks not modeled in the module.

Any of these can be manageable in isolation. Together, they are a sign that the VM shape does not match the module's intended lifecycle model.

## Decision

If the VM is a legacy old-template node, prefer replacement over in-place reconciliation.

Replacement is slower but safer:

```text
new VM gets current template and module shape
old VM remains untouched until workload is drained
cluster health is checked at each step
rollback is clearer
```

## Worker Node Sequence

Start with workers when possible.

```text
1. Provision replacement worker with Terraform.
2. Bootstrap OS and RKE2 prerequisites.
3. Join worker to the cluster.
4. Verify node Ready condition.
5. Verify CNI, kube-proxy, DNS, and storage behavior.
6. Cordon old worker.
7. Drain old worker.
8. Delete old node from Kubernetes.
9. Retire old VM and clean source-of-truth state.
10. Repeat one worker at a time.
```

Useful checks:

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide --field-selector spec.nodeName=worker-1
kubectl drain worker-1 --ignore-daemonsets --delete-emptydir-data
```

## Control-Plane And Etcd Sequence

Control-plane and etcd nodes need stricter sequencing.

Before each replacement:

```bash
kubectl get nodes
kubectl get --raw='/readyz?verbose'
```

Check etcd health using the platform's supported tooling.

Operational rules:

- replace one member at a time.
- preserve quorum.
- wait for the replacement to become healthy before touching the next node.
- do not reuse hostname or IP until old membership is safely removed.
- keep an etcd backup before membership work.

## Tool Boundaries

Use each tool for its layer:

- Terraform provisions the replacement VM and NetBox ownership.
- Ansible or bootstrap scripts prepare the OS and RKE2 configuration.
- Kubernetes handles cordon, drain, and node deletion.
- RKE2/etcd tooling handles control-plane membership checks.
- Rancher or the platform UI confirms final cluster visibility.

## Finish Criteria

For each replaced node:

```text
replacement node Ready
critical pods healthy
storage attach/mount works if applicable
old node drained
old node removed from Kubernetes
old VM retired
NetBox reflects current VM ownership
Terraform plan remains intentional
```

## Operating Rule

A drift audit is allowed to end with “do not apply.”

When Terraform reveals that legacy nodes do not match the current module shape, replacement-node lifecycle is often the safer reconciliation path.
