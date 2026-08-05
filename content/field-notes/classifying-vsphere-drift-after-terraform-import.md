+++
title = 'Classifying vSphere Drift After Terraform Import'
date = 2026-06-17T00:00:00-05:00
draft = false
description = 'Field note for reading Terraform audit plans after importing existing vSphere VMs and deciding whether to reconcile drift or replace legacy nodes.'
tags = ['terraform', 'vsphere', 'kubernetes', 'drift', 'audit', 'operations']
categories = ['field-notes']
+++

After existing vSphere VMs are imported into Terraform state, expect drift.

The question is not whether drift exists. The question is whether applying that drift is safe.

## Generate The Audit Plan

```bash
terraform plan -out=audit.tfplan
terraform show -json audit.tfplan \
  | jq -r '.resource_changes[]? | [.address, .type, (.change.actions | join(","))] | @tsv'
```

Start with action types:

```text
no-op
update
create
delete
delete,create
```

For imported production-like nodes, any `delete`, `create`, or `delete,create` action needs explicit review before apply.

## Good Checkpoint

A good checkpoint after NetBox import may look like:

```text
netbox_virtual_machine no-op
netbox_interface       no-op
netbox_ip_address      no-op
netbox_primary_ip      no-op
vsphere_virtual_machine update
```

That means source-of-truth inventory is clean and vSphere drift remains isolated.

## Common Legacy Drift Categories

Imported VMs often differ from the shared Terraform module in these areas:

- CPU hot-add setting.
- memory hot-add setting.
- datastore ID.
- network ID.
- imported VM marker or clone metadata.
- guestinfo metadata and userdata.
- wait timeout settings.
- disk labels.
- disk count and unit numbers.
- orphaned or extra disks.

Some of these are harmless. Some can disrupt a Kubernetes node.

## Do Not Treat In-Place As Automatically Safe

Terraform may show:

```text
update
```

But an in-place update can still include risky changes:

```text
network_id change
datastore_id change
disk label changes
disk removal or orphan handling
guestinfo metadata injection
clone/customize block changes
```

For Kubernetes nodes, especially control-plane or etcd members, do not apply these casually.

## Inspect vSphere VM Details

Use targeted JSON review:

```bash
terraform show -json audit.tfplan \
  | jq '.resource_changes[]?
    | select(.type == "vsphere_virtual_machine")
    | {
        address,
        actions: .change.actions,
        before: {
          datastore_id: .change.before.datastore_id,
          network: [.change.before.network_interface[]? | .network_id],
          disks: [.change.before.disk[]? | {label, unit_number, size}]
        },
        after: {
          datastore_id: .change.after.datastore_id,
          network: [.change.after.network_interface[]? | .network_id],
          disks: [.change.after.disk[]? | {label, unit_number, size}]
        }
      }'
```

Classify each change as:

```text
safe metadata drift
safe compute setting
requires maintenance window
unsafe on legacy node
replace node instead
```

## Replacement-Node Decision

If the imported node shape differs materially from the shared module, prefer replacement over in-place reconciliation.

Replacement-node model:

```text
1. Provision replacement VM with current module/template.
2. Bootstrap OS and RKE2 prerequisites.
3. Join replacement node.
4. Drain old node.
5. Remove old node from Kubernetes/RKE2/etcd as appropriate.
6. Retire old VM and Terraform state.
7. Repeat one node at a time.
```

For workers, add temporary capacity first when needed.

For control-plane or etcd nodes:

- preserve quorum.
- replace one node at a time.
- verify API health after each step.
- verify etcd health after each step.
- do not reuse hostname/IP until old membership is safely removed.

For a more detailed rehearsal shape using prebuilt powered-off VMs, see [Fast OS Template Node Replacement Rehearsal](/field-notes/fast-os-template-node-replacement-rehearsal/).

## Suggested Tool Split

Use the right tool for each layer:

- Terraform: VM, disks, network intent, NetBox ownership.
- Ansible: OS prep, packages, kernel/sysctl, RKE2 config, service control.
- `kubectl` and RKE2 tooling: drain, node deletion, etcd checks.
- Rancher: cluster visibility and final health validation.

## Operating Rule

A drift audit is successful when it tells you not to apply.

If NetBox is clean but vSphere drift is risky, stop at the checkpoint and move to a replacement-node runbook.
