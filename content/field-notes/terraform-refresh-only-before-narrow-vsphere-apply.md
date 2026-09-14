+++
title = 'Terraform Refresh-Only Before Narrow vSphere Applies'
date = 2026-09-14T00:00:00-05:00
draft = false
description = 'Field note for using Terraform plan classification, refresh-only state reconciliation, and lifecycle ignore_changes before applying narrow vSphere guestinfo updates on live Kubernetes nodes.'
tags = ['terraform', 'vsphere', 'kubernetes', 'drift', 'operations', 'guardrails']
categories = ['field-notes']
+++

A Terraform plan can look like a small in-place update and still contain dangerous vSphere operations.

When live VMs have been moved by incident response, storage maintenance, DRS, or a CSI controller, Terraform state may lag behind vCenter reality. A normal apply can try to move everything back, detach disks, or rewrite placement while you only meant to update a harmless metadata value.

## Situation

The intended change was narrow:

```text
guestinfo.network-config: netmask /16 -> /22
```

The first plan was not narrow. It also included:

```text
host_system_id changes
datastore_id changes
disk / orphaned_disk_N changes
output refresh noise
```

That combination is a stop sign. On vSphere VMs that are Kubernetes nodes, those fields can mean host relocation, storage migration, or live CSI volume detach behavior.

## Classify Before Apply

Save the plan and inspect the JSON, not just the summary line:

```bash
terraform plan -out=change.tfplan
terraform show -json change.tfplan > change.tfplan.json
```

Start with action and address review:

```bash
jq -r '.resource_changes[]?
  | [(.change.actions | join(",")), .type, .address]
  | @tsv' change.tfplan.json
```

Then inspect the vSphere VM fields that can move or disrupt nodes:

```bash
jq '.resource_changes[]?
  | select(.type == "vsphere_virtual_machine")
  | {
      address,
      actions: .change.actions,
      host_before: .change.before.host_system_id,
      host_after: .change.after.host_system_id,
      datastore_before: .change.before.datastore_id,
      datastore_after: .change.after.datastore_id,
      disks_before: [.change.before.disk[]? | {label, unit_number, size}],
      disks_after: [.change.after.disk[]? | {label, unit_number, size}],
      extra_config_before: .change.before.extra_config,
      extra_config_after: .change.after.extra_config
    }' change.tfplan.json
```

Classify each VM into practical buckets:

```text
metadata-only
host placement
datastore placement
disk attach/detach
replace/create/destroy
output-only
```

Only the first and last categories belong in a narrow guestinfo apply.

## Use Refresh-Only For Accepted Drift

If vCenter was intentionally changed outside Terraform, first fold that reality into state:

```bash
terraform apply -refresh-only
```

This should read providers and update Terraform state. It should not ask vCenter to relocate a VM, change disks, power cycle a node, or rewrite guestinfo.

After refresh-only, plan again:

```bash
terraform plan -out=after-refresh.tfplan
terraform show -json after-refresh.tfplan > after-refresh.tfplan.json
```

If the dangerous fields disappear, the original problem was stale state. If they remain, configuration is still trying to enforce something that is no longer the desired owner of that field.

## Ignore Only Fields Owned Elsewhere

Use `lifecycle.ignore_changes` when another system intentionally owns part of the VM lifecycle.

Example for Kubernetes nodes where placement and dynamic CSI disks are operationally managed outside this Terraform root:

```hcl
resource "vsphere_virtual_machine" "node" {
  for_each = local.vms

  # ... normal VM configuration ...

  lifecycle {
    ignore_changes = [
      host_system_id,
      datastore_id,
      disk,
    ]
  }
}
```

Do not add ignores as a way to silence an uncomfortable plan. Add them only when ownership is clear:

```text
host_system_id  -> placement tooling, DRS policy, or incident relocation
datastore_id    -> storage maintenance or relocation tooling
disk            -> vSphere CSI dynamic volume attachment
```

If Terraform should own those fields again later, remove the ignore during a planned reconciliation window and review the resulting plan as a separate change.

## Replan Until The Diff Is Exact

The safe checkpoint is a plan where every changed VM has exactly the intended attribute:

```text
extra_config.guestinfo.network-config
```

Use JSON to prove the direction of the change:

```bash
jq -r '.resource_changes[]?
  | select(.type == "vsphere_virtual_machine")
  | select(.change.actions | index("update"))
  | [.address,
     (.change.before.extra_config["guestinfo.network-config"] // ""),
     (.change.after.extra_config["guestinfo.network-config"] // "")]
  | @tsv' after-refresh.tfplan.json
```

Expected review statement:

```text
All VM updates are guestinfo.network-config only.
No host_system_id changes.
No datastore_id changes.
No disk changes.
No power state changes.
No create, delete, or replace actions.
```

Only then apply the saved, reviewed plan:

```bash
terraform apply after-refresh.tfplan
```

## Guestinfo Is Not The Live Guest

For vSphere cloud-init flows, changing `guestinfo.network-config` usually updates what the VM will read on the next cloud-init run. It does not necessarily change the running OS immediately.

For a live subnet-mask correction, treat these as separate workstreams:

```text
Terraform guestinfo update -> future boot / future clone behavior
in-guest netplan update    -> current running interface behavior
```

Verify both layers. From Terraform, confirm the final plan has no resource changes. From the guest or management plane, confirm the active address and prefix length are correct.

## Operating Rule

`terraform apply -refresh-only` is not a substitute for plan review, and `ignore_changes` is not a broom.

The safe pattern is:

```text
1. Save plan.
2. Classify every vSphere VM change.
3. Stop on host, datastore, disk, create, delete, or replace drift.
4. Refresh state for accepted live drift.
5. Ignore only fields intentionally owned elsewhere.
6. Replan and prove the remaining diff is exact.
7. Apply the saved reviewed plan.
```

For broader drift classification after imports, see [Classifying vSphere Drift After Terraform Import](/field-notes/classifying-vsphere-drift-after-terraform-import/). For deliberately narrow Terraform operations on live cluster nodes, see [Terraform Targeted Plans For Live Cluster Node Expansion](/field-notes/terraform-targeted-plan-live-cluster-nodes/). For the guestinfo/cloud-init boundary, see [vSphere Guestinfo And Cloud-Init On Cloned VMs](/field-notes/vsphere-cloud-init-guestinfo/).
