+++
title = 'Terraform Targeted Plans For Live Cluster Node Expansion'
date = 2026-07-02T00:00:00-05:00
draft = false
description = 'Field note for safely adding new vSphere VMs to a live Kubernetes cluster with Terraform, NetBox records, saved targeted plans, and JSON plan verification.'
tags = ['terraform', 'vsphere', 'netbox', 'kubernetes', 'rke2', 'operations', 'guardrails']
categories = ['field-notes']
+++

Targeted Terraform applies are a sharp tool. They are not a normal workflow, but they are sometimes the safer option when a live cluster needs a narrow expansion and the full plan contains unrelated refactor drift.

This note covers the pattern for adding a small set of new monitor nodes to an existing RKE2 cluster while avoiding changes to existing etcd, control-plane, worker, and load balancer VMs.

## Situation

The environment already had Terraform-managed vSphere VMs:

```text
lb1, lb2
etc1, etc2, etc3
mstr1, mstr2, mstr3
wrkr1, wrkr2, wrkr3
```

The intended change was only:

```text
mntr1, mntr2, mntr3
```

The module refactor also introduced NetBox resources for VMs, interfaces, IP addresses, primary IP assignment, and tags. That meant the first full plan was not safe to apply directly.

## Do Not Trust A Failed Or Partial Plan

First issue: the NetBox provider prompted for missing credentials:

```text
provider.netbox.api_token
provider.netbox.server_url
```

That is not a valid reviewed plan. The correct response is to stop, set credentials through the expected environment variables, and rerun the plan.

```bash
export NETBOX_SERVER_URL='https://netbox.example.com'
export NETBOX_API_TOKEN='<redacted>'
```

Do not paste long-lived tokens into shared logs or tickets. If a token lands in a transcript, rotate it.

## Why The Full Plan Was Unsafe

After credentials were available, the full plan still was not safe:

```bash
terraform plan -detailed-exitcode
```

The full plan wanted to create NetBox records for existing VMs and also detected unrelated drift on existing data disks. In this case, existing nodes had larger data disks than the refactored defaults, so Terraform interpreted the config as a disk shrink.

That is a stop sign.

The full plan was answering a different question:

```text
What would happen if this whole refactor were applied now?
```

The operational question was narrower:

```text
Can we create only mntr1, mntr2, mntr3 and their required NetBox records?
```

## Build A Targeted Saved Plan

Use `-target` only for the intended resource addresses and save the reviewed plan:

```bash
terraform plan -out=targeted.tfplan \
  -target='netbox_tag.cluster' \
  -target='module.vm_group.netbox_virtual_machine.vm["mntr1"]' \
  -target='module.vm_group.netbox_interface.vm["mntr1"]' \
  -target='module.vm_group.netbox_ip_address.vm["mntr1"]' \
  -target='module.vm_group.netbox_primary_ip.vm["mntr1"]' \
  -target='module.vm_group.vsphere_virtual_machine.vm["mntr1"]' \
  -target='module.vm_group.netbox_virtual_machine.vm["mntr2"]' \
  -target='module.vm_group.netbox_interface.vm["mntr2"]' \
  -target='module.vm_group.netbox_ip_address.vm["mntr2"]' \
  -target='module.vm_group.netbox_primary_ip.vm["mntr2"]' \
  -target='module.vm_group.vsphere_virtual_machine.vm["mntr2"]' \
  -target='module.vm_group.netbox_virtual_machine.vm["mntr3"]' \
  -target='module.vm_group.netbox_interface.vm["mntr3"]' \
  -target='module.vm_group.netbox_ip_address.vm["mntr3"]' \
  -target='module.vm_group.netbox_primary_ip.vm["mntr3"]' \
  -target='module.vm_group.vsphere_virtual_machine.vm["mntr3"]'
```

The Terraform warning about `-target` is expected. The warning is useful because it reminds you that the result is incomplete by design. That is acceptable only when the operational goal is intentionally narrow and the plan is reviewed as such.

## Prove The Saved Plan Scope

Human-readable review:

```bash
terraform show -no-color targeted.tfplan
```

Machine-readable review:

```bash
terraform show -json targeted.tfplan \
  | jq -r '.resource_changes[] | [(.change.actions | join(",")), .address] | @tsv'
```

Expected shape:

```text
create  netbox_tag.cluster
create  module.vm_group.netbox_virtual_machine.vm["mntr1"]
create  module.vm_group.netbox_interface.vm["mntr1"]
create  module.vm_group.netbox_ip_address.vm["mntr1"]
create  module.vm_group.netbox_primary_ip.vm["mntr1"]
create  module.vm_group.vsphere_virtual_machine.vm["mntr1"]
create  module.vm_group.netbox_virtual_machine.vm["mntr2"]
create  module.vm_group.netbox_interface.vm["mntr2"]
create  module.vm_group.netbox_ip_address.vm["mntr2"]
create  module.vm_group.netbox_primary_ip.vm["mntr2"]
create  module.vm_group.vsphere_virtual_machine.vm["mntr2"]
create  module.vm_group.netbox_virtual_machine.vm["mntr3"]
create  module.vm_group.netbox_interface.vm["mntr3"]
create  module.vm_group.netbox_ip_address.vm["mntr3"]
create  module.vm_group.netbox_primary_ip.vm["mntr3"]
create  module.vm_group.vsphere_virtual_machine.vm["mntr3"]
```

The important checks:

- every action is `create`.
- there are no `update`, `delete`, or `replace` actions.
- no existing `lb`, `etc`, `mstr`, or `wrkr` addresses appear.
- the saved plan includes required dependency resources such as `netbox_tag.cluster`.

If the JSON output contains any existing node address, stop and rebuild the plan.

## Include Missing NetBox Tags As Managed Dependencies

The monitor nodes used a cluster tag:

```text
cluster:cluster-a
```

The apply failed when that tag did not exist in NetBox:

```text
could not locate referenced tag "cluster:cluster-a" in netbox, no results
```

The fix was to make the tag a first-class Terraform resource:

```hcl
resource "netbox_tag" "cluster" {
  name        = "cluster:cluster-a"
  slug        = "cluster-cluster-a"
  color_hex   = "2196f3"
  description = "RKE2 Kubernetes cluster cluster-a - identifies all VMs that are members of this cluster"
}
```

Then reference it from VM tag lists:

```hcl
locals {
  cluster_netbox_tag_name = netbox_tag.cluster.name
}

netbox_tags = ["monitor", "rke2-node", local.cluster_netbox_tag_name]
```

That creates an explicit dependency so Terraform creates the tag before NetBox VM records need it.

One caveat: if someone creates the tag manually before Terraform applies, import it instead of creating a duplicate:

```bash
terraform import netbox_tag.cluster <tag-id>
```

## Verify Hot Add Before Apply

For live cluster nodes, CPU and memory hot-add settings matter. Check the saved plan, not just the source code:

```bash
terraform show -json targeted.tfplan \
  | jq -r '.resource_changes[]
      | select(.type == "vsphere_virtual_machine")
      | [.name, .index, (.change.after.cpu_hot_add_enabled|tostring), (.change.after.memory_hot_add_enabled|tostring)]
      | @tsv'
```

Expected shape:

```text
vm  mntr1  true  true
vm  mntr2  true  true
vm  mntr3  true  true
```

This is another reason to inspect the saved plan JSON. It proves what Terraform will send to vSphere for the exact resources being applied.

## Apply Only The Reviewed Plan

Apply the saved plan file, not a fresh plan:

```bash
terraform apply "targeted.tfplan"
```

Expected summary for this pattern:

```text
16 added, 0 changed, 0 destroyed
```

That includes:

- one NetBox cluster tag.
- NetBox VM/interface/IP/primary IP records for three monitor nodes.
- three vSphere virtual machines.

Afterward, do not run a broad `terraform apply` until the full-plan drift is resolved. In this case, the full refactor still needed data disk sizing reconciliation for existing nodes.

## Guardrails

- `terraform validate` only proves configuration syntax and provider schema compatibility.
- `terraform plan -detailed-exitcode` is not useful if the provider prompts or errors.
- `-target` is acceptable for narrowly scoped live operations, but only with a saved plan and explicit address review.
- never use a filtering variable that removes existing keys from `for_each` unless you have proven it will not plan destroys.
- NetBox dependencies such as tags should be managed or imported before dependent VM records are created.
- apply the reviewed `.tfplan`, not a new plan.
- rotate credentials if they were pasted into a transcript.

The operating rule is simple: when a live cluster needs three new nodes, the plan should prove exactly three new VMs and their dependencies. Anything else belongs in a separate refactor window.
