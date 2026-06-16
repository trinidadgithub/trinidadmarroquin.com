+++
title = 'Post-Provision VM State Verification With NetBox'
date = 2026-06-16T00:00:00-05:00
draft = false
description = 'Field note for verifying Terraform-managed vSphere VM metadata, interface assignment, IPAM state, DNS name, and cleanup behavior in NetBox after provisioning or resizing.'
tags = ['netbox', 'terraform', 'vsphere', 'ipam', 'automation', 'operations']
categories = ['field-notes']
+++

After Terraform creates or resizes a vSphere VM, verify NetBox reflects the same lifecycle state.

This check is separate from preflight. Preflight prevents unsafe allocation before apply. Post-provision verification proves source-of-truth state matches what Terraform just changed.

## Set Lookup Values

Use generic environment variables so the commands are reusable:

```bash
export VM_NAME="cluster-a-app-01"
export VM_IP="192.0.2.10"
export VM_DNS_NAME="cluster-a-app-01.example.com"
export NETBOX_CLUSTER_NAME="cluster-a"
```

NetBox API credentials:

```bash
export NETBOX_SERVER_URL="https://netbox.example.com"
export NETBOX_API_TOKEN="..."
```

## Verify VM Metadata

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/virtualization/virtual-machines/?name=$VM_NAME" \
  | jq '.results[] | {
      id,
      name,
      status: .status.value,
      cluster: .cluster.name,
      vcpus,
      memory_mb: .memory,
      disk_size_mb: .disk,
      primary_ip4: .primary_ip4.address
    }'
```

Confirm:

- one VM is returned.
- cluster is expected.
- status is expected.
- vCPU count matches Terraform.
- memory matches Terraform in MB.
- disk size matches Terraform in MB.
- primary IPv4 is populated.

## Verify Interface Assignment

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/virtualization/interfaces/?virtual_machine=$VM_NAME" \
  | jq '.results[] | {
      id,
      name,
      enabled,
      vm: .virtual_machine.name
    }'
```

Confirm the expected management interface exists and belongs to the VM.

## Verify IPAM Assignment

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/ipam/ip-addresses/?q=$VM_IP" \
  | jq '.results[] | {
      id,
      address,
      status: .status.value,
      dns_name,
      assigned_object_type,
      assigned_object: .assigned_object.name
    }'
```

Confirm:

- one IP is returned.
- address and prefix are expected.
- status is expected.
- DNS name is expected.
- assigned object points at the VM interface.

## Verify DNS Name Lookup In NetBox

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/ipam/ip-addresses/?dns_name=$VM_DNS_NAME" \
  | jq '.results[] | {
      id,
      address,
      dns_name,
      status: .status.value,
      assigned_object_type,
      assigned_object: .assigned_object.name
    }'
```

This catches cases where the IP exists but the recorded DNS name is stale or missing.

## Verify Cluster Membership

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/virtualization/virtual-machines/?cluster=$(jq -rn --arg value "$NETBOX_CLUSTER_NAME" '$value|@uri')" \
  | jq --arg vm_name "$VM_NAME" '.results[] | select(.name == $vm_name) | {
      id,
      name,
      status: .status.value,
      cluster: .cluster.name,
      vcpus,
      memory_mb: .memory,
      disk_size_mb: .disk,
      primary_ip4: .primary_ip4.address
    }'
```

This proves the VM appears under the expected virtualization cluster, not just by global name search.

## Verify Cleanup After Destroy

After applying a reviewed destroy plan, the VM and IP lookups should return zero records.

VM cleanup check:

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/virtualization/virtual-machines/?name=$VM_NAME" \
  | jq '.count'
```

Expected:

```text
0
```

IP cleanup check:

```bash
curl -s \
  -H "Authorization: Token $NETBOX_API_TOKEN" \
  -H "Accept: application/json" \
  "$NETBOX_SERVER_URL/api/ipam/ip-addresses/?q=$VM_IP" \
  | jq '.count'
```

Expected:

```text
0
```

## Operating Rule

NetBox verification should happen after create, after resize, and after destroy.

If Terraform owns VM lifecycle state, NetBox should show the same lifecycle state or be intentionally updated by the same apply.
