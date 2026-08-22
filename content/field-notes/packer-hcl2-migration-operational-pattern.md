+++
title = 'Packer HCL2 Migration Operational Pattern'
date = 2026-08-21T00:00:00-05:00
draft = false
description = 'Field note for migrating Packer templates to HCL2 without losing validation, variable ownership, plugin pinning, or image promotion safety.'
tags = ['packer', 'hcl2', 'images', 'automation', 'validation']
categories = ['field-notes']
+++

Migrating Packer templates to HCL2 is not just a syntax cleanup. It changes how operators reason about variables, plugin versions, reusable blocks, and what the pipeline can validate before a build starts.

The goal is not to make the file look modern. The goal is to make image builds easier to review, safer to parameterize, and less dependent on undocumented wrapper behavior.

## Preserve The Operating Boundary

Do not use an HCL2 migration to move runtime configuration back into the image.

The same boundary still applies:

```text
Packer HCL       -> reusable image mechanism
site variables   -> build target and infrastructure placement
secrets backend  -> credentials used by the build runner
Terraform/cloud-init/bootstrap -> clone-specific runtime behavior
```

If the old JSON template kept domain names, cluster tokens, static IPs, or environment-specific bootstrap values in loose variables, migration is the moment to move those values out of the image path.

HCL2 makes bad ownership easier to see. Use that visibility.

## Convert In Reviewable Slices

Avoid a migration shaped like:

```text
convert every template -> change every variable -> upgrade every plugin -> rewrite pipeline
```

That creates a diff nobody can audit.

A safer sequence is:

```text
pin current behavior -> convert one template -> validate equivalent build
-> extract shared locals/modules -> upgrade plugins intentionally
```

Keep the first converted template boring. Same source ISO, same provisioners, same output naming, same validation gate. The first win is equivalence, not elegance.

## Make Variables Legible

HCL2 gives variables type, validation, and defaults. Use those to separate required site inputs from optional tuning.

Useful boundaries:

- vSphere placement: datacenter, cluster, datastore, folder, network.
- build access: temporary username, communicator settings, WinRM or SSH behavior.
- image identity: OS family, OS version, image role, version suffix.
- feature flags: optional packages, hardening profile, bootstrap inclusion.
- secrets: passed by the runner, not committed in variable files.

Do not hide required site behavior in untyped maps unless the indirection pays for itself. Operators should be able to answer "what changes between sites?" without reading every provisioner.

## Pin Plugins And Packer Version

HCL2 makes plugin source and version constraints explicit through `required_plugins`. That is useful only if the pipeline treats those constraints as part of the artifact's supply chain.

Record:

- Packer version used for the build.
- plugin source and version constraints.
- resolved plugin versions in the build log or metadata record.
- Git commit of the template repository.

Then a future rebuild can answer whether a changed image came from template code, a plugin upgrade, a base ISO change, or external infrastructure.

## Keep Validation Gates Intact

The migration is not done when `packer validate` passes.

Use staged gates:

```text
packer fmt -> packer validate -> build disposable template
-> clone test -> metadata comparison -> promotion
```

Compare the migrated template against the old one for the things operators actually rely on:

- image name and versioning convention.
- installed package and agent baseline.
- VMware Tools or guest agent health.
- cleanup and sealing behavior.
- post-clone customization readiness.
- artifact metadata retained by the pipeline.

If the HCL2 template produces a syntactically valid but operationally different image, the migration changed behavior. That can be acceptable, but it should not be accidental.

## Failure Model

The common failure is treating HCL2 as a refactor with no runtime consequence:

```text
template converts -> validation passes -> plugin behavior changes
-> image builds -> clone test skipped -> consumers inherit drift
```

The fix is boring: migrate one image path, preserve validation gates, retain artifact metadata, and promote only after a clone proves the result.

The operating rule is simple: HCL2 should make the image factory more explainable, not merely more fashionable.
