+++
title = 'Terraform vSphere DNS Search Suffix Ownership'
date = 2026-06-19T00:00:00-05:00
draft = false
description = 'Field note for separating VM identity domain from DNS search suffixes in Terraform vSphere modules and proving which setting reaches guest customization.'
tags = ['terraform', 'vsphere', 'dns', 'netplan', 'cloud-init', 'operations']
categories = ['field-notes']
+++

A VM can have the correct FQDN intent and still receive the wrong resolver search suffix.

The trap is treating these as the same setting:

```text
vm_domain  -> identity/FQDN domain
dns_search -> resolver search suffix list
```

They are related, but they are not the same control.

## Symptom

An environment sets DNS search suffixes to empty:

```hcl
dns_search = "[]"
```

But new vSphere VMs still boot with a resolver search domain such as:

```text
search corp.example.com
```

The node audit shows drift even though the Terraform input looked correct:

```text
resolv_conf_search = corp.example.com
netplan_search     = [corp.example.com]
```

## Root Cause Pattern

The environment may define `dns_search`, but the module might not consume it.

The broken pattern looks like this:

```hcl
module "vm_group" {
  source = "../../../modules/vsphere-vm-group"

  vm_domain       = var.vm_domain
  dns_server_list = var.dns_server_list
  # dns_search exists in variables.tf, but is not passed here
}
```

Then the module derives vSphere guest customization search suffixes from `vm_domain`:

```hcl
customize {
  linux_options {
    host_name = each.value.name
    domain    = var.vm_domain
  }

  network_interface {
    ipv4_address = each.value.ipv4_address
    ipv4_netmask = tonumber(each.value.ipv4_netmask)
  }

  ipv4_gateway    = var.ipv4_gateway
  dns_server_list = var.dns_server_list
  dns_suffix_list = [var.vm_domain]
}
```

In that shape, `dns_search = "[]"` is a red herring. It exists, but it does not control anything.

## Prove The Active Path

Search the Terraform code first:

```bash
rg 'dns_search|dns_suffix_list|vm_domain|network-config|guestinfo' .
```

Look for two possible paths:

```text
vSphere guest customization: customize.dns_suffix_list
cloud-init guestinfo:        network-config.yaml nameservers.search
```

If guestinfo network config is disabled, the cloud-init template is not the active source even if it contains a search entry.

## Inspect Plan JSON Without Reading Secrets

If a plan JSON already exists, inspect only the resolved fields needed for evidence:

```bash
jq -r '
  .configuration.root_module.module_calls.vm_group.expressions.vm_domain.references,
  .variables.vm_domain,
  .variables.dns_search
' tfplan.json
```

Then inspect vSphere customization values:

```bash
jq -r '
  .planned_values.root_module.child_modules[]?
  | select(.address == "module.vm_group")
  | .resources[]?
  | select(.type == "vsphere_virtual_machine")
  | .values.clone[0].customize[0]
  | {dns_suffix_list, linux_options}
' tfplan.json
```

Useful evidence shape:

```json
{
  "dns_search": { "value": "[]" },
  "dns_suffix_list": ["corp.example.com"],
  "linux_options": [{ "domain": "corp.example.com" }]
}
```

That proves the search suffix came from module logic, not from the intended empty `dns_search` input.

## Minimal Module Fix

Pass `dns_search` into the module:

```hcl
module "vm_group" {
  source = "../../../modules/vsphere-vm-group"

  vm_domain       = var.vm_domain
  dns_server_list = var.dns_server_list
  dns_search      = var.dns_search
}
```

Add a module variable that preserves the existing bracketed string interface:

```hcl
variable "dns_search" {
  type        = string
  description = "DNS search suffixes in bracketed form, for example [] or [corp.example.com]"
  default     = "[]"
}
```

Parse it once:

```hcl
locals {
  dns_search_suffixes = compact([
    for suffix in split(",", trim(var.dns_search, "[] ")) : trimspace(replace(suffix, "\"", ""))
  ])
}
```

Use it for vSphere customization:

```hcl
dns_suffix_list = local.dns_search_suffixes
```

If cloud-init guestinfo network config is enabled, use the same parsed value there too. Do not maintain separate search suffix logic for vSphere customization and cloud-init.

## Validate The Behavior

Run formatting and validation:

```bash
terraform fmt main.tf ../../../modules/vsphere-vm-group/main.tf ../../../modules/vsphere-vm-group/variables.tf
terraform validate
```

Then inspect a new plan if provider credentials are available. If not, use existing plan/state evidence and document that a fresh plan was blocked by missing provider credentials.

Expected behavior:

```text
dns_search = "[]"                  -> dns_suffix_list = []
dns_search = "[corp.example.com]"  -> dns_suffix_list = ["corp.example.com"]
vm_domain = "corp.example.com"     -> still controls VM FQDN/domain intent
```

## Operating Rule

Do not let a variable name create false confidence.

For infrastructure modules, every important input needs a traceable path:

```text
root variable -> module argument -> module variable -> provider argument -> plan/state -> guest audit
```

If the chain breaks anywhere, the variable is documentation, not behavior.
