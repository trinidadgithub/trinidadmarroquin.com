+++
title = 'Building Guardrails Before Terraform Creates vSphere VMs'
date = 2026-06-15T00:00:00-05:00
draft = false
description = 'A practical walkthrough of using Terraform validation, NetBox ownership, vCenter checks, DNS checks, and network liveness tests to avoid VM and IP collisions before vSphere creates anything.'
tags = ['terraform', 'vsphere', 'netbox', 'automation', 'sre', 'operations']
categories = ['notes']
+++

The dangerous failure mode was simple: Terraform could be technically correct and still create the wrong thing.

A VM name might already exist in vCenter. An IP might already be active on the network but missing from NetBox. DNS might still resolve from an older system. NetBox might be unavailable. A plan might look routine while carrying enough ambiguity to clobber an existing workload.

The fix was not one control. It was a guardrail stack.

The goal was clear: before Terraform creates a vSphere VM, prove that the planned VM name and IP are safe across the systems that already know about infrastructure.

## The Boundary That Matters

For VM provisioning, Terraform usually owns desired state, but it is not the only source of truth.

The real environment also has:

- vCenter inventory.
- NetBox VM and IPAM records.
- DNS forward records.
- reverse DNS records.
- live hosts responding on the network.

If Terraform only validates its own input map, it can catch duplicate values inside the plan but miss everything that already exists outside the plan.

That is why the guardrails were split into layers:

```text
Terraform variable validation
  -> NetBox provider resources
  -> preflight checks against NetBox, vCenter, DNS, and network liveness
  -> vSphere VM creation
```

Each layer catches a different class of mistake.

## Terraform Validation Catches Local Mistakes

The first layer was inside the Terraform module. VM names and IPv4 addresses must be unique inside the planned VM map.

That catches problems like:

```text
vm-a -> 192.0.2.10
vm-b -> 192.0.2.10
```

or:

```text
key-a -> name = worker-01
key-b -> name = worker-01
```

Those failures should happen during `terraform plan`, before any provider starts creating infrastructure.

This layer is useful, but it only knows what is in the configuration.

## NetBox First, vSphere Second

The stronger pattern was to make NetBox ownership explicit before creating the vSphere VM.

The module planned NetBox records for:

- virtual machine.
- interface.
- IP address.
- primary IPv4 relationship.

Then the vSphere VM depended on the NetBox primary IP relationship.

That dependency is important. It makes NetBox more than documentation. It becomes a provisioning gate.

If NetBox already has the VM name, the NetBox VM resource fails. If NetBox already has the IP address, the NetBox IP resource fails. If NetBox is down or the cluster lookup fails, Terraform fails before vSphere creation proceeds.

That is the desired fail-closed behavior.

```text
NetBox unavailable
  -> Terraform cannot resolve/create NetBox records
  -> vSphere VM is not created
```

## Why Preflight Still Matters

NetBox-first provisioning is not enough by itself.

There are real situations where NetBox is incomplete or stale:

- a VM exists in vCenter but not in NetBox.
- an IP responds on the network but has no IPAM record.
- a DNS record still resolves after a system was removed.
- reverse DNS points to an old hostname.
- `govc` is missing configuration and the vCenter check silently becomes useless.

Those are exactly the cases a preflight script should catch.

The preflight workflow used the Terraform plan JSON as input:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
./scripts/preflight-vm-guardrails.sh --plan-json tfplan.json
```

From that plan, the script can inspect the planned VM names and static IP addresses, then check external systems before apply.

## The Checks That Paid Off

The useful preflight checks were intentionally boring:

- query NetBox for planned VM names.
- query NetBox for planned IP addresses.
- query vCenter with `govc` for planned VM names.
- resolve planned VM names with `getent hosts`.
- check reverse DNS with `dig -x` or `getent`.
- probe planned IPs with `nmap -sn -n`.
- fail explicitly if `govc` is required but not configured.

The last point matters more than it looks.

A skipped check is acceptable when it is explicit. A silently weakened check is not.

If vCenter checks are enabled and `govc` is not configured, the safe behavior is to fail with a clear message. Operators can rerun with `--skip-govc` when that is intentional.

## What Was Tested

The guardrail stack was tested against the failure modes that matter:

- clean new VM.
- duplicate IP inside Terraform config.
- duplicate VM name inside Terraform config.
- IP already exists in NetBox.
- VM name already exists in NetBox.
- VM exists in vCenter but not NetBox.
- IP is active on the network but not in NetBox.
- reverse DNS exists.
- forward DNS exists for the VM name.
- NetBox enabled without provider credentials.
- preflight without NetBox credentials.
- NetBox cluster missing.
- NetBox unreachable.

The important result was not that every command succeeded. The important result was that each unsafe condition failed in the correct place.

Some failures belong in `terraform plan`. Some belong in preflight. Some belong in provider lookups. The operator should know which layer is responsible for each class of risk.

## The Practical Lesson

Guardrails should be close to the action they protect.

Terraform validation catches mistakes in Terraform input. NetBox provider resources protect source-of-truth ownership. vCenter, DNS, and nmap preflight checks catch reality outside Terraform and NetBox.

The strongest design was not “trust NetBox” or “trust Terraform.” It was:

```text
Trust each system only for the thing it can actually prove.
```

Then make the VM creation step depend on those proofs.

Related Field Notes:

- [NetBox First Ownership For vSphere VM Provisioning](/field-notes/netbox-first-vsphere-vm-ownership/)
- [Terraform vSphere VM Preflight Guardrails](/field-notes/terraform-vsphere-vm-preflight-guardrails/)
- [Terraform VM Guardrail Test Matrix](/field-notes/terraform-vm-guardrail-test-matrix/)
