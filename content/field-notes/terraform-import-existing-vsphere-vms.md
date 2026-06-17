+++
title = 'Terraform Import Workflow For Existing vSphere VMs'
date = 2026-06-17T00:00:00-05:00
draft = false
description = 'Field note for importing existing vSphere and NetBox VM resources into Terraform state so a site can be audited before any apply.'
tags = ['terraform', 'vsphere', 'netbox', 'state', 'audit', 'operations']
categories = ['field-notes']
+++

Use this workflow when existing vSphere VMs need to be brought under Terraform state for audit and future lifecycle management.

The first goal is not to change the VMs. The first goal is to make Terraform aware of them and classify drift.

## Safety Boundary

Set the operating rule before importing:

```text
Import state and audit only. Do not apply full vSphere changes to existing cluster nodes.
```

This avoids turning a state migration into an accidental infrastructure mutation.

## Refactor To The Shared Module

Move the environment from root-level VM resources to the shared module shape:

```hcl
module "vm_group" {
  source = "../../../modules/vsphere-vm-group"

  vms = local.vms

  netbox_enabled      = true
  netbox_cluster_name = var.netbox_cluster_name

  # vSphere, template, network, DNS, and bootstrap inputs omitted
}
```

Keep VM definitions in a local map:

```hcl
locals {
  vms = {
    "cp1" = {
      name             = "cluster-a-cp-01"
      ipv4_address     = "192.0.2.5"
      ipv4_netmask     = tostring(var.netmask)
      cpu              = 4
      ram_gb           = 16
      disksize         = 80
      attach_data_disk = true
      data_disk_gb     = 200
    }
  }
}
```

## Import State In Layers

Import in small, reviewable layers:

```text
1. NetBox VM records
2. NetBox VM interfaces
3. NetBox IP addresses
4. NetBox primary IPv4 relationships
5. vSphere virtual machines
```

After each layer, run a targeted plan or full audit plan and inspect action types.

## Plan Classification Command

Generate an audit plan:

```bash
terraform plan -out=audit.tfplan
```

Classify every resource action:

```bash
terraform show -json audit.tfplan \
  | jq -r '.resource_changes[]? | [.address, .type, (.change.actions | join(","))] | @tsv'
```

Useful checkpoint output:

```text
netbox_virtual_machine no-op
netbox_interface       no-op
netbox_ip_address      no-op
netbox_primary_ip      no-op
vsphere_virtual_machine update
```

That means NetBox is reconciled, but vSphere drift remains.

## Targeted Primary IP Reconciliation

If primary IP resources do not import cleanly, use a targeted plan and inspect it before apply:

```bash
terraform plan \
  -target='module.vm_group.netbox_primary_ip.vm' \
  -out=primary-ips.tfplan

terraform show -json primary-ips.tfplan \
  | jq -r '.resource_changes[]? | [.address, .type, (.change.actions | join(","))] | @tsv'
```

Acceptable shape for a NetBox-only reconciliation:

```text
netbox_interface no-op
netbox_ip_address no-op or update
netbox_virtual_machine no-op or update
netbox_primary_ip create
```

Do not apply if any vSphere VM appears in the targeted plan.

After apply, verify count:

```bash
terraform state list | grep 'module.vm_group.netbox_primary_ip.vm' | wc -l
```

## Verify A Primary IP Resource

```bash
terraform state show 'module.vm_group.netbox_primary_ip.vm["cp1"]'
```

Then verify NetBox directly:

```bash
curl -s \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_URL/api/virtualization/virtual-machines/$NETBOX_VM_ID/" \
  | jq '{id,name,memory,disk,vcpus,primary_ip4}'
```

## Audit-Only Finish Line

The first safe finish line is not a clean full plan. It may be:

```text
NetBox resources: no-op
vSphere resources: update
no destroys
```

That is still useful. It means source-of-truth inventory is reconciled and remaining drift is isolated to legacy vSphere shape.

## Operating Rule

Importing existing VMs into Terraform is an audit workflow first.

Do not apply the full plan until every vSphere update is classified as safe, intentionally accepted, or replaced by a node migration plan.
