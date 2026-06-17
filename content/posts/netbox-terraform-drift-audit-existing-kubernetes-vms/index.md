+++
title = 'Drift Audit Report: Bringing Existing Kubernetes VMs Under Terraform And NetBox'
date = 2026-06-17T00:00:00-05:00
draft = false
description = 'A drift audit report for converting VM inventory from NetBox DCIM devices to virtualization objects, importing existing vSphere and NetBox resources into Terraform state, and deciding not to apply unsafe legacy VM drift.'
tags = ['terraform', 'vsphere', 'netbox', 'kubernetes', 'drift', 'audit', 'operations']
categories = ['notes']
+++

This work was not a greenfield deployment.

The cluster already existed. The VMs already existed in vSphere. NetBox already had inventory, but some of it was modeled as DCIM devices rather than virtualization virtual machines. Terraform had a reusable module that could manage VM lifecycle state, NetBox VM records, interfaces, IP addresses, and primary IPv4 relationships. The problem was getting from “existing infrastructure” to “managed state” without accidentally changing the running cluster.

That calls for a different kind of write-up: a drift audit report.

The goal was not to apply changes. The goal was to model the current site, import state carefully, and use Terraform plans as evidence.

## The Starting Problem

The first signal was simple: a NetBox API query against the virtualization VM endpoint returned nothing for a known Kubernetes node.

That led to an important distinction:

```text
DCIM device != virtualization virtual machine
```

NetBox can represent a VMware VM as a DCIM device if that is how it was imported, but Terraform's NetBox virtualization resources expect virtual machine objects. If the source of truth is going to participate in VM lifecycle automation, the model needs to match the provider's resource model.

The audit therefore had two tracks:

- migrate or recreate the inventory as NetBox virtualization VM objects.
- import matching vSphere and NetBox resources into Terraform state.

Only after that could Terraform be used as a drift detector.

## The Reconciliation Boundary

The safe boundary was explicit:

```text
Import and audit first. Do not apply full vSphere changes to legacy nodes.
```

That boundary matters because an imported VM may not look like a VM created by the shared module. Existing disks may have different labels. Network backing may differ. Datastore placement may differ. Clone metadata may be absent. Guestinfo metadata may not exist. Hot-add may be disabled.

Terraform can detect all of that, but detection is not permission to apply.

## NetBox Migration Checkpoint

After the NetBox virtualization objects were created and imported, the NetBox side reached a clean checkpoint:

```text
netbox_virtual_machine: no-op
netbox_interface:       no-op
netbox_ip_address:      no-op
netbox_primary_ip:      no-op
```

That is the useful milestone. It means Terraform and NetBox agree about the VM inventory, interfaces, IPs, and primary IP relationships.

One quirk showed up during this process: existing primary IP relationships may not import cleanly as standalone `netbox_primary_ip` resources. In practice, creating the synthetic Terraform primary-IP resource can also normalize related NetBox VM and IP metadata, such as vCPU count, memory, disk size, DNS name, and interface association.

That is acceptable only when the plan is reviewed and confirmed to be NetBox-only.

## Plan Review Saved The Site

The important command was not `terraform apply`. It was plan classification:

```bash
terraform plan -out=audit.tfplan
terraform show -json audit.tfplan \
  | jq -r '.resource_changes[]? | [.address, .type, (.change.actions | join(","))] | @tsv'
```

After NetBox was reconciled, the remaining full plan showed:

```text
Plan: 0 to add, 14 to change, 0 to destroy
```

All remaining changes were vSphere VM in-place updates.

That sounds safe at first glance. It was not safe enough to apply casually.

The drift categories included:

- CPU hot-add and memory hot-add changing from disabled to enabled.
- datastore placement differences.
- network backing differences.
- imported VM metadata changing to module clone metadata.
- guestinfo metadata/userdata being added.
- disk label and disk shape mismatches.
- extra legacy worker disks not represented by the shared module.

The key point: there were no NetBox changes left, but the vSphere changes were still operationally risky for existing Kubernetes nodes.

## The Decision: Replace, Do Not Reconcile In Place

At that point the audit had done its job.

It showed that NetBox and Terraform state could be reconciled cleanly, but the legacy VMs did not match the desired shared-module shape. Applying the module shape directly onto old-template Kubernetes nodes could touch network, datastore, clone, guestinfo, and disk attributes.

The better path is replacement-node lifecycle:

```text
create replacement VM with current module/template
bootstrap OS and RKE2 prerequisites
join replacement node
drain old node
remove old node from Kubernetes/RKE2/etcd as appropriate
retire old VM and state
repeat one node at a time
```

For workers, temporary extra capacity can make migration easier. For control-plane and etcd nodes, the sequence needs stricter quorum and health checks.

## Responsibility Split

This audit also clarified tool boundaries:

- Terraform owns VM, disks, network intent, and NetBox ownership.
- Ansible is a good fit for OS prep, packages, kernel/sysctl settings, RKE2 configuration, and service control.
- `kubectl` and RKE2 tooling own drain, node deletion, and etcd membership checks.
- Rancher confirms final cluster visibility and health.

That split keeps Terraform from becoming an unsafe in-place remediation tool for legacy Kubernetes nodes.

## The Practical Lesson

Importing existing infrastructure into Terraform should start as an audit, not an apply.

The win is not “Terraform can now change all these VMs.” The win is knowing exactly which systems agree, which resources are clean, and which drift is risky enough to require replacement instead of reconciliation.

For this site, the checkpoint was:

```text
NetBox migration complete.
Terraform state import complete for source-of-truth objects.
NetBox plan clean.
vSphere drift classified.
Full apply intentionally blocked.
Next step: replacement-node runbook.
```

That is a healthy outcome for a drift audit.

Related Field Notes:

- [NetBox DCIM To Virtualization VM Migration](/field-notes/netbox-dcim-to-virtualization-vm-migration/)
- [Terraform Import Workflow For Existing vSphere VMs](/field-notes/terraform-import-existing-vsphere-vms/)
- [Classifying vSphere Drift After Terraform Import](/field-notes/classifying-vsphere-drift-after-terraform-import/)
