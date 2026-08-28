+++
title = 'vSphere CSI VolumeSnapshotClass Validation'
date = 2026-08-28T00:00:00-05:00
draft = false
description = 'Field note for enabling and validating Kubernetes VolumeSnapshotClass support for vSphere CSI, including snapshot creation, readyToUse checks, GitOps ownership, retention, and restore proof.'
tags = ['vsphere', 'kubernetes', 'csi', 'storage', 'snapshots', 'gitops', 'operations']
categories = ['field-notes']
+++

Kubernetes snapshot support has several layers. A healthy vSphere CSI deployment does not automatically mean there is a usable snapshot class.

The missing object is often small:

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: vsphere-csi-snapshot-class
driver: csi.vsphere.vmware.com
deletionPolicy: Delete
```

That object tells Kubernetes which CSI driver should handle a `VolumeSnapshot` request.

## Verify The Existing Platform Pieces

Start read-only:

```bash
kubectl api-resources | grep -i snapshot
kubectl get volumesnapshotclass
kubectl get volumesnapshot -A
kubectl get volumesnapshotcontent
kubectl get pods -A | grep -Ei 'snapshot-controller|vsphere-csi'
kubectl get csidriver csi.vsphere.vmware.com -o yaml
```

You want to confirm:

- snapshot CRDs exist.
- the snapshot controller is running.
- vSphere CSI controller pods are healthy.
- vSphere CSI node pods are healthy.
- the `CSIDriver` exists as `csi.vsphere.vmware.com`.
- a `VolumeSnapshotClass` exists for that driver, or you have confirmed it is missing.

If the snapshot APIs exist and vSphere CSI is healthy, but `kubectl get volumesnapshotclass` returns none, the snapshot primitive is present but not exposed through a class.

## Add The Snapshot Class Declaratively

For a manual proof, apply the class:

```bash
kubectl apply -f - <<'EOF'
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: vsphere-csi-snapshot-class
driver: csi.vsphere.vmware.com
deletionPolicy: Delete
EOF
```

Then verify:

```bash
kubectl get volumesnapshotclass
```

Expected:

```text
NAME                         DRIVER                   DELETIONPOLICY
vsphere-csi-snapshot-class   csi.vsphere.vmware.com   Delete
```

For production, commit the `VolumeSnapshotClass` to the Git or ArgoCD path that owns the vSphere CSI deployment. Do not leave a cluster-scoped storage object as a mystery manual change.

## Prove The PVC Uses vSphere CSI

Before snapshotting anything, prove the source PVC is backed by the vSphere driver:

```bash
kubectl get pvc <pvc-name> -n <namespace> \
  -o custom-columns='PVC:.metadata.name,SC:.spec.storageClassName,PV:.spec.volumeName'

PV=$(kubectl get pvc <pvc-name> -n <namespace> \
  -o jsonpath='{.spec.volumeName}')

kubectl get pv "$PV" \
  -o custom-columns='PV:.metadata.name,SC:.spec.storageClassName,DRIVER:.spec.csi.driver,HANDLE:.spec.csi.volumeHandle'
```

The authoritative field is:

```text
DRIVER: csi.vsphere.vmware.com
```

The StorageClass name is useful, but the PV CSI driver proves which backend owns the volume.

## Create And Verify A Test Snapshot

Use a disposable PVC for the first test. Then create a snapshot:

```bash
kubectl apply -f - <<'EOF'
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: vsphere-snapshot-test
  namespace: default
spec:
  volumeSnapshotClassName: vsphere-csi-snapshot-class
  source:
    persistentVolumeClaimName: vsphere-snapshot-test-pvc
EOF
```

Watch readiness:

```bash
kubectl get volumesnapshot vsphere-snapshot-test -n default -w
kubectl describe volumesnapshot vsphere-snapshot-test -n default
```

Success condition:

```text
READYTOUSE true
```

Then inspect the backing content:

```bash
kubectl get volumesnapshotcontent
kubectl get volumesnapshotcontent <content-name> -o yaml
```

Useful proof fields:

```yaml
spec:
  driver: csi.vsphere.vmware.com
  volumeSnapshotClassName: vsphere-csi-snapshot-class
status:
  readyToUse: true
  restoreSize: 1073741824
  snapshotHandle: <vsphere-snapshot-handle>
```

That proves the chain:

```text
PVC -> PV -> csi.vsphere.vmware.com -> VolumeSnapshot -> VolumeSnapshotContent -> readyToUse
```

## Deletion Policy And PVC Deletion

`deletionPolicy: Delete` controls what happens when the `VolumeSnapshot` is deleted. It does not mean Kubernetes automatically creates a snapshot when a PVC is deleted.

The safe answer to an application team is:

```text
Deleting a PVC does not automatically create or preserve a snapshot.
Snapshots must exist before PVC deletion if recovery from snapshot is expected.
```

If the sequence is:

```text
create VolumeSnapshot -> readyToUse true -> delete source PVC
```

the snapshot can remain and can be used to provision a replacement PVC.

If the sequence is only:

```text
delete PVC -> no pre-existing snapshot
```

there is no CSI snapshot recovery point. If the StorageClass reclaim policy is `Delete`, the backing vSphere volume may also be removed.

## Restore Proof

Snapshot creation and restore are separate capabilities. Prove restore with a new PVC:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vsphere-snapshot-restore-test
  namespace: default
spec:
  storageClassName: vsphere-csi-sc
  dataSource:
    name: vsphere-snapshot-test
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

Then:

```bash
kubectl apply -f restore-pvc.yaml
kubectl get pvc vsphere-snapshot-restore-test -n default -w
```

The requested restore size must be at least as large as the snapshot restore size.

The strongest test is practical:

```text
write recognizable file -> snapshot PVC -> delete original PVC -> restore new PVC -> mount -> prove file exists
```

## Lifecycle

Kubernetes does not schedule or expire `VolumeSnapshot` objects by itself.

For vSphere environments with a small snapshot limit per volume, a simple policy may be enough:

```text
create snapshot on cadence
retain newest three per PVC
delete older snapshots
```

Because the class uses `deletionPolicy: Delete`, deleting old `VolumeSnapshot` objects should also clean up the backing vSphere snapshots.

The operating rule: `VolumeSnapshotClass` enables the primitive; GitOps ownership, retention, and restore testing make it operational.
