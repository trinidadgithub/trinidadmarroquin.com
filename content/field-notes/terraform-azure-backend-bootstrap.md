+++
title = 'Terraform Azure Backend Bootstrap'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for bootstrapping an Azure Storage backend for Terraform state without confusing the first apply with the later remote backend migration.'
tags = ['terraform', 'azure', 'state', 'cloud']
categories = ['field-notes']
+++

Remote state has a chicken-and-egg problem: Terraform needs somewhere to store state, but the storage account and container may also be managed by Terraform.

The clean approach is to treat backend bootstrapping as a short, explicit phase. Create the state storage resources first, migrate state intentionally, then use the remote backend for the rest of the infrastructure.

## Target Shape

For Azure Blob Storage, the backend needs:

- a resource group.
- a storage account.
- a private blob container.
- a stable state key per root module or environment.

Example backend shape:

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "platform-state-rg"
    storage_account_name = "platformstateacct"
    container_name       = "terraform-state"
    key                  = "prod/network/terraform.tfstate"
  }
}
```

The exact names should match the environment and ownership model. Avoid reusing one vague state key for unrelated infrastructure.

## Bootstrap Sequence

Start with the backend block commented out or absent:

```bash
terraform init
terraform validate
terraform plan
terraform apply
```

After the resource group, storage account, and container exist, add the backend block and migrate:

```bash
terraform init -migrate-state
```

Verify that Terraform now reads and writes remote state:

```bash
terraform state list
terraform plan
```

The plan should be clean unless other intentional changes exist.

## State Key Rules

Use state keys that express blast radius:

```text
prod/network/terraform.tfstate
prod/aks/terraform.tfstate
nonprod/network/terraform.tfstate
shared/observability/terraform.tfstate
```

Avoid:

```text
terraform.tfstate
main.tfstate
test.tfstate
```

Those names hide ownership and make recovery harder when multiple roots exist.

## Access And Safety Checks

Before using the backend for shared work, confirm:

- the container is private.
- only the automation and operators that need state access can read it.
- state access is logged through Azure activity logs or storage diagnostics where required.
- the storage account is protected by the expected network and identity controls.
- state files are excluded from Git.

At minimum, keep this out of source control:

```gitignore
**/*.tfstate
**/*.tfstate.*
**/*.tfplan
```

## Recovery Notes

If backend migration fails, do not delete local state casually. First identify where the current authoritative state lives:

```bash
terraform state list
```

Then inspect the backend configuration and rerun initialization only after the storage account, container, and key are correct:

```bash
terraform init -reconfigure
```

Use `-reconfigure` when changing backend settings without migrating existing state. Use `-migrate-state` when intentionally moving state from one backend to another.

## Operating Rule

Backend bootstrapping is infrastructure work, not a throwaway setup step.

Write down:

- who owns the state storage.
- which root module owns each key.
- how access is granted.
- how state is recovered.
- how old local state files are removed after migration.

The goal is not just remote state. The goal is state that an operator can find, protect, and recover under pressure.
