+++
title = 'Terraform vSphere Compute Resize Checklist'
date = 2026-06-16T00:00:00-05:00
draft = false
description = 'Field note for safely changing vSphere VM CPU, memory, primary disk, and optional data disk sizing through Terraform after provisioning.'
tags = ['terraform', 'vsphere', 'vmware', 'automation', 'operations', 'validation']
categories = ['field-notes']
+++

Use this checklist when resizing Terraform-managed vSphere VMs after initial provisioning.

The goal is to update VM state without accidentally replacing the VM, losing NetBox alignment, or skipping guest OS disk follow-up.

## Edit Desired State

Change the VM entry in the environment VM map:

```hcl
locals {
  vms = {
    "app-1" = {
      name             = "cluster-a-app-01"
      ipv4_address     = "192.0.2.10"
      ipv4_netmask     = tostring(var.netmask)
      cpu              = 4
      ram_gb           = 32
      disksize         = 80
      attach_data_disk = true
      data_disk_gb     = 200
    }
  }
}
```

Avoid manual vCenter edits for values Terraform owns.

## Generate A Saved Plan

```bash
terraform plan -out=compute-change.tfplan
```

Use a saved plan so the reviewed plan is the applied plan.

## Inspect Action Types

```bash
terraform show -json compute-change.tfplan \
  | jq -r '.resource_changes[]? | [.address, .type, (.change.actions | join(","))] | @tsv'
```

Expected for a normal resize:

```text
module.vm_group.vsphere_virtual_machine.vm["app-1"]  vsphere_virtual_machine  update
module.vm_group.netbox_virtual_machine.vm["app-1"]   netbox_virtual_machine   update
```

Stop if you see an unexpected replacement:

```text
delete,create
```

Stop if unrelated VMs or destroy actions appear.

## Inspect vSphere Before And After Values

```bash
terraform show -json compute-change.tfplan \
  | jq '.resource_changes[]?
    | select(.type == "vsphere_virtual_machine")
    | {
        address,
        actions: .change.actions,
        before: {
          cpu: .change.before.num_cpus,
          memory_mb: .change.before.memory,
          disks: [.change.before.disk[]? | {label, size}]
        },
        after: {
          cpu: .change.after.num_cpus,
          memory_mb: .change.after.memory,
          disks: [.change.after.disk[]? | {label, size}]
        }
      }'
```

Confirm:

- CPU is the intended value.
- memory is the intended value in MB.
- primary disk size is expected.
- data disk exists only when intended.
- disk changes are growth-only unless replacement is explicitly approved.

## Inspect NetBox Metadata Changes

```bash
terraform show -json compute-change.tfplan \
  | jq '.resource_changes[]?
    | select(.type == "netbox_virtual_machine")
    | {
        address,
        actions: .change.actions,
        before: {
          vcpus: .change.before.vcpus,
          memory_mb: .change.before.memory_mb,
          disk_size_mb: .change.before.disk_size_mb
        },
        after: {
          vcpus: .change.after.vcpus,
          memory_mb: .change.after.memory_mb,
          disk_size_mb: .change.after.disk_size_mb
        }
      }'
```

Expected metadata relationship:

```text
memory_mb = ram_gb * 1024
disk_size_mb = (primary_disk_gb + optional_data_disk_gb) * 1024
```

## Apply The Reviewed Plan

```bash
terraform apply compute-change.tfplan
```

Do not regenerate the plan between review and apply unless you review the new plan too.

## Confirm Idempotency

```bash
terraform plan -detailed-exitcode
```

Expected:

```text
No changes. Your infrastructure matches the configuration.
```

Exit code expectations:

```text
0 = no changes
1 = error
2 = diff remains
```

## Guest Disk Follow-Up

If a virtual disk grew, verify the guest sees the new size:

```bash
lsblk
df -h
```

Common Linux follow-up patterns, depending on layout:

```bash
sudo growpart <disk> <partition>
sudo resize2fs <partition>
```

or LVM:

```bash
sudo pvresize <device>
sudo lvextend -r -l +100%FREE <logical-volume>
```

Do not assume vSphere disk growth means the guest filesystem expanded.

## Operating Rule

Treat post-provision VM resizing as a lifecycle change, not a console task.

Review the saved plan, apply the saved plan, verify NetBox metadata, and confirm idempotency.
