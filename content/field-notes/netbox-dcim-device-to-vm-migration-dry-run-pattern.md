+++
title = 'NetBox DCIM Device To VM Migration Dry Run Pattern'
date = 2026-06-18T00:00:00-05:00
draft = false
description = 'Field note for running an idempotent NetBox DCIM-device to virtualization-VM migration with dry-run evidence, scoped applies, and tag synchronization.'
tags = ['netbox', 'migration', 'automation', 'audit', 'operations']
categories = ['field-notes']
+++

Use a dry-run-first workflow when migrating VMware inventory from NetBox DCIM devices to virtualization VMs.

The script should be idempotent: running it again should report `already-migrated` or `tags-ok`, not create duplicates.

## Recommended Script Modes

Useful modes for a migration helper:

```text
--cluster-tag <slug>                 process one cluster tag
--all-cluster-devices                discover all DCIM devices with cluster tags
--all-matching-vms                   validate all matching migrated VMs
--sync-tags-only                     sync tags without creating VMs
--ensure-vm-tag-scope                allow the selected cluster tag on VMs
--ensure-all-cluster-tag-scopes      repair all cluster tag scopes
--apply                              perform writes after dry-run review
```

Keep dry-run as the default. Make writes require an explicit flag.

## Step 1: Cluster-Scoped Dry Run

```bash
python3 Generated/migrate-dcim-devices-to-vms.py \
  --cluster-tag cluster-site-a-prod-rke2 \
  --ensure-vm-tag-scope \
  > Generated/migrate-cluster-site-a-prod-rke2.dry-run.tsv 2>&1
```

Summarize the output:

```bash
rg -c '^PLAN\tcreate-vm' Generated/migrate-cluster-site-a-prod-rke2.dry-run.tsv
rg -c '^DONE\talready-migrated' Generated/migrate-cluster-site-a-prod-rke2.dry-run.tsv
rg -c '^SKIP' Generated/migrate-cluster-site-a-prod-rke2.dry-run.tsv
```

Review skips before applying.

## Step 2: Apply One Cluster

```bash
python3 Generated/migrate-dcim-devices-to-vms.py \
  --cluster-tag cluster-site-a-prod-rke2 \
  --ensure-vm-tag-scope \
  --apply \
  > Generated/migrate-cluster-site-a-prod-rke2.apply.tsv 2>&1
```

Check writes:

```bash
rg -c '^DONE\tcreate-vm' Generated/migrate-cluster-site-a-prod-rke2.apply.tsv
rg -c '^DONE\talready-migrated' Generated/migrate-cluster-site-a-prod-rke2.apply.tsv
rg -c '^ERROR' Generated/migrate-cluster-site-a-prod-rke2.apply.tsv
```

## Step 3: Sync Tags Separately

VM creation and tag synchronization should be separate operations.

Dry run:

```bash
python3 Generated/migrate-dcim-devices-to-vms.py \
  --cluster-tag cluster-site-a-prod-rke2 \
  --sync-tags-only \
  --ensure-vm-tag-scope \
  > Generated/sync-cluster-site-a-prod-rke2.dry-run.tsv 2>&1
```

Apply:

```bash
python3 Generated/migrate-dcim-devices-to-vms.py \
  --cluster-tag cluster-site-a-prod-rke2 \
  --sync-tags-only \
  --ensure-vm-tag-scope \
  --apply \
  > Generated/sync-cluster-site-a-prod-rke2.apply.tsv 2>&1
```

Verify:

```bash
rg -c '^DONE\tsync-tags' Generated/sync-cluster-site-a-prod-rke2.apply.tsv
rg -c '^DONE\ttags-ok' Generated/sync-cluster-site-a-prod-rke2.apply.tsv
```

## Step 4: Re-Run For Idempotency

After apply, run the dry run again.

Healthy output trends:

```text
create-vm: 0
sync-tags: 0
already-migrated: expected count
tags-ok: expected count
errors: 0
```

This is the evidence that the migration can be resumed safely.

## Script Hardening Notes

For long-running inventory scripts, add:

- immediate log flushing.
- a reasonable HTTP timeout.
- tag scope caching.
- explicit dry-run/apply output prefixes.
- support for one-cluster scoping.
- support for tag-only repair.

Those small features make the script operable during a real migration window.

## Operating Rule

Do not migrate the whole fleet first.

Migrate one cluster, sync tags, verify counts, rerun for idempotency, then expand the scope.
