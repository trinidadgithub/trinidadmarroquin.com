+++
title = 'vCenter Automation Integration Points'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial model for vCenter integration points with Terraform, Packer, Kubernetes nodes, CSI storage, and backup workflows.'
tags = ['vsphere', 'terraform', 'packer', 'kubernetes']
categories = ['projects']
+++

Automation works best when vCenter exposes stable contracts.

Terraform, Packer, Kubernetes, CSI drivers, and backup tools all depend on vCenter inventory behaving predictably.

## Terraform Contracts

Terraform needs stable references for:

- datacenters.
- clusters and resource pools.
- datastores and datastore clusters.
- folders.
- port groups.
- templates.
- tags and custom attributes.

If these names change casually, infrastructure code becomes fragile.

## Packer Contracts

Packer needs a reliable build path:

- build network.
- ISO or content library access.
- temporary VM folder.
- template destination.
- credentials with limited build permissions.
- cleanup behavior for failed builds.

Template promotion should include validation before downstream Terraform consumes the image.

## Kubernetes And CSI Contracts

Kubernetes nodes rely on vCenter for VM placement, disks, networking, and CSI integration.

Document node requirements such as:

- VM hardware version.
- VMware tools health.
- `disk.EnableUUID = "TRUE"` for vSphere CSI.
- port group assignment.
- datastore policy.
- backup exclusions or inclusions.

## Backup Workflows

Backup tooling needs clear policy:

- which VMs are protected.
- which disks are excluded.
- snapshot coordination expectations.
- restore test cadence.
- application-consistent versus crash-consistent behavior.

## References

- VMware vSphere documentation: vCenter Server and Host Management.
- Terraform vSphere provider documentation.
- HashiCorp Packer documentation.
