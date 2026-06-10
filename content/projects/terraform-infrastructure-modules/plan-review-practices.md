+++
title = 'Terraform Plan Review Practices'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial Terraform plan review practices for safer infrastructure changes, state handling, and automation gates.'
tags = ['terraform', 'review', 'infrastructure', 'state']
categories = ['projects']
+++

Terraform plan review is where infrastructure intent becomes operational risk.

A good review does not ask only whether the syntax is valid. It asks whether the planned changes match the expected blast radius.

## Review Inputs

Every plan review should include:

- changed files.
- selected workspace or root module.
- variable files used.
- provider versions.
- plan output.
- expected changes.
- rollback or recovery notes.

Do not review a plan if the command that generated it is unclear.

## State Safety

Terraform state maps configuration addresses to real infrastructure. Treat state as production data.

Expectations:

- use remote state with locking for shared work.
- do not store state in Git.
- do not manually edit state files.
- use `terraform state` commands or moved blocks for refactors.
- back up state before risky migrations.

## Plan Signals

Review carefully when the plan includes:

- resource replacement.
- deletion of stateful resources.
- changes to network paths.
- changes to IAM or secrets.
- provider default changes.
- drift corrections the operator did not expect.

## Automation Gates

Useful gates:

```bash
terraform fmt -check
terraform init -backend=false
terraform validate
terraform plan -out=tfplan
terraform show -json tfplan
```

Policy checks can help, but human review is still needed for ownership, timing, and operational risk.

## Acceptance Criteria

- The reviewer can explain every create, update, delete, and replacement.
- State movement is explicit.
- Secrets are not exposed in plan artifacts.
- The apply target and variable inputs are known.
- Rollback or recovery is realistic.

## References

- Terraform documentation: State.
- Terraform documentation: State Locking.
- Terraform documentation: Plan and Apply.
