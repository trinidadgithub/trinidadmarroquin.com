+++
title = 'Terraform Module Composition Patterns'
date = 2026-08-10T00:00:00-05:00
draft = false
description = 'Operational field note for Terraform module composition: caller-owned vs module-owned decisions, nesting, for_each boundaries, outputs as contracts, and the failures that come from over-abstraction.'
tags = ['terraform', 'modules', 'hcl', 'platform-engineering', 'operations', 'infrastructure']
categories = ['field-notes']
+++

Module composition is where Terraform repos go from readable to unmaintainable.

A module is a way to package decisions and raise the abstraction level. Done well, it reduces duplication and concentrates behavior. Done badly, it hides ownership, buries `for_each` keys, and turns every apply into a refactor.

This note covers composing modules so the ownership boundaries stay visible.

## What A Module Should Own

A module should own one operational concept and expose the minimum contract needed to use it.

Before extracting any module, answer:

- what resource group does this wrap?
- what inputs must vary per caller or environment?
- what outputs do callers consume?
- what invariants must stay true after apply?
- what failure mode does this abstraction hide?

If those answers are unclear, the folder of resources is not a module yet, it is a name.

## Caller-Owned Versus Module-Owned Decisions

Good composition divides decisions carefully.

Caller-owned:

- resource names and tagging.
- environment-specific sizing and counts.
- network and dependency wiring into other modules.
- which provider and region the resource lands in.

Module-owned:

- internal resource wiring.
- safe defaults for settings that rarely change.
- invariants and validation.
- the internal list of optional resources.

A module should not pull in the caller's environment, region, or provider decisions unless it is genuinely a vertical slice.

## Keep Nesting Shallow

Deep module trees make plans hard to read and state hard to reason about.

```text
root
  module.network
    module.subnets          <- useful if truly vertical
      module.igw            <- rarely worth it
        module.eip          <- almost never worth it
```

Rule of thumb: if a module has a single resource or a single configurable output, it is usually indirection instead of abstraction.

## for_each Belongs At The Right Level

Decide where `for_each` lives and keep it there.

- Module called with `for_each` over environments or site keys: clean, as long as whole-instance ownership is consistent.
- `for_each` inside a module over a list that should vary by caller: hide the caller's real decision.
- Nested `for_each` inside `for_each` over maps with computed keys: source of plan noise and state breakage.

When a module instance represents one logical object per environment, drive that with `for_each` at the call site and keep the module itself single-instance:

```hcl
module "vm_group" {
  source   = "./modules/vm_group"
  for_each = local.environments
  ...
}
```

## Outputs Are Contracts

Outputs are the module's public interface to other callers and to plan review.

Expose:

- values other modules or roots actually consume.
- identifier and reference values needed for dependencies.
- a bounded, human-readable set, not every internal attribute.

Avoid:

- outputting entire resource attributes when only one field is needed.
- recomputing mashups in the root when the module should own the shape.
- optional outputs with ambiguous meaning across environments.

An output that is unused anywhere is dead contract. Plan reviewers and future maintainers will still try to hold it stable.

## Composing Without Coupling

Two modules that both need the same VPC ID should receive it as input, not import the other module.

```hcl
module "network" {
  source = "./modules/network"
  ...
}

module "compute" {
  source     = "./modules/compute"
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
}
```

The dependency is expressed through inputs and outputs, not through importing one module tree into another. That keeps each module independently testable and reviewable.

## Composition Failure Modes

### The God Module

A module grows to wrap dozens of unrelated resources because "they all go together." Ownership, review blast radius, and state boundaries blur.

### Indirection Without Abstraction

A single-resource module adds a call layer without raising the abstraction level. Cleanup cost shows up in every future refactor.

### Hidden Caller Decisions

The module computes names, sizing, or placement inside itself, so callers cannot express their real environment differences without editing module source.

### Output Coupling

Roots and other modules depend on outputs that keep changing shape. Every minor module change ripples across every caller.

### Drifting Module Trees

Environment copies of the module diverge because the shared copy is never versioned. Fixes happen in the copy, not the source.

## Composition Review Checklist

- Does the module wrap one operational concept?
- Are environment- and caller-specific decisions inputs, not internals?
- Is `for_each` at the level where ownership actually varies?
- Are outputs a stable, minimal contract?
- Are inter-module dependencies expressed through inputs and outputs?
- Is the tree shallow enough that a plan is readable?
- Does the module have a named owner?
- Is there at least one example root consuming it?

## Practical Takeaway

Modules should raise the abstraction level, not add indirection.

Keep each module to one operational concept, drive caller differences through inputs, expose a stable output contract, and express dependencies with data, not module imports. The test of good composition is a plan an operator can still review.

## References

- [Terraform Module Input Summary Pattern](/field-notes/terraform-module-input-summary-pattern/)
- [Terraform State Moves During A Module Refactor](/field-notes/terraform-state-move-module-refactor/)
- [Terraform Operational Module Boundaries](/projects/terraform-infrastructure-modules/operational-module-boundaries/)