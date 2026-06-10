+++
title = 'Terraform Operational Module Boundaries'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial guidance for Terraform module boundaries that match operational ownership and avoid unnecessary abstraction.'
tags = ['terraform', 'modules', 'operations']
categories = ['projects']
+++

Terraform modules should represent operational concepts, not just folders around resources.

HashiCorp guidance recommends moderation: modules are useful when they raise the abstraction level, but thin wrappers around single resources often add complexity without improving ownership.

## Boundary Principles

Good module boundaries answer:

- Who owns this infrastructure after apply?
- What lifecycle does it follow?
- What inputs must vary by environment?
- What outputs does another layer consume?
- What failure modes does the module hide or expose?

Avoid modules that combine unrelated ownership domains. A Kubernetes node module, network module, and storage module may interact, but they are not necessarily owned by the same team or changed on the same cadence.

## Root Modules

Root modules should map to deployable units:

```text
environments/prod/network
environments/prod/compute
environments/nonprod/kubernetes
```

This makes plan review safer because the blast radius is visible from the working directory.

## Reusable Modules

Reusable modules should have:

- clear inputs.
- stable outputs.
- examples.
- versioning.
- provider requirements.
- assumptions documented near the code.

Keep module trees relatively flat. Deep nesting makes ownership and state movement harder to understand.

## Acceptance Criteria

- Each module has a named operational owner.
- Root modules match environment and blast-radius boundaries.
- Reusable modules expose architecture-level concepts.
- Module outputs are intentional contracts.
- Refactors use moved blocks or explicit state moves.

## References

- Terraform documentation: Creating Modules.
- Terraform documentation: Best Practices for Composing Modules.
- Terraform documentation: Refactoring Modules.
