+++
title = 'NetBox Primary IP Assignment After Import'
date = 2026-06-12T00:00:00-05:00
draft = false
description = 'Field note for setting NetBox device primary IPv4 addresses after bulk importing devices, interfaces, and IP assignments.'
tags = ['netbox', 'ipam', 'automation', 'api', 'operations']
categories = ['field-notes']
+++

Importing an IP address and assigning it to an interface does not always mean the device's `primary_ip4` field is set.

Treat primary IP assignment as a separate verification and update step.

## Input File

Use a small mapping file:

```csv
name,primary_ip4
cluster-a-cp-01,192.0.2.10/24
cluster-a-worker-01,192.0.2.20/24
```

The address should match the existing NetBox IP object, including prefix length if your NetBox query requires it.

## Safe Update Logic

For each row:

- query device by exact name.
- query IP address by exact address.
- require exactly one device match.
- require exactly one IP match.
- skip blank rows.
- skip ambiguous rows.
- support dry-run mode.
- patch only the device `primary_ip4` field.

Ambiguity should stop the row, not trigger guessing.

## Example API Flow

Pseudo-flow:

```text
GET /api/dcim/devices/?name=<device-name>
GET /api/ipam/ip-addresses/?address=<address>
PATCH /api/dcim/devices/<id>/ {"primary_ip4": <ip-id>}
```

Dry-run output should show:

```text
DRY RUN: cluster-a-cp-01 -> 192.0.2.10/24 (device_id=123 ip_id=456)
```

Only run the patch after the dry run shows the expected device/IP pairs.

## Verification

After the update:

- open a few representative devices in the UI.
- filter devices by cluster tag.
- confirm primary IPv4 is populated.
- confirm VIPs remain reserved and unassigned if that was intended.
- confirm no unexpected device count changes occurred.

## Operating Rule

Primary IP assignment is a relationship update, not just an IPAM import.

Make it idempotent, exact-match only, and safe to dry-run.
