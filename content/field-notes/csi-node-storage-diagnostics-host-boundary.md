+++
title = 'CSI Node Storage Diagnostics Need A Host Boundary'
date = 2026-08-20T00:00:00-05:00
draft = false
description = 'A runbook-style field note for safely running host-level iSCSI diagnostics from Kubernetes CSI node pods without turning troubleshooting into uncontrolled host mutation.'
tags = ['kubernetes', 'storage', 'csi', 'iscsi', 'runbooks', 'operations', 'security']
categories = ['field-notes']
+++

CSI node plugins often sit exactly where Kubernetes troubleshooting gets uncomfortable.

The pod is a Kubernetes object, but the failure is on the host: iSCSI sessions, multipath devices, kernel routes, udev, or mounted filesystems. If SSH is not the approved path, operators may need to use the CSI node pod or a temporary privileged diagnostic pod to see the host.

That is valid during an incident, but it needs a boundary. Host diagnostics should not quietly become host mutation.

## Start With The Access Model

Many CSI node DaemonSets already run with host access:

```text
hostNetwork: true
hostPID or host mounts
/host root filesystem mount
privileged container or privileged sidecar
vendor wrapper for host commands
```

Some drivers ship wrappers that execute host commands through a chroot, for example:

```text
/chroot/iscsiadm -> chroot /host iscsiadm
```

That can be safer than inventing a new privileged pod, because it uses the storage driver's existing operational boundary. It is still host-level access. Treat every command as if it is running on the worker.

## Map Worker To CSI Node Pod

First find the CSI node pod on the affected worker:

```bash
kubectl -n storage-system get pods -o wide
```

Or use JSON when pod names are noisy:

```bash
kubectl -n storage-system get pods -o json \
  | python3 -c '
import json,sys
node="worker-1"
for pod in json.load(sys.stdin)["items"]:
    if pod["spec"].get("nodeName") == node and pod["metadata"]["name"].startswith("csi-node-"):
        print(pod["metadata"]["name"])
'
```

Record the pod name, node name, driver container name, and image before running diagnostics.

## Keep The First Pass Read-Only

The first command set should establish whether the host can see storage and whether CSI is failing before or after attach.

Useful read-only checks:

```bash
kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- \
  /chroot/iscsiadm -m iface

kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- \
  /chroot/iscsiadm -m session

kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- \
  /chroot/iscsiadm -m node
```

Check routes and portal reachability from the same host context:

```bash
kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- sh -c '
  ip route get 192.0.2.10
  ip route get 198.51.100.10
  timeout 3 sh -c "echo > /dev/tcp/192.0.2.10/3260" && echo portal-a-ok
  timeout 3 sh -c "echo > /dev/tcp/198.51.100.10/3260" && echo portal-b-ok
'
```

If those checks pass, do not keep debugging “the network” in the abstract. Move toward the exact command the CSI node plugin is failing to run.

## Reproduce The Driver Path

For iSCSI-backed failures, compare the driver-equivalent discovery command with explicit controls:

```bash
kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- \
  timeout 25 /chroot/iscsiadm -m discovery -t sendtargets -p 192.0.2.10
```

Then bind the expected path:

```bash
kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- \
  timeout 25 /chroot/iscsiadm -m discovery -t sendtargets -p 192.0.2.10 -I iscsi01
```

This comparison is often more useful than another page of pod events. It answers whether the CSI node plugin's host command works in the same context where the plugin runs.

## Use strace As Evidence, Not Exploration

When the host command fails even though connectivity checks pass, trace the syscall boundary:

```bash
kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- sh -c '
  timeout 20 nsenter -t 1 -m -p -u -i -n -- \
    strace -f -e trace=socket,connect,bind,setsockopt -v -s 80 \
    iscsiadm -m discovery -t sendtargets -p 192.0.2.10 \
    2>&1 | grep -E "SO_BINDTODEVICE|connect\(|EHOSTUNREACH"'
```

The useful output is not “strace was run.” The useful output is the exact mechanism:

```text
SO_BINDTODEVICE "iscsi02"
connect(192.0.2.10:3260) = -1 EHOSTUNREACH
```

That evidence can turn an ambiguous storage ticket into a precise host configuration finding.

## If A Debug Pod Is Required

If the CSI node pod does not contain the tools you need, use a one-shot pod with explicit scope:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: storage-debug-worker-1
  namespace: storage-system
spec:
  restartPolicy: Never
  hostPID: true
  hostNetwork: true
  nodeName: worker-1
  containers:
    - name: debugger
      image: registry.example.com/storage-debug:latest
      securityContext:
        privileged: true
      command:
        - /bin/sh
        - -c
        - |
          nsenter -t 1 -m -p -u -i -n -- sleep 3600
```

Keep it node-pinned. Keep it temporary. Delete it when the evidence is collected.

This is the same class of risk as other temporary privileged maintenance helpers. For broader host-access controls and cleanup expectations, see [Temporary Privileged DaemonSets Are Host Access Changes](/field-notes/temporary-privileged-daemonset-maintenance-access/).

## Before Any Host Mutation

If the diagnosis requires a host change, stop and create a reversible boundary first.

Minimum pre-change evidence:

```bash
date
hostname
iscsiadm -m iface
iscsiadm -m session
iscsiadm -m node
ip -br addr
ip route
multipath -ll
```

Back up the host storage configuration:

```bash
tar -C /etc -czf /root/iscsi-before-change-$(date +%Y%m%d-%H%M%S).tgz iscsi
cp -a /etc/iscsi /root/iscsi-before-change
tar -tzf /root/iscsi-before-change-*.tgz | head
```

If running through a CSI node pod with `/host` mounted:

```bash
kubectl -n storage-system exec <csi-node-pod> -c csi-driver -- sh -c '
  ts=$(date +%Y%m%d-%H%M%S)
  mkdir -p /host/root/iscsi-backup
  tar -C /host -czf /host/root/iscsi-backup/etc-iscsi-$ts.tgz etc/iscsi
  cp -a /host/etc/iscsi /host/root/iscsi-backup/etc-iscsi-copy-$ts
  tar -tzf /host/root/iscsi-backup/etc-iscsi-$ts.tgz | head
'
```

Do not change service state, node databases, iface records, and workload scheduling all at once. Change one variable, then verify the driver-equivalent command.

## Reversible Change Pattern

For the open-iscsi iface-binding failure, the safe change was to move records out of the active iface directory, not delete them:

```bash
mkdir -p /root/iscsi-backup/ifaces-removed
mv /etc/iscsi/ifaces/iscsi01 /root/iscsi-backup/ifaces-removed/
mv /etc/iscsi/ifaces/iscsi02 /root/iscsi-backup/ifaces-removed/
iscsiadm -m iface
```

Then verify discovery before touching pods:

```bash
for i in 1 2 3 4 5; do
  timeout 25 iscsiadm -m discovery -t sendtargets -p 192.0.2.10 -o new
done
```

Rollback stays simple:

```bash
mv /root/iscsi-backup/ifaces-removed/iscsi01 /etc/iscsi/ifaces/
mv /root/iscsi-backup/ifaces-removed/iscsi02 /etc/iscsi/ifaces/
iscsiadm -m iface
```

The operational rule is simple: if rollback needs memory instead of commands captured in the evidence bundle, the change was not prepared well enough.

## Prove Recovery Separately

After the host command succeeds, prove Kubernetes recovery as a separate step:

```bash
kubectl get pods -A -o wide --field-selector spec.nodeName=worker-1
kubectl -n app-namespace delete pod app-cache-0 --wait=false
kubectl -n app-namespace get pods -o wide -w
```

Then verify sessions and multipath after the pod starts:

```bash
iscsiadm -m session -P 3
multipath -ll
```

A pod entering `Running` is necessary, but it is not the whole storage validation. Confirm the expected paths are present and the workload mounted the intended volume.

## Practical Takeaway

CSI storage debugging crosses the Kubernetes-host boundary. Make that boundary explicit.

Use the CSI node pod when it gives you the same host view the driver uses. Keep the first pass read-only. Capture the exact failing host command. Back up before any mutation. Move files instead of deleting them. Verify the driver path before restarting workloads.

That discipline turns a risky live-host incident into a controlled, reviewable maintenance action.

## References

- [When open-iscsi Iface Bindings Break CSI Discovery](/field-notes/open-iscsi-iface-bindings-csi-discovery/)
- [Temporary Privileged DaemonSets Are Host Access Changes](/field-notes/temporary-privileged-daemonset-maintenance-access/)
- [Kubernetes Maintenance Evidence Bundles Need A Redaction Plan](/field-notes/kubernetes-maintenance-evidence-bundles/)
