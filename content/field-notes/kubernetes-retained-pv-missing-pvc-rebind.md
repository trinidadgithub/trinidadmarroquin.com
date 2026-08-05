+++
title = 'Kubernetes Retained PV Missing PVC Rebind'
date = 2026-08-05T00:00:00-05:00
draft = false
description = 'Field note for recovering a workload that references a missing PVC when a retained PV still exists and can be rebound explicitly.'
tags = ['kubernetes', 'storage', 'persistent-volumes', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

A pod stuck in `Pending` because a PVC does not exist is not always a provisioning problem. Sometimes the data still exists in a retained PV and only the claim object is missing.

The safe recovery is to prove the PV is the intended backing store, then recreate the PVC with an explicit `volumeName` so it binds to that retained PV instead of provisioning something new.

## Confirm The Symptom

Start with the pod event:

```bash
kubectl -n <namespace> describe pod <pod-name>
kubectl -n <namespace> get events --sort-by=.lastTimestamp
```

The key signal is:

```text
persistentvolumeclaim "<pvc-name>" not found
```

Then inspect the workload volume reference:

```bash
kubectl -n <namespace> get deploy <deployment-name> -o yaml \
  | yq '.spec.template.spec.volumes'
```

Confirm the workload still references the missing claim name.

## Find The Retained PV

List available PVs:

```bash
kubectl get pv -o wide
```

Inspect the candidate retained PV:

```bash
kubectl get pv <pv-name> -o yaml
```

Confirm:

- `status.phase` is `Available`.
- `persistentVolumeReclaimPolicy` is `Retain`.
- capacity matches the workload expectation.
- access mode matches the workload expectation.
- storage class matches the original claim.
- labels, path, CSI handle, or other metadata identify it as the intended PV.

Do not bind a random available PV just because the size matches.

## Recreate The Claim Explicitly

Create the PVC with `spec.volumeName` set to the retained PV:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
  namespace: app-namespace
  labels:
    app: app-api
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: standard
  volumeMode: Filesystem
  volumeName: app-retained-pv
```

Apply it:

```bash
kubectl apply -f pvc-rebind.yaml
```

Then verify binding:

```bash
kubectl -n app-namespace get pvc app-data -o wide
kubectl get pv app-retained-pv -o wide
```

Expected:

```text
PVC: Bound
PV:  Bound
```

## Verify The Workload

Watch the pod leave `Pending` or `ContainerCreating`:

```bash
kubectl -n app-namespace get pod -o wide
kubectl -n app-namespace rollout status deploy/app-api --timeout=180s
kubectl -n app-namespace describe pod <pod-name>
```

If the pod schedules but does not become ready, continue with mount, permissions, and application logs. The PVC rebind only fixes the missing-claim condition.

## GitOps Follow-Up

If the workload is GitOps-managed, recreate the PVC in the source of truth or restore the missing manifest. A live PVC fix that is not represented in Git can disappear during a future prune or namespace rebuild.

Also check why the PVC disappeared while the PV remained. Common causes include manual deletion, prune behavior, a Helm chart split, or a previous migration that retained the PV intentionally but did not preserve the claim.

## Operating Rule

A retained PV is recoverable evidence, not automatic permission to bind it.

Rebind only after confirming identity, capacity, access mode, storage class, and workload ownership. Then put the claim back into the declared state so the recovery survives reconciliation.
