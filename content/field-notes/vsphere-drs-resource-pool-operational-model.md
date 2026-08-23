+++
title = 'vSphere DRS And Resource Pool Operational Model'
date = 2026-08-23T00:00:00-05:00
draft = false
description = 'Field note for operating vSphere DRS and resource pools without hiding capacity constraints, ownership ambiguity, or automation placement risk.'
tags = ['vsphere', 'vcenter', 'vmware', 'drs', 'resource-pools', 'capacity', 'operations']
categories = ['field-notes']
+++

DRS and resource pools are useful when they express an operating model. They are dangerous when they become a second, invisible capacity plan.

The mistake is assuming a resource pool is just a folder with limits. It is not. It changes scheduling behavior, and automation that deploys into it inherits those rules.

## DRS Is A Policy, Not Magic

DRS helps place and rebalance workloads inside the cluster's constraints. It cannot create host capacity, fix datastore contention, or make incompatible workloads safe to colocate.

Review DRS with these questions:

- Is automation allowed to rely on automatic placement?
- Are anti-affinity rules documented and still valid?
- Are maintenance-mode evacuations expected to complete without manual placement?
- Are there pinned or partially automated VMs that DRS cannot move?
- Do operators know when to override recommendations?

DRS recommendations are evidence. They are not a substitute for understanding why the cluster is constrained.

## Resource Pool Ownership

Use resource pools only when there is a clear reason:

- separating platform capacity from application capacity.
- protecting critical management services from noisy tenants.
- expressing quota or chargeback boundaries.
- giving Terraform a stable placement target with intentional shares and reservations.

Avoid pools that exist only because a team wanted a visual grouping. Folders and tags are usually better for inventory organization. Resource pools should affect scheduling on purpose.

For each resource pool, record:

```text
owner
purpose
reservation / limit / shares policy
expected workload class
automation consumers
review cadence
deletion or retirement criteria
```

If nobody owns the policy, nobody owns the capacity risk.

## Limits Need Operational Justification

Limits are easy to set and easy to forget. A limit that made sense during a test can become a production incident later.

Before setting or keeping a limit, ask:

- What failure does this limit prevent?
- Who is paged when the pool is constrained?
- How will saturation be detected?
- Can critical VMs starve while the cluster still has spare capacity?
- Does Terraform or a provisioning module deploy into this pool by default?

Prefer documented reservations and shares for priority modeling. Use hard limits only when the operational consequence is intentional and monitored.

## Validation Checks

Before promoting a new placement policy, validate:

- resource pool path used by Terraform is stable.
- DRS rules do not conflict with expected VM count or host count.
- HA can restart the protected workload under the pool policy.
- maintenance-mode simulation or rehearsal succeeds for at least one host.
- monitoring sees pool-level CPU and memory pressure.
- runbooks explain when manual vMotion is acceptable.

The test is not "can I create a VM?" The test is "will scheduling behavior stay explainable during failure and maintenance?"

## Failure Model

The quiet failure looks like this:

```text
resource pool created -> Terraform starts using it
-> limits/shares drift -> DRS follows policy correctly
-> workloads starve while cluster capacity appears available
```

The system is doing what it was told. The problem is that nobody still owns what it was told.

The operating rule: folders organize inventory; resource pools allocate capacity. Do not use one when you mean the other.
