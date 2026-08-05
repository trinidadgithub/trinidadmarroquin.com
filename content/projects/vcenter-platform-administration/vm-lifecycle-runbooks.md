+++
title = 'VM Lifecycle Runbooks'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial runbook model for vCenter VM lifecycle, capacity review, maintenance, and incident response.'
tags = ['vsphere', 'vmware', 'operations']
categories = ['projects']
+++

VM lifecycle runbooks should make common operations repeatable without hiding the risks.

The same lifecycle pattern applies whether the VM is a Kubernetes node, platform appliance, or application server.

## Lifecycle States

Track each VM through clear states:

- requested.
- provisioned.
- configured.
- in service.
- maintenance.
- retired.
- deleted.

Each state should have an owner and exit criteria.

## Standard Runbooks

Useful runbooks include:

- provision a VM from template.
- resize CPU, memory, or disk.
- add or change network adapters.
- audit or remove unused virtual CD-ROM devices.
- snapshot before risky maintenance.
- restore from backup or snapshot.
- retire and delete a VM.
- investigate guest customization failure.

Each runbook should list read-only verification commands first, then mutation steps.

## Capacity Review

Capacity review should include:

- cluster CPU and memory headroom.
- datastore utilization and growth rate.
- snapshot age and size.
- VM sprawl and powered-off inventory.
- resource pool constraints.
- HA and maintenance mode headroom.

Capacity is not just percent used. It is whether the platform can tolerate failure and maintenance.

## Incident Response

During an incident, preserve evidence:

- vCenter task history.
- VM events.
- datastore alarms.
- host health.
- recent automation runs.
- guest logs when accessible.

Avoid making multiple speculative changes at once. vCenter incidents often cross host, storage, network, and guest boundaries. For a specific virtual media cleanup pattern, see [vSphere CD-ROM Host Device Cleanup With govc](/field-notes/vsphere-cdrom-host-device-cleanup-govc/).

## References

- VMware vSphere documentation: vCenter Server and Host Management.
- VMware vSphere documentation: Working with vSphere Tasks.
- VMware vSphere documentation: Troubleshooting Overview.
