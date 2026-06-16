+++
title = 'Managing vSphere VM Lifecycle State With Terraform And NetBox'
date = 2026-06-16T00:00:00-05:00
draft = false
description = 'A lifecycle runbook for managing vSphere VM CPU, memory, disk sizing, NetBox metadata, idempotency, and teardown hygiene after initial Terraform provisioning.'
tags = ['terraform', 'vsphere', 'netbox', 'automation', 'operations', 'sre']
categories = ['notes']
+++

Provisioning a VM is only the first part of ownership.

The more interesting operational question is what happens after the VM exists. Can Terraform continue to manage CPU, memory, disk sizing, NetBox metadata, idempotency, and teardown without turning every follow-up change into a manual vCenter edit?

That was the next step after adding VM/IP guardrails. The automation already knew how to prevent duplicate VM names, duplicate IPs, stale DNS collisions, active network IP reuse, and NetBox/vCenter drift before create. The next improvement was to keep the VM lifecycle managed after creation.

The useful pattern became:

```text
provision -> record in NetBox -> manage compute and disks -> verify metadata -> confirm idempotency -> destroy -> verify cleanup
```

## The Ownership Boundary

The module now treats a VM as more than a clone operation.

Terraform owns the intended values for:

- vCPU count.
- memory size.
- primary disk size.
- optional secondary data disk attachment.
- optional secondary data disk size.
- CPU hot-add setting.
- memory hot-add setting.
- NetBox VM memory metadata.
- NetBox VM vCPU metadata.
- NetBox VM disk-size metadata.
- NetBox VM/interface/IP/primary-IP relationships.

That matters because manual post-provisioning changes are where platform drift usually starts. A VM gets resized during a troubleshooting window. A disk gets grown in vCenter. NetBox still shows the old size. Terraform either wants to undo the change later or keeps reporting confusing drift.

The better operating model is to make the desired size change in the VM map, review the plan, apply the saved plan, and then verify both vSphere and NetBox reflect the same intent.

## Example State Change

The VM map carries per-VM overrides for compute and disk sizing:

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

Those values drive both the vSphere VM and the NetBox metadata.

In vSphere, Terraform manages:

```text
num_cpus
memory
disk[0].size
disk[1].size, when a data disk is enabled
```

In NetBox, Terraform records:

```text
vcpus
memory_mb
disk_size_mb
```

The disk metadata is the sum of the primary disk and optional data disk, expressed in megabytes.

## Safe Change Workflow

The workflow is intentionally conservative.

Generate a saved plan:

```bash
terraform plan -out=compute-change.tfplan
```

Inspect action types:

```bash
terraform show -json compute-change.tfplan \
  | jq -r '.resource_changes[]? | [.address, .type, (.change.actions | join(","))] | @tsv'
```

For a normal resize, the expected vSphere action is usually:

```text
update
```

If the VM shows `delete,create`, stop and understand why Terraform wants replacement.

Inspect before and after values:

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

Inspect NetBox metadata changes too:

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

Apply only the reviewed saved plan:

```bash
terraform apply compute-change.tfplan
```

Then check idempotency:

```bash
terraform plan -detailed-exitcode
```

The desired result is no changes.

## Hot-Add Is Not A Substitute For Review

CPU and memory hot-add make many changes less disruptive, but they do not remove the need for plan review.

The operator still needs to verify:

- the VM is being updated, not replaced.
- the CPU and memory values are expected.
- the disk changes are growth-only unless replacement is intentional.
- NetBox metadata changes match the VM state change.
- no unrelated VM, IP, interface, or destroy action is present.

Hot-add improves the execution path. It does not prove the change is safe.

## Disk Growth Has Two Layers

Terraform can grow the virtual disk in vSphere. That does not always mean the guest operating system has expanded the partition, LVM volume, or filesystem.

After increasing a disk, plan for guest verification:

```bash
lsblk
df -h
sudo growpart <disk> <partition>
sudo pvresize <device>
sudo lvextend -r -l +100%FREE <logical-volume>
```

The exact guest commands depend on the image layout. The important distinction is that vSphere disk size and guest usable filesystem size are separate layers.

## NetBox Verification

After apply, verify NetBox reflects the intended lifecycle state.

Set generic lookup values:

```bash
export VM_NAME="cluster-a-app-01"
export VM_IP="192.0.2.10"
export VM_DNS_NAME="cluster-a-app-01.example.com"
export NETBOX_CLUSTER_NAME="cluster-a"
```

Verify VM metadata:

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/virtualization/virtual-machines/?name=$VM_NAME" \
  | jq '.results[] | {
      name,
      status: .status.value,
      cluster: .cluster.name,
      vcpus,
      memory_mb: .memory,
      disk_size_mb: .disk,
      primary_ip4: .primary_ip4.address
    }'
```

Verify IP assignment:

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/ipam/ip-addresses/?q=$VM_IP" \
  | jq '.results[] | {
      address,
      status: .status.value,
      dns_name,
      assigned_object_type,
      assigned_object: .assigned_object.name
    }'
```

NetBox should not lag behind the hypervisor. If Terraform manages the VM size, the source-of-truth metadata should move with it.

## Destroy Is Part Of Lifecycle Management

The lifecycle test is not complete until destroy is tested too.

For a disposable managed VM, review the destroy plan:

```bash
terraform plan -destroy -out=destroy.tfplan
terraform show -json destroy.tfplan \
  | jq -r '.resource_changes[]? | [.address, .type, (.change.actions | join(","))] | @tsv'
```

Expected resources include the vSphere VM and the NetBox object graph:

```text
netbox_primary_ip
netbox_ip_address
netbox_interface
netbox_virtual_machine
vsphere_virtual_machine
```

After applying the destroy plan, verify cleanup:

```bash
terraform apply destroy.tfplan
terraform state list
govc find / -type m -name "$VM_NAME"
```

NetBox lookups for the VM and IP should return count `0`.

That proves the full lifecycle:

```text
create -> manage -> verify idempotency -> destroy -> cleanup NetBox and vSphere
```

## The Practical Lesson

The most useful automation is not the automation that creates something once. It is the automation that keeps ownership clear after the first successful apply.

For vSphere VM operations, that means Terraform should own the intended VM lifecycle state, NetBox should reflect that state, and operators should review plans as lifecycle changes, not just deployment events.

Related Field Notes:

- [Terraform vSphere Compute Resize Checklist](/field-notes/terraform-vsphere-compute-resize-checklist/)
- [Post-Provision VM State Verification With NetBox](/field-notes/post-provision-vm-state-verification-netbox/)
