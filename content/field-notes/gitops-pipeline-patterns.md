+++
title = 'GitOps Pipeline Patterns For Platform Teams'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for GitOps pipeline patterns in infrastructure teams: change pipelines, fleet rollouts, tenant onboarding, and the operating model that keeps Git as the single source of truth.'
tags = ['gitops', 'cicd', 'concourse', 'infrastructure', 'platform']
categories = ['field-notes']
+++

## Make Git The Only Entry Point

If a change can be made without opening a pull request, it will eventually be made without a pull request. The rule is simple: no PR, no change.

This applies to:

- Terraform and Ansible runs.
- Image template version bumps.
- Pipeline configuration changes.
- DNS and load balancer records.
- Monitoring and alerting rules.

## Pipeline Shapes

### Change Pipeline

```text
PR → lint → validate → plan → plan review → apply non-prod → apply prod → verify
```

Plan output must be retained as an artifact. Apply stages must be serialized per state backend.

### Fleet Rollout Pipeline

```text
trigger → per-site jobs (run in parallel or serial groups) → per-site verify → summary
```

Each site runs independently. A failure in one site does not block others. Retry individual sites without rerunning the entire fleet.

### Tenant Onboarding Pipeline

```text
tenant PR → validate manifest → generate resources → apply → notify
```

The tenant provides a declarative manifest. The pipeline translates it into platform resources. No platform engineer touches a terminal for standard onboarding.

## Production Rules

- Pipelines hold the only credentials that can apply changes. No human runs `terraform apply` or `ansible-playbook` against production.
- Production apply jobs require an explicit approval gate.
- Rollback is `git revert` + pipeline run. Practice it.
- If the Git repo is lost, the ability to manage infrastructure is lost. Back up the repo before the Terraform backend.

## Verification

After every apply, verify:

```text
Pipeline job: verify
- Does the target match the declared state?
- Are checksums or version tags consistent?
- Did the apply complete without partial failure?
- Does the verification itself produce an auditable result?
```

If verification fails, the pipeline stops. Do not proceed to the next environment or site until verification passes.

## Common Mistakes

- **Allowing SSH access for debugging.** Debugging sessions turn into ad-hoc changes. Use pipeline debug jobs or ephemeral shells that leave no state.
- **Sharing credentials across environments.** The pipeline should assume different identities per environment. If the dev credential is compromised, prod should not be reachable.
- **Bypassing plan review for urgent changes.** Urgency is when processes matter most. Use expedited review, not no review.
- **Treating rollback as a revert only.** Some infrastructure changes (database migrations, storage expansions, certificate rotations) cannot be cleanly reverted. Rollback planning must happen before apply.
