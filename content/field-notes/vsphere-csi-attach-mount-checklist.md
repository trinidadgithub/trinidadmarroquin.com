+++
title = 'vSphere CSI Attach And Mount Checklist'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for checking Kubernetes PVCs, StorageClasses, VolumeAttachments, worker VM disk UUID settings, and vSphere CSI mount readiness.'
tags = ['kubernetes', 'vsphere', 'vmware', 'storage', 'troubleshooting']
categories = ['field-notes']
+++

Use this checklist when a Kubernetes workload has a PVC that should use vSphere CSI, but the pod is pending, stuck in init, or failing to mount the volume.

The goal is to follow the volume from intent to pod readiness:

```text
StorageClass -> PVC -> PV -> VolumeAttachment -> worker VM -> kubelet mount -> pod ready
```

## Check The Workload State

Start with pods and PVCs in the affected namespace:

```bash
kubectl get pods -n <namespace> -o wide
kubectl get pvc -n <namespace> -o wide
```

Look for:

- pods stuck in `Pending`, `ContainerCreating`, or `Init:*`.
- PVCs stuck in `Pending`.
- PVCs bound to an unexpected `STORAGECLASS`.
- pods pinned to one worker because of a temporary `nodeSelector`.

Describe the blocked pod and PVC:

```bash
kubectl describe pod -n <namespace> <pod-name>
kubectl describe pvc -n <namespace> <pvc-name>
```

Useful event reasons include:

- `FailedScheduling`.
- `FailedAttachVolume`.
- `FailedMount`.
- `ProvisioningFailed`.

## Confirm The StorageClass

List available StorageClasses:

```bash
kubectl get storageclass
```

For vSphere CSI, the provisioner should be:

```text
csi.vsphere.vmware.com
```

If a workload is expected to use a class such as `vsphere-csi-sc`, verify the PVC actually references it:

```bash
kubectl get pvc -n <namespace> <pvc-name> -o jsonpath='{.spec.storageClassName}{"\n"}'
```

If migrating from an older storage backend, search for stale class references:

```bash
kubectl get pvc -A -o json \
  | jq -r '.items[] | select(.spec.storageClassName == "hpe-alletra-ssd") | [.metadata.namespace,.metadata.name,.status.phase,.spec.volumeName] | @tsv'

kubectl get pv -o json \
  | jq -r '.items[] | select(.spec.storageClassName == "hpe-alletra-ssd") | [.metadata.name,.status.phase,(.spec.claimRef.namespace // ""),(.spec.claimRef.name // "")] | @tsv'
```

No output is expected after the old storage class is fully removed.

## Check vSphere CSI Components

Verify the vSphere CSI controller and node pods are running:

```bash
kubectl get pods -n vmware-system-csi -o wide
```

This only proves the driver pods are up. It does not prove workload mounts can succeed.

Check recent CSI-related events:

```bash
kubectl get events -A --sort-by=.lastTimestamp \
  | grep -i 'vsphere\|csi\|volume\|mount\|attach'
```

If the issue is namespace-specific, narrow the event query:

```bash
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

## Follow The PV

Get the PV backing the PVC:

```bash
kubectl get pvc -n <namespace> <pvc-name> -o jsonpath='{.spec.volumeName}{"\n"}'
```

Inspect the PV:

```bash
kubectl get pv <pv-name> -o yaml
```

Confirm:

- `spec.storageClassName` is the expected vSphere CSI class.
- `pv.kubernetes.io/provisioned-by` is `csi.vsphere.vmware.com`.
- there are no finalizers or annotations from an older CSI provider.

## Check VolumeAttachments

List attachments:

```bash
kubectl get volumeattachments -o wide
```

Expected healthy signal:

```text
ATTACHER                 PV          NODE          ATTACHED
csi.vsphere.vmware.com   pvc-...     worker-name   true
```

If attachment exists but the pod cannot mount, inspect it:

```bash
kubectl describe volumeattachment <volumeattachment-name>
```

This helps separate attach failures from guest-level mount or device discovery failures.

## Verify Worker VM Requirement

For vSphere CSI, worker VMs need disk UUID visibility enabled:

```text
disk.EnableUUID = "TRUE"
```

Without this setting, volumes may provision and attach, but kubelet and the CSI node plugin may fail to discover or mount the disk inside the guest.

With `govc`, inspect the VM extra config:

```bash
govc vm.info -e /path/to/worker-vm | grep -i 'disk.enableUUID'
```

Expected:

```text
disk.EnableUUID = TRUE
```

If it is missing, remediate one worker at a time:

```bash
kubectl cordon <worker>
kubectl drain <worker> --ignore-daemonsets --delete-emptydir-data
```

Then in vSphere:

```text
Power off VM
Set disk.EnableUUID = "TRUE"
Power on VM
```

Return the node:

```bash
kubectl uncordon <worker>
kubectl get nodes
```

## Remove Temporary Scheduling Pins

Temporary `nodeSelector` pins are useful during troubleshooting, but they should not remain as the final fix.

For Prometheus Operator resources, check selectors on the CRs:

```bash
kubectl get prometheus -n <namespace> <name> -o jsonpath='{.spec.nodeSelector}{"\n"}'
kubectl get alertmanager -n <namespace> <name> -o jsonpath='{.spec.nodeSelector}{"\n"}'
```

Check the rendered StatefulSets too:

```bash
kubectl get statefulset -n <namespace> <prometheus-statefulset> -o jsonpath='{.spec.template.spec.nodeSelector}{"\n"}'
kubectl get statefulset -n <namespace> <alertmanager-statefulset> -o jsonpath='{.spec.template.spec.nodeSelector}{"\n"}'
```

Empty output means no node selector is set.

If a temporary selector must be removed live:

```bash
kubectl patch prometheus -n <namespace> <name> --type=merge -p '{"spec":{"nodeSelector":null}}'
kubectl patch alertmanager -n <namespace> <name> --type=merge -p '{"spec":{"nodeSelector":null}}'
```

Make the same change in GitOps-managed values after the live fix.

## Prove Mobility

Recovery is not complete just because the pod runs once.

Validate that the workload can run on a worker with vSphere CSI volumes attached:

```bash
kubectl get pods -n <namespace> -o wide
kubectl get pvc -n <namespace> -o wide
kubectl get volumeattachments -o wide
```

Expected signals:

- pods are `Running` and ready.
- PVCs are `Bound` to the intended vSphere CSI StorageClass.
- `VolumeAttachment` entries are `ATTACHED=true` on the worker hosting the pod.
- workload CRs report reconciled and available, if using an operator.

For Prometheus Operator resources:

```bash
kubectl get prometheus,alertmanager -n <namespace> -o wide
```

Expected:

```text
RECONCILED   AVAILABLE
True         True
```

## GitOps Follow-Up

After live remediation, update the desired state:

- set the workload storage class explicitly to the vSphere CSI class.
- remove old storage class names from Helm values or manifests.
- remove temporary node pins.
- document `disk.EnableUUID = "TRUE"` in VM template or worker provisioning requirements.
- render the Prometheus and Alertmanager CRs before syncing.

The durable fix is not a successful manual mount. It is a desired state that recreates the same healthy storage path after the next sync, rollout, or node replacement.
