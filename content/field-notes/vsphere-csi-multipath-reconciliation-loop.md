+++
title = 'vSphere CSI Mount Loops Can Be Stale Multipath State'
date = 2026-09-08T00:00:00-05:00
draft = false
description = 'A Kubernetes storage field note on vSphere CSI pods that stay healthy while kubelet repeatedly logs already-mounted multipath errors.'
tags = ['kubernetes', 'vsphere', 'csi', 'storage', 'multipath', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

Not every `FailedMount` event means a pod is down.

In one cluster, several pods were `Running` and `Ready`, but kubelet kept emitting vSphere CSI mount warnings for weeks. The warnings had this shape:

```text
MountVolume.MountDevice failed for volume "pvc-<uid>":
mount failed: /dev/mapper/mpathX already mounted on
/var/lib/kubelet/plugins/kubernetes.io/csi/csi.vsphere.vmware.com/<volume-id>/globalmount
```

The workload was not currently down. The node had stale storage reconciliation state.

## Split Current Impact From Event Noise

Start with the workload, not the event text:

```bash
kubectl get pod -n app-namespace app-db-0 -o wide
kubectl get pvc -n app-namespace app-data -o wide
kubectl get volumeattachments -o wide | grep pvc-<uid>
```

If the pod is `Running`, the PVC is `Bound`, and the attachment says `attached=true`, the issue may be a repeated reconciliation warning rather than an active outage.

Still investigate it. Repeated mount warnings hide future failures and make real incidents harder to read.

## Inspect The Node Mount View

On the affected node, compare kubelet mounts with device mapper state:

```bash
findmnt -R /var/lib/kubelet/plugins/kubernetes.io/csi/csi.vsphere.vmware.com
grep 'csi.vsphere.vmware.com' /proc/self/mountinfo
multipath -ll
multipathd show maps status
dmsetup ls --tree
```

The suspicious pattern is a vSphere virtual disk claimed by multipath:

```text
/dev/mapper/mpathX mounted at .../globalmount
```

For vSphere CSI, the expected mount source after remediation was a plain SCSI disk such as:

```text
/dev/sdX mounted at .../globalmount
```

That distinction mattered. The node was treating a VMware virtual disk like a multipath storage device.

## Fix The Host Policy, Not Just The Pod

If `multipathd` is claiming VMware virtual disks, add a host-level blacklist while preserving real array multipath configuration:

```conf
blacklist {
  device {
    vendor "VMware"
    product "Virtual disk"
  }
}
```

Do not remove vendor-specific `devices {}` sections for real multipath storage arrays. The goal is to stop multipath from claiming vSphere virtual disks, not to disable multipath everywhere.

Apply and verify on one node at a time:

```bash
cp -a /etc/multipath.conf "/etc/multipath.conf.bak.$(date +%Y%m%d%H%M%S)"
vi /etc/multipath.conf
multipathd reconfigure
multipath -v3 -d 2>&1 | grep -i 'VMware.*Virtual disk.*blacklisted'
```

If the node still has stale mapper state, remove only confirmed-unused maps:

```bash
findmnt -S /dev/mapper/<mpath-name>
multipath -f <mpath-name>
```

Do not flush a mapper that is still mounted.

## Use A Test PVC To Prove The Node

After the host policy is fixed, schedule a small vSphere CSI test pod to that node:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: vsphere-csi-sc
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: pvc-mounter
  namespace: default
spec:
  nodeSelector:
    kubernetes.io/hostname: worker-1
  containers:
    - name: shell
      image: busybox:1.36
      command: ["sh", "-c", "echo hello-from-vsphere-csi > /data/check && sleep 3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: test-pvc
```

Then verify both Kubernetes and the node mount source:

```bash
kubectl get pod,pvc -n default -o wide
kubectl exec -n default pvc-mounter -- cat /data/check
findmnt -R /var/lib/kubelet/plugins/kubernetes.io/csi/csi.vsphere.vmware.com
```

The validation goal is specific:

```text
test pod Running
PVC Bound
mount source is /dev/sdX, not /dev/mapper/mpathX
no fresh FailedMount events on that node
```

Clean up after the test:

```bash
kubectl delete pod -n default pvc-mounter --wait=true
kubectl delete pvc -n default test-pvc
```

## Watch For A Second, Unrelated Failure

A storage fix can reveal the next problem. In the same investigation pattern, one replacement pod later mounted storage successfully but failed inside an application container because the container tried to write under `/etc/nginx` while the root filesystem was read-only.

That is not a CSI issue. It is an image or pod-spec mismatch:

```text
volume mounted successfully
init or sidecars running
application container exits
entrypoint writes to read-only path
```

When the symptom changes, reset the diagnosis. Do not keep debugging storage after the volume is mounted and the container has started.

## Practical Takeaway

For vSphere CSI mount warnings, prove whether the problem is current workload impact, stale kubelet reconciliation, or host multipath policy.

If VMware virtual disks are being claimed by multipath, fix the node image and validate with a small pinned test PVC. The durable fix belongs in the host template, not in one-off pod restarts.

## References

- [vSphere CSI Attach And Mount Checklist](/field-notes/vsphere-csi-attach-mount-checklist/)
- [Kubernetes ContainerCreating: Split Storage Failures From Missing Manifests](/field-notes/kubernetes-containercreating-storage-vs-manifest-triage/)
- [Fast OS Template Node Replacement Rehearsal](/field-notes/fast-os-template-node-replacement-rehearsal/)
