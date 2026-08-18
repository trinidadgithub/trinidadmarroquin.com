+++
title = 'Kubernetes ContainerCreating: Split Storage Failures From Missing Manifests'
date = 2026-08-18T00:00:00-05:00
draft = false
description = 'Field note for separating Kubernetes pods stuck in ContainerCreating because of CSI backend storage state from pods blocked by missing ConfigMaps or Secrets.'
tags = ['kubernetes', 'storage', 'csi', 'iscsi', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

Two pods can sit in `ContainerCreating` for days and need completely different fixes.

In one production triage, the first pod was blocked by a CSI volume that Kubernetes could request but the storage array would not present. The second pod was blocked by missing `ConfigMap` and `Secret` objects referenced by the pod spec. The visible symptom was the same. The evidence path was not.

That distinction matters because `ContainerCreating` is not a root cause. It is the kubelet saying it cannot finish preparing the container sandbox, volumes, or configuration.

## Start With Events, Not Assumptions

The fastest split is usually in `kubectl describe pod` and recent namespace events:

```bash
kubectl -n app-namespace describe pod app-cache-0
kubectl -n app-namespace get events --sort-by=.lastTimestamp
```

Storage backend failure often appears as a CSI staging or mount-device error:

```text
MountVolume.MountDevice failed for volume "pvc-<uid>":
rpc error: code = Internal desc = Failed to stage volume <array-volume-id>
device not found with serial <serial> or target
```

Missing manifest dependencies look different:

```text
MountVolume.SetUp failed for volume "app-config":
configmap "app-config" not found

MountVolume.SetUp failed for volume "ldap-config":
secret "app-ldap-config" not found
```

Do not treat both as storage incidents just because both pods are in `ContainerCreating`.

## Follow The Storage Failure Across Layers

For a CSI-backed volume, follow the claim to the backend handle:

```bash
kubectl -n app-namespace get pvc app-data -o wide
kubectl -n app-namespace get pvc app-data -o jsonpath='{.spec.volumeName}{"\n"}'
kubectl get pv pvc-<uid> -o yaml
```

Confirm the provisioner and volume handle:

```text
spec.csi.driver:        csi.example.com
spec.csi.volumeHandle: <array-volume-id>
```

Then check the node-side CSI plugin logs for device discovery evidence:

```bash
kubectl -n storage-system logs csi-node-abcde -c csi-driver --since=30m
```

Useful signals include:

```text
Failed to stage volume <array-volume-id>
unable to create device for volume <array-volume-id>
device not found with serial <serial> or target
```

Those messages usually mean the node plugin expected the LUN or disk to appear and could not map it. At that point, Kubernetes is only one witness. You still need the storage-controller and array view.

## Check The Storage Controller And Array State

For array-backed CSI drivers, the controller or vendor-side provider logs can prove whether Kubernetes successfully requested the publish operation:

```bash
kubectl -n storage-system logs storage-provider-abcde --since=2h
```

Look for:

```text
volume published to worker-1 initiator group
LUN assigned
initiator IQN matched
volume set offline
```

Then query the storage array, using your normal approved access path, and compare a failing volume with a known-good volume from the same class:

```text
failing volume:  state=offline  online=false  sessions=[]
working volume:  state=online   online=true   sessions=2
```

That comparison is the key. If the ACL or export is present but the array volume is offline, the node-side CSI error is downstream. The kubelet can retry forever, but the device will not appear until the backend presents it.

This is also the point where escalation should become precise. Do not ask the storage team to "check storage" in the abstract. Provide the PVC name, PV name, CSI volume handle, affected node, storage class, and the exact CSI error. That gives the storage administrator enough evidence to verify the backend object directly.

In the incident behind this note, that escalation confirmed the array volume was `offline` with an operator/user offline reason. That array-side state wedged the Kubernetes storage lifecycle: Kubernetes had a valid claim and CSI had a backend volume handle, but the LUN was never presented to the node. Once the storage administrator manually set the backend volume online, the lifecycle unblocked. Kubernetes completed the pending delete/recreate path, provisioned a fresh volume, and the workload moved out of `ContainerCreating`.

The important follow-up remained open: why the storage volume went offline in the first place. Treat `offline_reason=user` as a separate audit trail, not as a resolved Kubernetes root cause.

## Watch For PVC Protection Deadlocks

A common failed remediation is deleting the PVC while the stuck pod still references it.

Kubernetes protects in-use claims with `kubernetes.io/pvc-protection`. That can create a deadlock shape:

```text
pod references PVC
PVC deletion requested
PVC remains Terminating because pod still references it
pod remains ContainerCreating because volume cannot stage
```

Before forcing anything, decide the intended data outcome.

If the data matters, restore the backend volume first and let kubelet retry staging. If the workload is being reset or decommissioned, scale down or remove the workload so the PVC can release cleanly.

The dangerous middle path is letting a StatefulSet reprovision a fresh PVC without noticing that the old backend volume still contains the previous data.

When a storage administrator changes backend state during the incident, watch Kubernetes immediately afterward. The array fix may not attach the old data volume if Kubernetes already has a deletion or replacement workflow in progress. It may simply unblock the lifecycle manager enough to remove the old PVC/PV and create a new one.

## Prove Whether Recovery Used Old Or New Storage

After the pod starts, verify which volume it is using:

```bash
kubectl -n app-namespace get pod app-cache-0 -o wide
kubectl -n app-namespace get pvc app-data -o wide
kubectl get pv <new-or-old-pv> -o jsonpath='{.spec.csi.volumeHandle}{"\n"}'
```

Then confirm the array state:

```text
new volume:  online=true  sessions>0  usage=0 bytes
old volume:  offline     sessions=0   preserved by reclaim policy or array policy
```

That tells you whether the application recovered its original data or simply started on an empty replacement volume. Both can be acceptable, but they are not the same outcome.

## Split Missing Config From Storage

For the second `ContainerCreating` pod, the events may show missing API objects instead of storage failure:

```bash
kubectl -n app-namespace describe pod app-dashboard-abcde
kubectl -n app-namespace get cm,secret
```

Inspect the workload references:

```bash
kubectl -n app-namespace get deploy app-dashboard -o yaml
```

Review the blocking references:

```text
volume configMap name: app-dashboard-config      optional: false
volume secret name:    app-dashboard-ldap        optional: false
env secret name:       app-dashboard-credentials optional: false
```

Search whether those objects exist anywhere:

```bash
kubectl get configmap -A | grep app-dashboard
kubectl get secret -A | grep app-dashboard
```

If the objects are absent and the Deployment has no owner references, Helm metadata, or GitOps annotations, the fix is not a storage action. Restore the missing manifests from the source of truth, or remove the obsolete workload.

Optional references are different. An optional plugin ConfigMap may be absent without blocking pod startup. Non-optional volume and environment references block container creation.

## Evidence Checklist

For a storage-backed `ContainerCreating` incident, keep this evidence:

```text
pod event showing CSI stage/mount failure
PVC and PV names
CSI driver and volume handle
node-side CSI plugin error
storage provider publish/export log
array state: online/offline, ACL/export, sessions
storage-admin confirmation of backend health and state change
whether the old volume still exists and contains data
whether Kubernetes reused the original volume or provisioned a replacement
```

For a missing-manifest `ContainerCreating` incident, keep this evidence:

```text
pod event showing ConfigMap or Secret not found
workload volume and env references
optional versus non-optional reference status
cluster-wide search for the missing object names
owner references, Helm metadata, or GitOps annotations
decision: restore source manifests or remove obsolete workload
```

## Operating Rule

`ContainerCreating` is a symptom bucket. Split it before fixing it.

If the event says the CSI driver cannot find a device, prove the backend volume is online and presented to the node. If the event says a `ConfigMap` or `Secret` is missing, restore the declared Kubernetes objects. The wrong fix can either lose data by reprovisioning empty storage or waste time debugging storage for a manifest problem.
