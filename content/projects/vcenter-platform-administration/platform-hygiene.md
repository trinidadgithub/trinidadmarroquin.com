+++
title = 'vCenter Platform Hygiene'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial operating standards for vCenter cluster, datastore, network, template, tag, and permission hygiene.'
tags = ['vsphere', 'vmware', 'vcenter']
categories = ['projects']
+++

vCenter hygiene is the difference between a virtualization platform and a pile of VMs.

The goal is to keep inventory, networks, storage, permissions, and templates understandable enough that automation can safely depend on them.

## Inventory Organization

Folders, tags, and naming should expose ownership and lifecycle.

Recommended metadata:

- environment.
- application or platform owner.
- lifecycle state.
- backup policy.
- automation owner.
- cost or capacity group.

Use vSphere tags and custom attributes for metadata that operators need to search, report, or automate against.

## Datastores And Networks

Datastore and port group names should be stable contracts for automation.

Review regularly:

- datastore free space and overcommitment.
- orphaned disks and snapshots.
- port groups no longer used.
- VLAN or distributed switch drift.
- datastore clusters and placement rules.

Terraform and Packer depend on consistent names. Rename operations should be treated as platform changes.

## Template Hygiene

Templates should be versioned, patched, and retired intentionally.

Baseline expectations:

- current OS patches.
- VMware tools installed and healthy.
- cloud-init or guest customization readiness documented.
- stale machine identity removed before sealing.
- bootstrap prerequisites installed.
- template version and build date visible.

## Permissions

Use least privilege roles for automation accounts. Avoid giving broad administrator access to every tool that touches vCenter.

Separate roles for:

- template build.
- VM provisioning.
- read-only inventory discovery.
- backup operations.
- break-glass administration.

## References

- VMware vSphere documentation: vCenter Server and Host Management.
- VMware vSphere documentation: Tags and Custom Attributes.
- VMware vSphere documentation: Organizing Your vSphere Inventory.
