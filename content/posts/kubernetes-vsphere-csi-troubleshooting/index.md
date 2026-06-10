+++
title = 'Troubleshooting Kubernetes Storage Migration To vSphere CSI'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'A practical incident walkthrough for Kubernetes monitoring PVC failures, stale CSI storage, vSphere CSI attach and mount validation, and the disk.EnableUUID requirement.'
tags = ['kubernetes', 'vsphere', 'vmware', 'storage', 'troubleshooting', 'sre']
categories = ['notes']
+++

Storage incidents in Kubernetes are rarely just storage incidents.

In one troubleshooting session, a monitoring namespace looked broken in several different ways at once. `Alertmanager` was stuck pending. `Prometheus` was stuck in init. Node exporter pods were being rejected by Pod Security. The system upgrade controller had a long tail of evicted pods. Several control-plane nodes were under disk pressure.

The useful move was not to fix the first scary event. It was to separate the failures by ownership boundary: scheduler, storage class, CSI driver, VM configuration, and GitOps drift.

## Start With The Events

The cluster events showed multiple unrelated-looking warnings:

```text
FailedCreate           daemonset/kube-prometheus-stack-prometheus-node-exporter
EvictionThresholdMet   node/sat-1-mstr-1-rancher
FailedScheduling       pod/system-upgrade-controller-...
```

The upgrade controller was blocked because it had required affinity for control-plane nodes, while all eligible control-plane nodes had `DiskPressure` taints:

```text
0/6 nodes are available:
3 node(s) didn't match Pod's node affinity/selector,
3 node(s) had untolerated taint {node.kubernetes.io/disk-pressure: }.
```

That mattered, but it was not the same problem as monitoring storage. It was a cluster health issue that could obscure the storage issue if treated as the root cause for everything.

For monitoring, the important evidence was in the namespace itself:

```text
kubectl get pods -n vcobserve -o wide
```

The relevant state was:

```text
alertmanager-kube-prometheus-stack-alertmanager-0   0/2   Pending
prometheus-kube-prometheus-stack-prometheus-0       0/2   Init:0/1
```

The PVCs told the real story:

```text
kubectl get pvc -n vcobserve -o wide
```

```text
NAME                    STATUS    STORAGECLASS
alertmanager-...         Pending   vsphere-storage-class
prometheus-...           Bound     hpe-alletra-ssd
```

Two monitoring components were failing for different storage reasons:

- `Alertmanager` referenced an old or missing vSphere StorageClass name.
- `Prometheus` still had an older HPE CSI-backed PVC.
- The current target storage path was vSphere CSI through `vsphere-csi-sc`.

## Check Storage Classes Before Recreating Workloads

The cluster had more than one default-looking storage path over its lifetime:

```text
kubectl get storageclass
```

```text
NAME                        PROVISIONER
hpe-alletra-ssd (default)   csi.hpe.com
vsphere-csi-sc (default)    csi.vsphere.vmware.com
```

That is a red flag. Even if only one default is effective at a time, workloads can carry explicit `storageClassName` values from older Helm values, Prometheus Operator CRs, or historical PVCs.

The storage question became concrete:

```text
Which PVCs and PVs still depend on the old HPE path?
Which monitoring CRs will recreate PVCs with the wrong class if ArgoCD syncs?
Which nodes can actually attach and mount vSphere CSI volumes?
```

For stale CSI references, the cluster-wide checks were simple:

```bash
kubectl get pvc -A -o json | jq -r '.items[] | select(.spec.storageClassName == "hpe-alletra-ssd") | [.metadata.namespace,.metadata.name,.status.phase,.spec.volumeName] | @tsv'

kubectl get pv -o json | jq -r '.items[] | select(.spec.storageClassName == "hpe-alletra-ssd") | [.metadata.name,.status.phase,(.spec.claimRef.namespace // ""),(.spec.claimRef.name // "")] | @tsv'
```

After remediation, both commands returned no rows.

## CSI Pods Running Does Not Prove Mounts Work

Both CSI stacks had running pods:

```bash
kubectl get pods -n hpe-storage -o wide
kubectl get pods -n vmware-system-csi -o wide
```

That confirmed driver availability, not workload success.

The old Prometheus PV showed the historical dependency:

```text
pv.kubernetes.io/provisioned-by: csi.hpe.com
external-attacher/csi-hpe-com
```

The desired end state was not "CSI pods are running." The desired end state was more specific:

- Prometheus and Alertmanager PVCs are bound to `vsphere-csi-sc`.
- Pods can schedule without a permanent node pin.
- `VolumeAttachment` objects show attached volumes on the selected worker.
- Containers move past init and report ready.

## The vSphere-Specific Trap: Disk UUID Visibility

After moving the monitoring PVC intent to `vsphere-csi-sc`, provisioning worked, but pod mounts still failed on workers that were missing the vSphere disk UUID setting.

For vSphere CSI, worker VMs need disk UUID visibility enabled:

```text
disk.EnableUUID = "TRUE"
```

Without that, a volume can appear provisioned and even reach the attach path, while kubelet and the CSI node plugin cannot reliably discover the attached virtual disk inside the guest.

The remediation pattern was deliberately operational:

```bash
kubectl cordon <worker>
kubectl drain <worker> --ignore-daemonsets --delete-emptydir-data
```

Then, outside Kubernetes:

```text
Power off VM
Set disk.EnableUUID = "TRUE"
Power on VM
```

Then return the node:

```bash
kubectl uncordon <worker>
kubectl get nodes
```

This was repeated one worker at a time. The point was not just to set a VM flag. The point was to preserve workload availability while changing a prerequisite underneath the CSI node path.

## Temporary Pins Are Fine, But Remove Them

During the incident, pinning Prometheus and Alertmanager to a known-good worker helped prove the storage path without constantly fighting scheduler movement.

That pin had to be temporary.

Once the workers were fixed, the Prometheus Operator CRs were patched to remove the node selector:

```bash
kubectl patch prometheus -n vcobserve kube-prometheus-stack-prometheus --type=merge -p '{"spec":{"nodeSelector":null}}'

kubectl patch alertmanager -n vcobserve kube-prometheus-stack-alertmanager --type=merge -p '{"spec":{"nodeSelector":null}}'
```

Then verify both the CRs and rendered StatefulSets:

```bash
kubectl get prometheus -n vcobserve kube-prometheus-stack-prometheus -o jsonpath='{.spec.nodeSelector}{"\n"}'
kubectl get alertmanager -n vcobserve kube-prometheus-stack-alertmanager -o jsonpath='{.spec.nodeSelector}{"\n"}'

kubectl get statefulset -n vcobserve prometheus-kube-prometheus-stack-prometheus -o jsonpath='{.spec.template.spec.nodeSelector}{"\n"}'
kubectl get statefulset -n vcobserve alertmanager-kube-prometheus-stack-alertmanager -o jsonpath='{.spec.template.spec.nodeSelector}{"\n"}'
```

Empty output was the expected result.

## Prove Mobility, Not Just Recovery

The strongest validation was that monitoring could move to another worker and keep its vSphere CSI volumes healthy.

After removing the temporary pin, the operator rolled the StatefulSet pods and they scheduled on another worker:

```text
alertmanager-kube-prometheus-stack-alertmanager-0   2/2 Running   sat-1-wrkr-3-rancher
prometheus-kube-prometheus-stack-prometheus-0       2/2 Running   sat-1-wrkr-3-rancher
```

The PVCs were bound to the intended StorageClass:

```text
NAME                    STATUS   STORAGECLASS
alertmanager-...         Bound    vsphere-csi-sc
prometheus-...           Bound    vsphere-csi-sc
```

And the `VolumeAttachment` objects moved with the pods:

```text
ATTACHER                 PV                                         NODE                   ATTACHED
csi.vsphere.vmware.com   pvc-15299db7-4fca-47c4-92f2-5fdbba02a43d   sat-1-wrkr-3-rancher   true
csi.vsphere.vmware.com   pvc-c92e2898-b016-4a2a-a2b1-591c3b423948   sat-1-wrkr-3-rancher   true
```

Finally, the monitoring CRs reported healthy reconciliation:

```text
prometheus.monitoring.coreos.com/...     READY 1   RECONCILED True   AVAILABLE True
alertmanager.monitoring.coreos.com/...   READY 1   RECONCILED True   AVAILABLE True
```

That proved more than recovery. It proved the storage class, CSI controller, CSI node plugin, vSphere VM settings, scheduler placement, and Prometheus Operator reconciliation all agreed.

## GitOps Follow-Up

Live fixes are not finished until GitOps will preserve them.

The follow-up was to update the ArgoCD-managed kube-prometheus-stack values so the next sync would not reintroduce the incident:

- Set Prometheus storage explicitly to `vsphere-csi-sc`.
- Set Alertmanager storage explicitly to `vsphere-csi-sc`.
- Remove references to `hpe-alletra-ssd` and the old `vsphere-storage-class` name.
- Do not permanently pin monitoring pods to one worker.
- Document `disk.EnableUUID = "TRUE"` as a worker VM requirement for vSphere CSI.
- Validate rendered Prometheus and Alertmanager CRs before sync.

The operational fix was Kubernetes work. The durable fix was configuration ownership.

## Lessons

The incident had several overlapping symptoms, but the useful model was simple:

- Events show pressure points, not always root cause.
- PVC and PV metadata reveal historical storage dependencies.
- CSI controller health does not prove guest-level volume discovery.
- vSphere CSI depends on VM configuration, not just Kubernetes objects.
- Temporary scheduling pins are diagnostic tools, not final architecture.
- Recovery should prove workload mobility, not only that one pod is running now.
- GitOps must be updated after live remediation or the cluster will drift back.

The key storage lesson: when migrating Kubernetes workloads to vSphere CSI, do not stop at "PVC is bound." Follow the volume all the way through provisioning, attachment, guest discovery, mount, pod readiness, rescheduling, and GitOps reconciliation.
