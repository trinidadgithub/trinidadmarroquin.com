+++
title = 'NetBox First Ownership For vSphere VM Provisioning'
date = 2026-06-15T00:00:00-05:00
draft = false
description = 'Field note for making NetBox VM and IPAM records a fail-closed provisioning gate before Terraform creates vSphere virtual machines.'
tags = ['netbox', 'terraform', 'vsphere', 'ipam', 'automation', 'operations']
categories = ['field-notes']
+++

When Terraform creates vSphere VMs, NetBox should not be an after-the-fact documentation step.

Use NetBox as an ownership gate before vSphere VM creation.

## Desired Order

The safe order is:

```text
1. Resolve required NetBox objects
2. Create NetBox VM record
3. Create NetBox interface record
4. Create NetBox IP address record
5. Set NetBox primary IPv4
6. Create vSphere VM
```

The vSphere VM should depend on the NetBox primary IP relationship, not just the VM record.

That proves the source-of-truth object graph exists before the hypervisor receives the create request.

## Terraform Pattern

The shape is:

```hcl
data "netbox_cluster" "cluster" {
  count = var.netbox_enabled ? 1 : 0
  name  = var.netbox_cluster_name
}

resource "netbox_virtual_machine" "vm" {
  for_each = var.netbox_enabled ? var.vms : {}

  name      = each.value.name
  cluster_id = data.netbox_cluster.cluster[0].id
  status    = "active"
}

resource "netbox_interface" "mgmt" {
  for_each = var.netbox_enabled ? var.vms : {}

  virtual_machine_id = netbox_virtual_machine.vm[each.key].id
  name               = "mgmt0"
  enabled            = true
}

resource "netbox_ip_address" "mgmt" {
  for_each = var.netbox_enabled ? var.vms : {}

  ip_address   = "${each.value.ipv4_address}/${each.value.ipv4_prefix_length}"
  status       = "active"
  dns_name     = "${each.value.name}.example.com"
  interface_id = netbox_interface.mgmt[each.key].id
}

resource "netbox_primary_ip" "vm" {
  for_each = var.netbox_enabled ? var.vms : {}

  virtual_machine_id = netbox_virtual_machine.vm[each.key].id
  ip_address_id      = netbox_ip_address.mgmt[each.key].id
}

resource "vsphere_virtual_machine" "vm" {
  for_each = var.vms

  name = each.value.name

  depends_on = [
    netbox_primary_ip.vm,
  ]
}
```

Adapt resource arguments to the provider version in use. The important part is the dependency boundary.

## What This Protects

This pattern protects against:

- creating a VM when NetBox cannot be reached.
- creating a VM when the NetBox cluster lookup fails.
- creating a VM when the NetBox VM name already exists.
- creating a VM when the NetBox IP address already exists.
- creating a VM without a primary IP relationship in source of truth.

## What This Does Not Protect

NetBox-first ownership does not prove:

- the VM name is absent from vCenter.
- the IP is quiet on the network.
- forward DNS is clear.
- reverse DNS is clear.
- `govc` is configured correctly.

Those need a separate preflight check.

## Fail-Closed Tests

Run these before trusting the pattern.

Missing NetBox credentials:

```bash
unset NETBOX_SERVER_URL
unset NETBOX_API_TOKEN
terraform plan -out=/tmp/missing-netbox-creds.tfplan
```

Expected result:

```text
Error: Missing required argument
The argument "server_url" is required

Error: Missing required argument
The argument "api_token" is required
```

Missing NetBox cluster:

```bash
terraform plan -out=tfplan \
  -var='netbox_cluster_name=missing-cluster-test'
```

Expected result:

```text
Error: no result
with module.vm_group.data.netbox_cluster.cluster[0]
```

Unreachable NetBox:

```bash
NETBOX_SERVER_URL="https://netbox-unreachable.invalid" \
NETBOX_API_TOKEN="dummy" \
NETBOX_SKIP_VERSION_CHECK=true \
terraform plan -out=/tmp/netbox-unreachable-test.tfplan
```

Expected result:

```text
Planning failed.
Error: Get "https://netbox-unreachable.invalid/api/..."
```

The desired behavior is:

```text
NetBox fails -> Terraform plan fails -> vSphere VM is not created
```

## Operating Rule

If NetBox is the source of truth, make VM creation depend on NetBox ownership being established first.

Do not let documentation happen after provisioning when the documentation system is supposed to prevent collisions.
