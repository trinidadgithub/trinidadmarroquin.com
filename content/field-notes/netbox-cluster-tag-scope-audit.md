+++
title = 'NetBox Cluster Tag Scope Audit'
date = 2026-06-18T00:00:00-05:00
draft = false
description = 'Field note for auditing NetBox cluster tags so they can be assigned to virtualization VMs after DCIM-to-VM inventory migration.'
tags = ['netbox', 'kubernetes', 'ipam', 'audit', 'operations']
categories = ['field-notes']
+++

When NetBox inventory moves from DCIM devices to virtualization VMs, tags need their own audit.

A tag can exist and still be wrong for the new object model. If a cluster tag is scoped only to DCIM devices or IP addresses, migrated virtualization VMs may not be taggable or discoverable through normal cluster filters.

## Audit Cluster Tag Scopes

Set API variables:

```bash
NETBOX_URL="${NETBOX_URL:-https://netbox.example.com}"
TOKEN="${NETBOX_TOKEN:-}"

case "$TOKEN" in
  nbt_*) AUTH="Authorization: Bearer $TOKEN" ;;
  *)     AUTH="Authorization: Token $TOKEN" ;;
esac
```

List `cluster-*` tags missing virtualization VM scope:

```bash
curl -fsS -H "$AUTH" "$NETBOX_URL/api/extras/tags/?limit=1000" \
  | jq -r '.results[]
      | select(.slug | startswith("cluster-"))
      | [.slug, (.object_types | join(","))] | @tsv' \
  | awk -F '\t' '$2 !~ /virtualization\.virtualmachine/ {print}'
```

Expected output after cleanup:

```text
<no output>
```

## Why It Matters

Cluster tags are often used for:

- filtering nodes in the NetBox UI.
- scoping scripts to one cluster.
- selecting inventory for CSV export.
- validating migrated VM counts.
- grouping Terraform import targets.

If the tag does not support `virtualization.virtualmachine`, those workflows silently become incomplete.

## Repair Pattern

Use a script or API patch that preserves existing object types and appends the VM type.

Target state:

```text
dcim.device
ipam.ipaddress
virtualization.virtualmachine
```

Do not replace the whole object type list unless the script first reads the current tag and merges existing values.

## Verify Tagged VM Counts

After scope repair and tag sync, verify VM counts by cluster tag:

```bash
for slug in cluster-site-a-prod-rke2 cluster-site-a-uat-rke2; do
  printf '%s\t' "$slug"
  curl -fsS -H "$AUTH" \
    "$NETBOX_URL/api/virtualization/virtual-machines/?tag=$slug&limit=1" \
    | jq -r '.count'
done
```

Example output:

```text
cluster-site-a-prod-rke2    18
cluster-site-a-uat-rke2     14
```

The exact counts are less important than matching the expected cluster inventory.

## Final Check

Run both checks:

```text
missing VM tag scope: none
tagged VM counts: match expected inventory
```

Only then treat tag migration as complete.
