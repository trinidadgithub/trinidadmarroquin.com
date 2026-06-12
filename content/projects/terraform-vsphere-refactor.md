+++
title = 'Refactoring A vSphere Terraform Repo Into Environment Roots And Shared Modules'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'A Terraform infrastructure project writeup about reorganizing a vSphere repo into environment roots, shared modules, templates, and archived legacy state.'
tags = ['terraform', 'vsphere', 'infrastructure', 'sre']
categories = ['projects']
+++

This project started as a repository cleanup and turned into a clearer operating model for vSphere infrastructure.

The original Terraform repo had grown into a collection of copied root modules. Each site and environment had its own directory with a familiar set of files: `main.tf`, `variables.tf`, `output.tf`, `terraform.tfvars`, `vars.auto.tfvars`, `vars.env`, local state files, and copied templates. That worked while the repo was small, but it made every change harder to review.

The target was not to make the repo clever. The target was to make it understandable.

## Goals

- Group active infrastructure by site and environment.
- Move repeated VM creation logic into a shared module.
- Preserve historical state and templates without letting them clutter active work.
- Separate Terraform inputs from operator helper files.
- Make future changes easier to validate with `terraform plan`.

## Target Layout

The refactor moved toward this structure:

```text
terraform-vsphere-platform/
  environments/
    site-a/prod/
    site-a/nonprod/
    site-b/nonprod/
    site-c/tools/
  modules/
    vsphere-vm-group/
  templates/
  archive/
    legacy-roots/
    legacy-state/
    legacy-templates/
```

The important design choice was `environments/<site>/<env>`. That keeps production and nonproduction roots near each other, makes site ownership visible, and avoids long historical directory names like `Terraform-Site-A-prod`.

## Module Boundary

The first reusable module was not a single VM module. The existing Terraform already created groups of VMs from a map, so the correct initial module boundary was a VM group:

```text
modules/vsphere-vm-group/
  main.tf
  variables.tf
  outputs.tf
  versions.tf
```

That module owns repeated vSphere behavior: datacenter, datastore, cluster, network, template lookups, VM cloning, disks, guest customization, and outputs. Environment roots own inventory: VM names, IPs, site settings, gateway, DNS, resource pool, template choice, and operational flags.

## Migration Approach

The repo move was done with a dry-run migration script before moving files for real. That mattered because the repo contained state files, old templates, nested `.terraform` directories, one-off rebuilds, and historical folders.

The script created the new layout, moved active environment files, archived local state, and copied templates conservatively. A small directory-creation cache made the dry-run output readable instead of repeating the same `mkdir -p` lines hundreds of times.

After the move, empty legacy directories were removed only after inspection. That kept the Git history clean and made the refactor reviewable.

## State Safety

Moving a Terraform resource into a module changes its address. For example:

```text
vsphere_virtual_machine.vm["lb1"]
```

becomes:

```text
module.vm_group.vsphere_virtual_machine.vm["lb1"]
```

That requires explicit state movement before apply:

```bash
terraform state mv \
  'vsphere_virtual_machine.vm["lb1"]' \
  'module.vm_group.vsphere_virtual_machine.vm["lb1"]'
```

The validation target was simple: after state movement, `terraform plan` should show no unexpected destroy/recreate behavior.

## Operational Lessons

The refactor surfaced more than file duplication. It exposed hidden ownership boundaries between Terraform, vSphere customization, Packer-built templates, cloud-init, bootstrap scripts, netplan, and iSCSI configuration.

The most useful outcome was a clearer model:

- Terraform owns VM intent and vSphere resource configuration.
- Environment roots own site-specific inventory and values.
- Shared modules own repeated provisioning behavior.
- Packer owns the template baseline.
- Bootstrap owns first-boot operating system configuration that must vary by environment.
- CSI owns volume lifecycle after the node joins Kubernetes.

## Result

The repo became easier to scan, safer to change, and better aligned with how the infrastructure is operated. The refactor also created a reusable pattern for future site migrations: move layout first, preserve behavior, validate plans, then improve module behavior one environment at a time.

That is the useful version of infrastructure modernization: fewer surprises, clearer ownership, and smaller changes that operators can reason about under pressure.
