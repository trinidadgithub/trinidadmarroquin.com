+++
title = 'Terraform State Moves During A Module Refactor'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note for moving Terraform resources into a module without forcing VM replacement.'
tags = ['terraform', 'state', 'modules', 'vsphere']
categories = ['field-notes']
+++

When an existing Terraform resource is moved into a module, Terraform sees a new resource address. If state is not moved first, the plan may try to create the module resource and destroy the old root resource.

## Symptom

After converting a root resource to a module call, the plan shows addresses like this:

```text
# module.vm_group.vsphere_virtual_machine.vm["lb1"] will be created
```

while the existing state still has:

```text
vsphere_virtual_machine.vm["lb1"]
```

## Check Current State

Run from the environment root:

```bash
terraform state list
```

For vSphere VMs, filter the list:

```bash
terraform state list | grep vsphere_virtual_machine
```

## Move State

Move the existing resource address to the module address:

```bash
terraform state mv \
  'vsphere_virtual_machine.vm["lb1"]' \
  'module.vm_group.vsphere_virtual_machine.vm["lb1"]'
```

Repeat for each `for_each` key:

```bash
terraform state mv \
  'vsphere_virtual_machine.vm["wrkr1"]' \
  'module.vm_group.vsphere_virtual_machine.vm["wrkr1"]'
```

## Validate

Run:

```bash
terraform validate
terraform plan
```

The target result is no unexpected replacement. If the plan still shows replacement, inspect the forced replacement field before applying:

```bash
terraform plan -out=tfplan
terraform show -no-color tfplan > plan.txt
grep -n "must be replaced\|forces replacement" plan.txt
```

## Notes

- Do not use `terraform state rm` for this case. The resource still exists; only its Terraform address changed.
- Move state before applying the module conversion.
- Preserve behavior first. Improve module defaults after the plan is stable.
- If the environment uses `for_each`, the keys must stay stable or Terraform will treat the instances as different resources.
