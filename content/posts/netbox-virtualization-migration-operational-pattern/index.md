+++
title = 'Operating A NetBox Virtualization Migration Without Losing Control'
date = 2026-06-18T00:00:00-05:00
draft = false
description = 'A practical operating pattern for migrating NetBox VM inventory from DCIM devices to virtualization VMs while keeping Terraform state, tags, IPs, and audit boundaries under control.'
tags = ['netbox', 'terraform', 'vsphere', 'kubernetes', 'migration', 'audit', 'operations']
categories = ['notes']
+++

Inventory migrations are easy to underestimate.

Changing a NetBox object from a DCIM device to a virtualization VM sounds like a data cleanup task. In practice, it touches ownership boundaries: IP assignments, primary IPs, cluster tags, Terraform imports, and the difference between audit-only work and infrastructure mutation.

The safe way to run this kind of migration is to treat it like an operational change, not a CSV edit.

## The Problem

Some VMware-backed Kubernetes nodes were represented in NetBox as DCIM devices. That worked for basic inventory lookup, but it did not match the automation model.

Terraform was managing vSphere VMs through a shared module and using NetBox virtualization resources for source-of-truth state:

```text
netbox_virtual_machine
netbox_interface
netbox_ip_address
netbox_primary_ip
```

That meant the NetBox object model had to move from:

```text
DCIM device + DCIM interface + IP
```

to:

```text
virtualization VM + VM interface + IP + primary IPv4
```

The migration also had to preserve cluster tags so operators could still answer simple questions like “which VMs belong to this cluster?”

## The Control Plane For The Migration

The migration script needed more than a create loop.

The useful controls were:

- `--apply` only when the dry run was reviewed.
- `--cluster-tag` to scope work to one cluster at a time.
- `--all-cluster-devices` for broad inventory discovery.
- `--all-matching-vms` for idempotent follow-up checks.
- `--sync-tags-only` to repair tags after VM creation.
- `--ensure-vm-tag-scope` to make a cluster tag usable on virtualization VMs.
- `--ensure-all-cluster-tag-scopes` for fleet-wide tag-scope hygiene.

The important pattern is that create, tag scope, and tag sync are separate operations. Separating them makes the output easier to review and reduces the blast radius of each apply.

## Dry Run First

A dry run should produce evidence, not just a yes/no result.

Example output classes:

```text
PLAN    create-vm
PLAN    move-ip-to-vm-interface
PLAN    set-vm-primary-ip
PLAN    unset-device-primary-ip
PLAN    sync-tags
DONE    already-migrated
DONE    tags-ok
SKIP    missing-required-field
```

That output lets you count planned work before making changes:

```bash
rg -c '^PLAN\tcreate-vm' Generated/migrate-cluster-a.dry-run.tsv
rg -c '^DONE\talready-migrated' Generated/migrate-cluster-a.dry-run.tsv
rg -c '^SKIP' Generated/migrate-cluster-a.dry-run.tsv
```

The goal is to make the dry run boring before the apply.

## Apply In Small Batches

For cluster-scoped migration, the operating loop is:

```text
1. dry run one cluster tag
2. review planned creates/skips
3. apply one cluster tag
4. dry run tag sync
5. apply tag sync
6. verify tagged virtualization VM count
7. move to the next cluster
```

Do not jump from one successful cluster to a fleet-wide write unless the script has already proven idempotent behavior across the same object model.

## Tags Are Part Of The Data Model

One subtle failure mode is that a cluster tag may exist, but only be valid for DCIM devices or IP addresses.

If the tag is not scoped for virtualization VMs, the migrated VM can exist but not be discoverable through the same tag-based workflows operators used before.

The audit for that is simple:

```bash
curl -fsS -H "$AUTH" "$NETBOX_URL/api/extras/tags/?limit=1000" \
  | jq -r '.results[]
      | select(.slug | startswith("cluster-"))
      | [.slug, (.object_types | join(","))] | @tsv' \
  | awk -F '\t' '$2 !~ /virtualization\.virtualmachine/ {print}'
```

Expected output:

```text
<no output>
```

That means every `cluster-*` tag can be applied to virtualization VMs.

## Terraform Comes After The Inventory Shape Is Correct

Once NetBox virtualization objects exist, Terraform state can be imported into the shared module shape.

The safe checkpoint looks like this:

```text
NetBox VM resources:        no-op
NetBox interface resources: no-op
NetBox IP resources:        no-op
NetBox primary IP:          no-op
vSphere VM resources:       update
```

That is a useful result. It means NetBox is reconciled and the remaining drift is isolated to vSphere.

It does not mean the full plan should be applied.

## When Drift Means Replacement

Existing VMs often carry old-template drift:

- CPU and memory hot-add settings.
- datastore placement.
- port group attachment.
- missing or different guestinfo metadata.
- clone/customize metadata differences.
- disk label mismatches.
- extra worker disks outside the module model.

For Kubernetes nodes, especially control-plane and etcd members, applying those differences in place can be the wrong operational move. The better answer may be replacement-node lifecycle: build new nodes with the current module and template, join them, drain old nodes, and retire the legacy VMs one at a time.

## The Practical Lesson

A NetBox migration is not complete when the new objects exist.

It is complete when:

```text
objects exist in the correct NetBox model
IPs are attached to the correct VM interfaces
primary IPs are set
tags are synced
tag scopes support the new object type
Terraform imports are clean
full-plan drift is classified
unsafe vSphere changes are blocked
```

That is the difference between data cleanup and operational control.

Related Field Notes:

- [NetBox Cluster Tag Scope Audit](/field-notes/netbox-cluster-tag-scope-audit/)
- [NetBox DCIM Device To VM Migration Dry Run Pattern](/field-notes/netbox-dcim-device-to-vm-migration-dry-run-pattern/)
- [Replacement Node Workflow After Terraform Import Drift](/field-notes/replacement-node-workflow-after-terraform-import-drift/)
