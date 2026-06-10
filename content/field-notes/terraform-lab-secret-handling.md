+++
title = 'Secret Handling In Terraform Managed Labs'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for separating acceptable local lab shortcuts from production secret handling when Terraform manages Docker, Grafana, Concourse, or Vault-backed examples.'
tags = ['terraform', 'vault', 'secrets', 'cicd', 'observability']
categories = ['field-notes']
+++

Local infrastructure labs often start with hardcoded passwords, localhost endpoints, and convenience tokens. That is normal for learning, but dangerous when the lab pattern becomes a production pattern without review.

The useful distinction is not "lab bad, production good." The useful distinction is knowing which shortcuts are temporary and what must change before the pattern is reused.

## Common Lab Shortcuts

Terraform-managed Docker labs often include:

- Grafana admin credentials in container environment variables.
- Concourse local users such as `admin:admin`.
- Vault dev server tokens in shell environment files.
- database passwords pulled into Terraform state.
- generated private keys written to local files.
- privileged containers for CI workers or system exporters.
- localhost endpoints that assume a single operator workstation.

Each shortcut may be acceptable in a disposable lab. None should cross into shared infrastructure by accident.

## Main Risk

Terraform state can retain sensitive values even when the original source is Vault or an environment variable.

If Terraform reads a secret and uses it in a resource argument, assume the value may be present in state unless the provider and resource explicitly avoid storing it.

Check state handling before treating the workflow as safe:

```bash
terraform state list
terraform state show <resource-address>
```

Do not paste state output into tickets, chat, or public examples without reviewing it first.

## Better Lab Pattern

For local examples, prefer obvious placeholders:

```bash
export TF_VAR_grafana_admin_password='change-me-for-local-lab'
export TF_VAR_vault_addr='http://127.0.0.1:8200'
```

Keep real local values in ignored files:

```gitignore
*.auto.tfvars
terraform.tfvars
.env
*.env
keys/
```

Commit example files only:

```text
terraform.tfvars.example
vault.env.example
grafana.env.example
```

The example should teach the required inputs without carrying working secrets.

## Vault Integration Checks

When Vault is part of the lab, verify:

- the workflow does not require committing a Vault token.
- the token is short-lived or clearly marked as a dev token.
- secret paths are documented.
- policies are narrower than full administrative access.
- generated files containing keys are ignored.
- cleanup steps revoke or rotate credentials when the lab is done.

For shared environments, prefer identity-based authentication over passing a reusable root-like token into Terraform or a container.

## Container Credential Checks

For Grafana, Concourse, Prometheus, or similar containers, review:

- which ports are exposed to the host.
- whether default credentials are still active.
- whether admin credentials are rotated after first start.
- whether service-account tokens are stored in state.
- whether the container needs privileged mode.
- whether mounted host paths expose Docker, system files, or secrets.

A monitoring lab that mounts `/var/run/docker.sock` or `/var/lib/docker` may be useful, but it should be treated as privileged access to the host.

## Promotion Checklist

Before reusing a local lab pattern in a team environment:

- replace hardcoded credentials with an approved secret source.
- review Terraform state for sensitive values.
- add `.gitignore` rules for state, plans, keys, and env files.
- remove default admin users or force password rotation.
- restrict exposed ports and network reachability.
- document cleanup and credential revocation.
- separate lab names from production names.

## Operating Rule

A lab should make shortcuts visible.

If a secret is hardcoded for teaching, name it like a placeholder. If a key is generated locally, ignore it. If Terraform touches the value, assume state must be protected.

The goal is to preserve the speed of a lab without accidentally teaching unsafe production defaults.
