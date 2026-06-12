+++
title = 'Terraform Variable File Hygiene'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note for separating Terraform inputs, auto-loaded tfvars, govc environment files, and secrets in infrastructure repositories.'
tags = ['terraform', 'govc', 'secrets', 'operations']
categories = ['field-notes']
+++

Terraform repositories often accumulate `terraform.tfvars`, `*.auto.tfvars`, shell env files, examples, and helper scripts. That works until nobody remembers which file is authoritative.

## Problem

A single environment directory may contain:

```text
terraform.tfvars
vars.auto.tfvars
vars.env
terraform.tfvars.example
vars.auto.tfvars.example
vars.env.example
```

That creates three problems:

- Terraform may load values from multiple files.
- shell helper files look like Terraform configuration.
- secrets may drift into files that should be committed safely.

## How Terraform Loads Values

Terraform automatically loads:

```text
terraform.tfvars
*.auto.tfvars
```

If the same variable appears in both, the result can be confusing during plan review.

`vars.env` is not special to Terraform. It only matters if a person or script sources it.

## Recommended Model

Use a small, explicit model:

```text
variables.tf              # defines inputs
terraform.tfvars.example  # checked-in sample values
terraform.tfvars          # real non-secret values, usually ignored if sensitive
govc.env.example          # checked-in govc helper sample
govc.env                  # real govc helper values, ignored
```

Secrets should come from environment variables, a secret manager, or another approved workflow:

```bash
export TF_VAR_vsphere_user='...'
export TF_VAR_vsphere_password='...'
export TF_VAR_admin_password='...'
```

## Rename Helper Files

If `vars.env` exists only to run `govc`, rename it:

```bash
mv vars.env govc.env
```

That makes the purpose obvious:

```bash
source govc.env
govc about
govc device.ls -vm /DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-02
```

## Classify Existing Values

Inspect what is defined across files:

```bash
grep -h '^[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*=' terraform.tfvars vars.auto.tfvars 2>/dev/null
```

List variables Terraform expects:

```bash
grep '^variable "' variables.tf
```

Then classify each value:

- Terraform input: move to `terraform.tfvars` or the example file.
- Secret: move to `TF_VAR_...`, Vault, or another secret workflow.
- Operator helper value: move to `govc.env` or another clearly named tool file.
- Obsolete value: remove after a clean plan confirms it is not needed.

## Check `.gitignore`

At minimum:

```gitignore
**/.terraform/
**/*.tfstate
**/*.tfstate.*
**/*.tfplan
**/terraform.tfvars
**/govc.env
```

Decide intentionally whether to commit `.terraform.lock.hcl`. Many teams commit it for provider consistency, but avoid unmanaged lock files scattered across old roots unless that is the chosen model.

## Validate After Cleanup

Run from the environment root:

```bash
terraform validate
terraform plan
```

The cleanup is successful when the plan is unchanged except for expected variable hygiene changes.

## Operating Rule

Names should explain ownership:

- `terraform.tfvars` is for Terraform values.
- `govc.env` is for `govc` CLI context.
- `TF_VAR_...` or a secret manager is for sensitive Terraform inputs.

If a file name does not explain who consumes it, it will eventually confuse an operator.
