+++
title = 'Flux Reconciliation And Promotion Evidence'
date = 2026-08-26T00:00:00-05:00
draft = false
description = 'Field note for operating Flux with visible reconciliation state, Kustomization and HelmRelease health, promotion records, source freshness, and rollback evidence.'
tags = ['gitops-operators', 'flux', 'gitops', 'kubernetes', 'helm', 'operations']
categories = ['field-notes']
+++

Flux is strongest when reconciliation evidence is easy to read without guessing which controller owns the change.

The operator task is to connect Git revision, source artifact, rendered manifests, apply result, and workload health into one story.

## Follow The Controller Chain

A Flux deployment often crosses several controllers:

```text
GitRepository or HelmRepository -> Kustomization or HelmRelease -> Kubernetes objects -> workload readiness
```

When a rollout fails, check each link before changing manifests.

Useful commands:

```bash
flux get sources git -A
flux get sources helm -A
flux get kustomizations -A
flux get helmreleases -A
flux logs --all-namespaces --level=error
```

The first failed controller is usually more useful than the loudest workload event.

## Promotion Evidence

For environment promotion, record:

- source repo and path.
- commit SHA or chart version.
- image digest or immutable tag.
- target cluster and namespace.
- Flux resource that reconciled the change.
- reconcile time.
- readiness result.
- rollback commit or version.

Promotion is not just a merge. It is evidence that the target environment reconciled the intended revision.

## Kustomization Checks

For `Kustomization` resources, inspect:

- source revision.
- path and interval.
- dependencies.
- health checks.
- prune setting.
- decryption configuration.
- last applied revision.
- inventory of owned objects.

Dependencies matter. A platform add-on can look broken when its CRDs, secrets, or namespace baseline have not reconciled yet.

## HelmRelease Checks

For `HelmRelease` resources, inspect:

- chart source and version.
- values source.
- install and upgrade remediation settings.
- test settings.
- release history.
- failed hooks.
- drift between desired values and rendered output.

Treat chart upgrades as application changes. The controller can run the upgrade, but the team still owns compatibility and rollback expectations.

## Failure Model

The quiet failure is stale source confidence:

```text
Git has new commit -> Flux source cannot fetch or authenticate
-> Kustomization remains on old artifact -> workload appears stable
-> operators assume the new config is deployed
```

The operating rule: a Flux rollout is complete only when source freshness, reconciliation status, and workload health all point to the intended revision.
