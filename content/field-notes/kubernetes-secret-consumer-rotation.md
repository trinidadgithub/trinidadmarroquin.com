+++
title = 'Kubernetes Secret Consumer Rotation'
date = 2026-08-30T00:00:00-05:00
draft = false
description = 'Field note for rotating Kubernetes Secrets safely by proving consumer reload behavior, rollout timing, old credential revocation, and evidence without exposing secret values.'
tags = ['secrets', 'kubernetes', 'rotation', 'operations', 'security']
categories = ['field-notes']
+++

A Kubernetes `Secret` update is not the same thing as a completed rotation.

The object can change in etcd while the application still uses an old environment variable, cached file, open connection, or credential loaded at process start. Rotation is complete only when the consumer uses the replacement and the old credential is revoked or made irrelevant.

## Identify The Consumer Path

Start by finding how the workload consumes the secret:

```bash
kubectl -n app-ns get deploy,statefulset,daemonset -o yaml | grep -n 'secretKeyRef\|secretName'
kubectl -n app-ns get pod <pod> -o yaml | grep -n 'secretKeyRef\|secretName'
kubectl -n app-ns describe secret <secret-name>
```

Classify the path:

- environment variable from `secretKeyRef`.
- volume-mounted Secret.
- projected volume.
- CSI secret mount.
- generated Secret from an external controller.
- application direct call to the secret manager.

The reload behavior depends on this path.

## Rotation Plan

Use a small plan before changing values:

```text
secret:
namespace:
consumer workload:
delivery path:
reload behavior:
old credential revocation step:
verification command:
rollback decision:
```

Do not store the raw secret value in the plan, ticket, shell history, or evidence bundle.

## Reload Behavior

Environment variables usually require a pod restart or rollout. Volume-mounted Secrets update on disk eventually, but the application may not reread the file.

Check:

- whether the app watches the mounted file.
- whether a sidecar reloads the app.
- whether a Deployment rollout is required.
- whether a StatefulSet needs ordered restart.
- whether connection pools hold old credentials.
- whether old pods are still running with old values.

For a Deployment:

```bash
kubectl -n app-ns rollout restart deployment/app
kubectl -n app-ns rollout status deployment/app --timeout=180s
kubectl -n app-ns get pods -o wide
```

## Verify The Consumer

Object updates are weak evidence. Verify at the application boundary:

- application health check passes.
- dependency login succeeds with the new credential.
- old credential fails after revocation.
- error logs do not show authentication retries.
- metrics show normal request and dependency behavior.
- pods using the old ReplicaSet are gone or intentionally retained.

Do not print or decode secret values as routine evidence. Use timestamps, resource versions, rollout IDs, audit events, and application checks instead.

## Failure Model

The common failure is treating the Kubernetes object as the whole rotation:

```text
Secret updated -> Deployment not restarted
-> application keeps old env var -> upstream revokes old credential
-> app outage begins after a seemingly successful change
```

The operating rule: rotate the value, roll or reload the consumer, verify the new credential is used, then revoke the old credential.
