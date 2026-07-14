+++
title = 'Terraform Environment Scaffolding For Consistent vSphere Roots'
date = 2026-07-14T00:00:00-05:00
draft = false
description = 'Field note for generating consistent Terraform vSphere environment roots with standard files, blank tfvars, smoke tests, and README updates.'
tags = ['terraform', 'vsphere', 'automation', 'hcl', 'documentation', 'operations']
categories = ['field-notes']
+++

Copied Terraform environment roots are convenient until they drift. One root has a newer module call, another has an old variable name, a third has stale README instructions, and the next environment starts from whichever directory someone copied last.

Use a small scaffolding script when a repository has a standard root-module shape.

## What To Generate

For a vSphere environment root, generate the complete directory shape every time:

```text
environments/site-a/example/
  main.tf
  variables.tf
  locals.tf
  outputs.tf
  terraform.tfvars
  README.md
```

The script should create files that are immediately recognizable to operators:

- `main.tf` wires provider configuration and the shared module.
- `variables.tf` declares the environment inputs.
- `locals.tf` contains the VM list or per-environment object map.
- `outputs.tf` exposes useful VM and source-of-truth outputs.
- `terraform.tfvars` is blank or placeholder-only and ready for local population.
- `README.md` explains how to plan, preflight, apply, and destroy from that root.

Do not generate a half-root that still requires copying files by hand. The helper exists to remove copy/paste decisions.

## Put The Script Where Operators Look

If the repository already has a `scripts/` directory, put the generator there:

```bash
scripts/create-terraform-directory.sh environments/site-a/example
```

That keeps scaffolding with the rest of the operational helpers, such as preflight checks and inventory lookups. Document both common invocation styles:

```bash
# From repository root
scripts/create-terraform-directory.sh environments/site-a/example

# From an environment parent directory
../../scripts/create-terraform-directory.sh example
```

The script should refuse to overwrite an existing directory unless an explicit force flag exists. Accidental regeneration over an active Terraform root is worse than a failed command.

## Keep Real Values Out Of Git

A generated `terraform.tfvars` file is useful because it tells the operator what to populate, but it can become a secret or environment-specific data file quickly.

Use one of these patterns deliberately:

```text
terraform.tfvars.example  # committed sample values
terraform.tfvars          # ignored real values
*.auto.tfvars             # ignored or tightly controlled if environment-specific
```

If the repository intentionally creates a blank `terraform.tfvars`, make sure `.gitignore` policy is clear and consistent. Do not rely on memory to keep credentials, vCenter endpoints, or private addressing out of commits.

Related: [Terraform Variable File Hygiene](/field-notes/terraform-variable-file-hygiene/) covers the broader input-file ownership model.

## Smoke-Test The Generated Root

The generator is infrastructure code. Test it before publishing:

```bash
bash -n scripts/create-terraform-directory.sh

scripts/create-terraform-directory.sh environments/site-a/.scaffold-test
terraform fmt -check -recursive environments/site-a/.scaffold-test
rm -r environments/site-a/.scaffold-test
```

If the generated files include module references, also run a lightweight init in a disposable path when provider access allows it:

```bash
terraform -chdir=environments/site-a/.scaffold-test init -backend=false
```

Do not skip the smoke test. A broken generator spreads the same mistake to every future root.

## Update The README In The Same Change

Scaffolding scripts often expose stale documentation. If the active repository layout is now:

```text
environments/
modules/
templates/
scripts/
archive/
```

then the README should not still describe legacy paths such as old Packer or Terraform directories. Update the sections operators actually use:

- repository structure.
- common requirements.
- quick start.
- helper script catalog.
- preflight and guardrail workflow.

Documentation drift is not cosmetic. If the quick start points at a deleted path, operators will copy an old root or bypass the guardrails.

## Keep Branches Clean

Infrastructure repos often have unrelated local plans, generated JSON, or environment edits in the worktree. Stage only the scaffolding change:

```bash
git add README.md scripts/README.md scripts/create-terraform-directory.sh
git diff --cached --stat
git diff --cached
```

If the branch requires ticket-prefixed commit messages, fix that before review. Rewriting a feature branch can be acceptable, but use `--force-with-lease` and only after confirming the branch is yours to rewrite.

## Operating Rule

New Terraform roots should be generated, not copied from memory.

The generator, README, and smoke test together form the contract: every new environment starts with the same module shape, the same guardrail workflow, and the same warning about where real values belong.
