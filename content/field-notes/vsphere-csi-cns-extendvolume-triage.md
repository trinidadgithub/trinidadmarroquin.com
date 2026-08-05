+++
title = 'vSphere CSI CNS ExtendVolume Triage'
date = 2026-08-05T00:00:00-05:00
draft = false
description = 'Field note for triaging vSphere CSI CNS ExtendVolume task messages by mapping CNS volume IDs to PVs and PVCs, separating resize state from attachment failures, and avoiding destructive rollback.'
tags = ['kubernetes', 'vsphere', 'vmware', 'csi', 'storage', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

A vSphere CSI controller log that says a CNS `ExtendVolume` task is pending does not immediately tell you whether the workload is blocked by resize, attachment, mount, or a stale backend task. The first job is to map the CNS volume ID back to Kubernetes state and avoid turning a storage delay into a destructive rollback.

The useful triage order is:

```text
CNS volume ID -> PV -> PVC -> pod -> VolumeAttachment -> CSI controller logs -> vCenter task state
```

## Map The CNS Volume ID

Start by mapping the reported CNS volume ID to the Kubernetes PV and PVC:

```bash
volume_id='<cns-volume-id>'

kubectl get pv -o json \
  | jq -r --arg volume_id "$volume_id" '
      .items[]
      | select(.spec.csi.volumeHandle == $volume_id)
      | [
          .metadata.name,
          .spec.claimRef.namespace,
          .spec.claimRef.name,
          .spec.capacity.storage,
          .status.phase
        ]
      | @tsv'
```

Then inspect the PVC and PV directly:

```bash
kubectl -n <namespace> get pvc <pvc-name> -o yaml
kubectl get pv <pv-name> -o yaml
```

Look for the requested size, current capacity, annotations, conditions, and storage class. A PVC that is already `Bound` at the expected size is a different problem than one stuck with expansion conditions.

## Separate Resize From Attach

Check whether Kubernetes still believes expansion is pending:

```bash
kubectl -n <namespace> describe pvc <pvc-name>
kubectl -n <namespace> get events --sort-by=.lastTimestamp
```

Useful resize signals include:

```text
ExternalExpanding
Resizing
FileSystemResizePending
FileSystemResizeSuccessful
```

Then check VolumeAttachments separately:

```bash
kubectl get volumeattachments -o json \
  | jq -r --arg pv '<pv-name>' '
      .items[]
      | select(.spec.source.persistentVolumeName == $pv)
      | [
          .metadata.name,
          .spec.nodeName,
          .status.attached,
          (.status.attachError.message // "")
        ]
      | @tsv'
```

An attach error such as `DeadlineExceeded` may be the active symptom even when the log line that started the investigation mentions `ExtendVolume`. Do not assume one log phrase is the whole incident.

## Check The Workload Path

Inspect the affected pod and node placement:

```bash
kubectl -n <namespace> get pod <pod-name> -o wide
kubectl -n <namespace> describe pod <pod-name>
kubectl get node <node-name> -o wide
```

This tells you whether the pod is blocked before scheduling, waiting on attach, waiting on mount, or already running after reconciliation caught up.

For vSphere CSI components, verify both controller and node pods:

```bash
kubectl -n vmware-system-csi get pods -o wide
kubectl -n vmware-system-csi logs deploy/vsphere-csi-controller --since=30m --all-containers=false
```

If the CSI controller is intentionally paused during maintenance, record that explicitly. A paused controller can make unrelated storage symptoms look worse than they are.

## Check CSI Operation And Leader State

vSphere CSI also keeps Kubernetes-side operation records. When vCenter is slow or task visibility is inconsistent, these records can explain why CSI keeps retrying old work:

```bash
kubectl -n vmware-system-csi get cnsvolumeoperationrequests.cns.vmware.com

kubectl -n vmware-system-csi get cnsvolumeoperationrequest <operation-name> -o yaml
```

Look for:

```text
firstOperationDetails.taskStatus
latestOperationDetails[].taskStatus
latestOperationDetails[].error
latestOperationDetails[].taskId
volumeID
```

Repeated `TimeOut`, `VSLM task failed`, or an operation that still says `InProgress` after vCenter no longer shows queued/running tasks is a signal to slow down. It may be stale CSI memory, vCenter task history lag, or a backend task that has not reconciled through every layer yet.

Also verify CSI sidecar leadership when attach status stops moving:

```bash
kubectl -n vmware-system-csi get lease
kubectl -n vmware-system-csi get lease external-attacher-leader-csi-vsphere-vmware-com -o yaml
kubectl -n vmware-system-csi get pods -o wide
```

If the external-attacher lease is held by a deleted pod, a live attacher may never update `VolumeAttachment` status. Deleting only the stale lease can be the smallest safe unblock, because a current controller pod should reacquire it:

```bash
kubectl -n vmware-system-csi delete lease external-attacher-leader-csi-vsphere-vmware-com
kubectl -n vmware-system-csi get lease external-attacher-leader-csi-vsphere-vmware-com -o yaml
```

Do this only after confirming the holder pod is gone. Do not delete all leases or restart every CSI component blindly.

## Backend Attached, Kubernetes Still False

A confusing failure mode is when vCenter and the guest show the disk attached, but Kubernetes still reports the `VolumeAttachment` as `attached=false`.

Correlate all three views:

```bash
kubectl get volumeattachment <volumeattachment-name> -o yaml
govc device.info -vm '<vm-path-or-name>'
ssh operator@192.0.2.24 'lsblk; findmnt; sudo dmesg | tail -100'
```

CSI logs may show a shape like:

```text
attachedStatus=false found=true
```

That means the backend can see the disk, but the Kubernetes status path has not reconciled. At that point, patching `VolumeAttachment.status.attached=true` may look tempting. Treat that as a manual status intervention, not a normal fix. It bypasses the CSI controller's failed update path and should require an explicit decision, current evidence that the correct disk is attached to the correct node, and a rollback plan.

When in doubt, wait for vCenter/CNS to settle before patching storage status, deleting operation records, removing finalizers, or detaching disks.

## Use vCenter As Correlation, Not Guesswork

If Kubernetes still shows pending attachment or resize, correlate with vCenter task state. Use read-only commands first:

```bash
govc tasks
govc events -vm '<vm-path-or-name>'
```

Capture whether CNS tasks are queued, running, succeeded, or no longer visible. If the Kubernetes PVC and pod recover while you are waiting, do not keep forcing remediation just because an earlier log line mentioned a pending task.

`govc tasks` can be misleading if you only run the default view. The default output is recent task history; it may not show the active backlog you care about. Query queued and running tasks explicitly:

```bash
govc tasks -json -s queued -s running -n=300 \
  | jq -r '.Tasks[]? | [
      .StartTime,
      .QueueTime,
      .State,
      (.Progress|tostring),
      .DescriptionId,
      (.EntityName // ""),
      .Key
    ] | @tsv'
```

For a suspected worker VM, scope the same query to the VM path:

```bash
vm='/DC-Site-A/vm/K8s-Cluster/cluster-a-worker-2'

govc tasks -json -s queued -s running -n=300 "$vm" \
  | jq -r '.Tasks[]? | [
      .StartTime,
      .QueueTime,
      .State,
      (.Progress|tostring),
      .DescriptionId,
      (.EntityName // ""),
      .Key
    ] | @tsv'
```

A useful backlog summary is count by state for the affected VM:

```bash
govc tasks -json -n=300 \
  | jq -r --arg vm 'cluster-a-worker-2' '
      [.Tasks[]? | select((.EntityName // "") == $vm)]
      | group_by(.State)[]
      | [.[0].State, length]
      | @tsv'
```

Look specifically for task types that can serialize or block storage progress:

```text
com.vmware.cns.tasks.attachvolume
com.vmware.cns.tasks.detachvolume
com.vmware.cns.tasks.extendvolume
com.vmware.cns.tasks.updatevolume
vslm.vcenter.VStorageObjectManager.extendDisk
VirtualMachine.attachDisk
VirtualMachine.detachDisk
Drm.ExecuteVMotionLRO
```

The important distinction is whether CSI is still creating new work or whether vCenter/ESXi is still draining already-submitted work. If CSI is paused and no new controller pods are running, a growing queue probably points at the backend task backlog, not a fresh Kubernetes scheduling decision.

When `govc tasks -s queued -s running` returns no rows but CSI operation CRs still mention an old task as `InProgress`, treat that as a split-brain signal between CSI's remembered operation state and currently visible vCenter task state. Do not delete CSI operation records or patch storage status until the backend state, guest disk state, and Kubernetes object state have been reconciled deliberately.

## Avoid Destructive Rollback

Storage rollback is not the same as rolling back an operational pause.

Safe operational rollback examples:

- remove temporary CSI pause taints.
- restore GitOps sync policy after maintenance.
- restart or unpause CSI controllers when the runbook says to.

Potentially destructive storage rollback examples:

- deleting a replacement PVC.
- removing finalizers.
- detaching disks manually.
- reverting a database workload to an older volume.

Do not perform storage rollback just because the workload was once pending. If the replacement PVC is now bound, attached, mounted, and serving the workload, treat it as live storage.

## Final Health Gate

Close the incident only after the storage and workload views agree:

```bash
kubectl -n <namespace> get pod <pod-name> -o wide
kubectl -n <namespace> get pvc <pvc-name> -o wide
kubectl get volumeattachments -o wide
kubectl -n vmware-system-csi get pods -o wide
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
```

Expected signals:

- PVC is `Bound` at the intended size.
- workload pod is `Running` and ready.
- matching VolumeAttachment is `attached=true`.
- CSI controller and node pods are healthy.
- no new storage-related non-running pods remain.
- no visible queued or running vCenter tasks explain a continuing symptom.

## Operating Rule

Treat `ExtendVolume task pending on CNS` as a starting signal, not a diagnosis.

Map the CNS ID to Kubernetes objects, separate resize from attach and mount, correlate with vCenter task state, and only then decide whether to wait, unpause controllers, restart CSI components, or plan a storage rollback.
