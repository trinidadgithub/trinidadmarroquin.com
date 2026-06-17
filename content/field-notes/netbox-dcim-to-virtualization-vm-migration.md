+++
title = 'NetBox DCIM To Virtualization VM Migration'
date = 2026-06-17T00:00:00-05:00
draft = false
description = 'Field note for recognizing when VMware VMs were modeled as NetBox DCIM devices and migrating them toward virtualization VM objects for Terraform ownership.'
tags = ['netbox', 'terraform', 'vsphere', 'ipam', 'audit', 'operations']
categories = ['field-notes']
+++

NetBox has more than one way to represent infrastructure.

A VMware VM imported as a DCIM device may look usable in the UI, but it is not the same object model as a NetBox virtualization virtual machine. Terraform provider resources for NetBox virtualization expect the virtualization model.

## Symptom

A known VM does not show up through the virtualization endpoint:

```bash
curl -s \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_URL/api/virtualization/virtual-machines/?name=$VM_NAME" \
  | jq '.count'
```

Expected if it is modeled as a virtualization VM:

```text
1
```

If it returns `0`, check whether it was modeled as a DCIM device:

```bash
curl -s \
  -H "Authorization: Token $NETBOX_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_URL/api/dcim/devices/?name=$VM_NAME" \
  | jq '.results[] | {
      id,
      name,
      status: .status.value,
      site: .site.name,
      role: .role.name,
      device_type: .device_type.model,
      primary_ip4: .primary_ip4.address
    }'
```

## Environment Variable Mismatch

Be consistent with token variable names.

Some scripts use:

```bash
NETBOX_URL
NETBOX_TOKEN
```

The Terraform NetBox provider commonly uses:

```bash
NETBOX_SERVER_URL
NETBOX_API_TOKEN
```

If one command uses empty variables, it can look like NetBox has no records when the request is actually malformed or unauthenticated.

## Migration Target

For Terraform-managed VM lifecycle work, model each VM as:

```text
virtualization virtual machine
virtualization interface
IP address assigned to VM interface
primary IPv4 relationship
```

The object graph should line up with Terraform resources such as:

```text
netbox_virtual_machine
netbox_interface
netbox_ip_address
netbox_primary_ip
```

## Validation Checks

Before importing or reconciling, validate:

- no duplicate VM names.
- no duplicate IP addresses.
- every IP has the expected prefix.
- every assigned IP has a VM/interface owner.
- every VM belongs to the expected virtualization cluster.
- every VM has the expected primary IPv4.
- VM compute metadata is either intentionally blank or ready to be managed.

## Primary IP Quirk

Primary IPv4 assignment may require a separate import, API patch, or Terraform reconciliation step.

If an existing NetBox VM already has a primary IP, Terraform may still need a matching `netbox_primary_ip` state resource. Review the plan carefully before applying any primary-IP reconciliation.

Acceptable targeted action shape:

```text
netbox_primary_ip create
netbox_virtual_machine update
netbox_ip_address update
netbox_interface no-op
```

Only proceed if the plan contains no vSphere resources and the NetBox updates are expected metadata normalization.

## Operating Rule

Do not treat DCIM device inventory and virtualization VM inventory as interchangeable.

Pick the NetBox object model that matches the automation you want Terraform to own, then import and audit before applying changes.
