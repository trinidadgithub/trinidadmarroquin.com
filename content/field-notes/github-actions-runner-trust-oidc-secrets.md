+++
title = 'GitHub Actions Runner Trust OIDC And Secrets'
date = 2026-08-26T00:00:00-05:00
draft = false
description = 'Field note for handling GitHub Actions runner trust, permissions, OIDC federation, repository secrets, environment protection, and self-hosted runner risk.'
tags = ['github-actions', 'cicd', 'secrets', 'oidc', 'security', 'operations']
categories = ['field-notes']
+++

GitHub Actions credentials are production access if the workflow can mutate production.

The safe pattern is short-lived, scoped access tied to the repository, branch, environment, and workflow that needs it. Long-lived cloud keys in repository secrets should be the exception, not the default.

## Start With Permissions

Set workflow permissions explicitly:

```yaml
permissions:
  contents: read
```

Then add only what a job needs:

```yaml
permissions:
  contents: read
  id-token: write
```

`id-token: write` enables OIDC token issuance. It does not by itself grant cloud access; the cloud trust policy still decides what the token can assume.

## OIDC Trust Checks

For cloud federation, review the trust boundary:

- repository owner and name.
- branch, tag, or environment condition.
- workflow file path, if used.
- audience value.
- allowed role or service account.
- session duration.
- audit trail for assumed identity.

Do not trust every workflow in a repo to assume the same production role. Separate validation, non-production, and production identities.

## Repository And Environment Secrets

Prefer environment-scoped secrets for deployment credentials. Protect production environments with reviewers and branch restrictions.

Review:

- which repositories can access an organization secret.
- whether forked PRs can reach sensitive jobs.
- whether secrets are printed through debug output.
- whether secrets are passed to third-party actions.
- whether rotated credentials break old workflow runs.

If a secret can deploy production, its usage should be visible in workflow review and environment protection rules.

## Self-Hosted Runner Risk

Self-hosted runners change the threat model.

Check:

- runner group scope.
- which repositories can schedule work there.
- network reachability from the runner.
- persistence between jobs.
- cleanup behavior.
- access to Docker socket, cloud metadata, kubeconfig, or internal networks.

A self-hosted runner reachable from pull requests is not just CI capacity. It is an execution path inside your environment.

## Failure Model

The dangerous failure is broad trust:

```text
repo secret holds production key
-> workflow condition is widened
-> PR or branch job reaches deploy step
-> audit shows GitHub Actions but not the intended change boundary
```

The operating rule: scope credentials to the narrowest workflow identity that can do the work, and make privileged jobs explain why they were allowed to run.
