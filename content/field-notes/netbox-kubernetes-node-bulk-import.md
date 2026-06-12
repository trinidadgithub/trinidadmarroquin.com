+++
title = 'NetBox Bulk Import Order For Kubernetes Nodes'
date = 2026-06-12T00:00:00-05:00
draft = false
description = 'Field note for importing Kubernetes VM node inventory into NetBox using ordered device, interface, and IP address CSV files.'
tags = ['netbox', 'kubernetes', 'ipam', 'automation', 'operations']
categories = ['field-notes']
+++

NetBox imports are safest when object relationships are created in dependency order.

For Kubernetes VM nodes, split the import into devices, interfaces, and IP addresses instead of trying to represent everything as one operation.

## Import Order

Use this order:

```text
1. devices.csv
2. interfaces.csv
3. ip-addresses.csv
```

Why:

- interfaces need devices to exist first.
- IP addresses need interfaces to exist before assignment.
- primary IP selection is a device relationship and may need a later update.

## Device CSV

Example shape:

```csv
name,role,manufacturer,device_type,site,status,tags,comments
cluster-a-cp-01,Server,VMware,Virtual Machine,site-a,active,"cluster-a-prod,k8s-node,control-plane",Kubernetes control-plane node
cluster-a-worker-01,Server,VMware,Virtual Machine,site-a,active,"cluster-a-prod,k8s-node,worker",Kubernetes worker node
```

Confirm these objects exist before import:

- site.
- role.
- manufacturer.
- device type.
- tags.

Do not assume the NetBox UI will create tags with the slugs you want. Pre-create important tags when naming consistency matters.

## Interface CSV

Example shape:

```csv
device,name,type,enabled
cluster-a-cp-01,mgmt0,virtual,true
cluster-a-worker-01,mgmt0,virtual,true
```

For virtual machines, `virtual` is usually clearer than a physical media type unless your NetBox model intentionally tracks the emulated adapter type.

Keep the management interface name consistent. `mgmt0` is simple and predictable for automation.

## IP Address CSV

Example shape:

```csv
address,status,dns_name,description,device,interface
192.0.2.10/24,active,cluster-a-cp-01.example.internal,Kubernetes control-plane management IP,cluster-a-cp-01,mgmt0
192.0.2.20/24,active,cluster-a-worker-01.example.internal,Kubernetes worker management IP,cluster-a-worker-01,mgmt0
192.0.2.2/24,reserved,cluster-a-api.example.internal,Kubernetes API VIP,,
```

VIPs can be intentionally unassigned. Make that explicit with `reserved` status and blank device/interface fields.

## Validation Checklist

Before import, verify:

- no duplicate device names.
- no duplicate IP addresses.
- no duplicate DNS names where uniqueness matters.
- every interface references a device in `devices.csv`.
- every assigned IP references a device/interface pair in the generated files.
- every IP belongs to the expected prefix.
- VIPs are intentionally unassigned.
- required NetBox objects already exist.

## Operating Rule

Generate CSVs from source data, then validate the relationships before opening the NetBox UI.

If the validation finds duplicate device names or ambiguous ownership, stop and resolve the naming decision before import.
