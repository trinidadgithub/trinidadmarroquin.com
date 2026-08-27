+++
title = 'GitOps Drift And Prune Safety Checks'
date = 2026-08-26T00:00:00-05:00
draft = false
description = 'Field note for handling GitOps drift and prune behavior safely across ArgoCD, Flux, Helm, CRDs, stateful workloads, and incident-driven live changes.'
tags = ['gitops-operators', 'argocd', 'flux', 'gitops', 'kubernetes', 'operations']
categories = ['field-notes']
+++

Drift is a signal. Prune is a deletion engine. Treat them differently.

A GitOps controller showing drift tells you declared state and live state differ. It does not automatically prove which side is correct.

## Classify Drift First

Before syncing, classify the difference:

- expected controller mutation.
- admission webhook defaulting.
- Helm-rendered value change.
- manual incident fix.
- secret or certificate rotation.
- generated name or checksum annotation.
- unmanaged object created outside Git.
- stale manifest that should be removed.

The response depends on the class. Syncing everything is fast, but it can erase the clue that explains the incident.

## Prune Risk Review

Before enabling or triggering prune, ask:

- Could this delete a PVC, Secret, CRD, namespace, or cluster-scoped dependency?
- Is the object still owned by another controller?
- Was the manifest intentionally moved between apps or paths?
- Is finalizer behavior understood?
- Will deletion cascade into child resources?
- Is restore possible if this prune is wrong?

Prune is useful for hygiene. It is not a substitute for understanding object ownership.

## Stateful Objects

Be more conservative with stateful resources:

- PVCs.
- database custom resources.
- object storage buckets declared through controllers.
- secrets that hold encryption, bootstrap, or replication credentials.
- CRDs whose deletion removes custom resources.

For stateful workloads, prefer an explicit migration or retirement PR over relying on a generic prune sweep.

## Incident Pattern

A safe incident flow looks like this:

```text
detect drift -> identify owner -> decide live fix or Git fix
-> apply smallest safe action -> capture controller status
-> update Git if live state changed -> reconcile -> verify health
```

The important step is writing the incident change back to Git. Without it, the next reconciliation cycle may reintroduce the incident.

## Evidence To Keep

Capture:

- controller name and namespace.
- application, Kustomization, or HelmRelease name.
- live object diff.
- Git revision before and after.
- sync or reconciliation result.
- prune decision and excluded objects.
- post-sync health check.

This evidence turns GitOps from "the controller changed it" into a reviewable operating history.

## Failure Model

The dangerous failure is cleanup without ownership review:

```text
repo path is reorganized -> old app still owns previous objects
-> prune deletes shared Secret or PVC -> workload outage starts
```

The operating rule: drift deserves investigation; prune deserves a deletion review.
