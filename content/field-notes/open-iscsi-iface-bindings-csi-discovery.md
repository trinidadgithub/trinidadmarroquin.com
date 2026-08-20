+++
title = 'When open-iscsi Iface Bindings Break CSI Discovery'
date = 2026-08-20T00:00:00-05:00
draft = false
description = 'A Kubernetes storage field note on diagnosing CSI NodeStage failures caused by legacy open-iscsi iface bindings and unbound SendTargets discovery.'
tags = ['kubernetes', 'storage', 'csi', 'iscsi', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

Some Kubernetes storage failures are not attach failures. The volume is created. The attachment says it is attached. The pod still cannot start.

In one cluster, several storage-backed pods were stuck in `ContainerCreating` or `Init` after node maintenance. Existing pods with storage kept running, but new pods could not stage volumes on a subset of workers.

The important split was this:

```text
existing sessions keep working
fresh CSI NodeStage requires discovery
discovery fails only on legacy workers
```

That shape points below Kubernetes and above the storage array. The CSI node plugin was asking the host to discover an iSCSI target, and the host-side open-iscsi configuration was changing how that discovery behaved.

## Symptom

The pod events and CSI node logs pointed at NodeStage and device discovery:

```text
MountVolume.MountDevice failed for volume "pvc-<uid>":
rpc error: code = Internal desc = Failed to stage volume <volume-id>,
err: device not found with serial <serial> or target
```

CSI logs showed `iscsiadm` discovery failing with a network-looking error:

```text
iscsiadm: cannot make connection to 192.0.2.10: No route to host
iscsiadm: connection login retries exceeded
iscsiadm: Could not perform SendTargets discovery: iSCSI PDU timed out
```

That message is easy to misread as a broken route, VLAN, firewall, or storage portal. In this case, basic connectivity was good.

## The False Network Lead

The worker had two dedicated storage interfaces:

```text
iscsi01  192.0.2.26/24
iscsi02  198.51.100.26/24
```

Linux routing was correct:

```text
192.0.2.10      dev iscsi01 src 192.0.2.26
198.51.100.10   dev iscsi02 src 198.51.100.26
```

Both storage portals answered ICMP and TCP/3260. Explicitly binding discovery to the correct interface worked:

```bash
iscsiadm -m discovery -t sendtargets -p 192.0.2.10 -I iscsi01
iscsiadm -m discovery -t sendtargets -p 198.51.100.10 -I iscsi02
```

The driver-equivalent command failed:

```bash
iscsiadm -m discovery -t sendtargets -p 192.0.2.10
```

So the failure was not “the node cannot reach storage.” The failure was “unbound discovery is not using the same path Linux routing would choose.”

## The Smoking Gun

`strace` showed open-iscsi binding the discovery socket to the wrong interface during retries:

```bash
timeout 20 strace -f \
  -e trace=socket,connect,bind,setsockopt \
  -v -s 80 \
  iscsiadm -m discovery -t sendtargets -p 192.0.2.10 \
  2>&1 | grep -E 'SO_BINDTODEVICE|connect\(|EHOSTUNREACH'
```

The pattern was clear:

```text
SO_BINDTODEVICE "iscsi01"
connect(192.0.2.10:3260) = 0

SO_BINDTODEVICE "iscsi02"
connect(192.0.2.10:3260) = -1 EHOSTUNREACH
```

The mirror-image test against the second portal showed the opposite wrong binding:

```text
SO_BINDTODEVICE "iscsi01"
connect(198.51.100.10:3260) = -1 EHOSTUNREACH
```

The storage network was reachable. open-iscsi was explicitly binding discovery to an interface that could not route to the selected portal.

## Why Only Some Workers Failed

The cluster had two generations of workers:

```text
legacy workers:          /etc/iscsi/ifaces/iscsi01 and iscsi02 exist
template-built workers:  no custom open-iscsi iface records
```

Every worker with legacy iface records failed the driver-equivalent unbound discovery command. Every template-built worker without custom iface records succeeded.

That generational split mattered more than the Kubernetes symptom.

The legacy nodes had been manually configured years earlier. Newer nodes came from a standardized image and relied on normal Linux routing. The newer behavior was what the CSI driver expected: no explicit open-iscsi iface records, so unbound discovery used the kernel route table.

## Why Existing Storage Worked

This failure did not break every mounted volume because the CSI driver only needed discovery when there was no active session to the target.

The simplified path looked like this:

```text
target already logged in
-> CSI skips discovery
-> rescan existing session
-> new LUN can appear

target not logged in
-> CSI runs SendTargets discovery
-> open-iscsi rotates through legacy ifaces
-> wrong iface hits EHOSTUNREACH
-> NodeStage fails
```

That explains the confusing symptom: old pods looked fine while new pods were stuck. The broken path was fresh discovery, not steady-state I/O.

Node reboots made the issue visible by clearing active iSCSI sessions. The reboot was the trigger. The legacy iface records were the root-cause condition.

## Safe Remediation Pattern

The fix was not to delete one storage path. Removing only one custom iface record did not solve the problem reliably. Any custom bound iface record could pull unbound discovery into the wrong path.

The successful remediation was to normalize the legacy workers to match the template-built workers:

```text
backup /etc/iscsi
move custom iface records out of /etc/iscsi/ifaces
verify unbound discovery succeeds repeatedly
verify existing sessions remain logged in
let CSI retry NodeStage
```

The files were moved, not deleted:

```bash
mkdir -p /root/iscsi-backup-<date>/ifaces-removed
mv /etc/iscsi/ifaces/iscsi01 /root/iscsi-backup-<date>/ifaces-removed/
mv /etc/iscsi/ifaces/iscsi02 /root/iscsi-backup-<date>/ifaces-removed/
```

Then the driver-equivalent command became the verification gate:

```bash
ok=0; fail=0
for i in 1 2 3 4 5; do
  out=$(timeout 25 iscsiadm -m discovery -t sendtargets -p 192.0.2.10 -o new 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    ok=$((ok+1)); echo "try$i OK"
  else
    fail=$((fail+1)); echo "try$i FAIL rc=$rc"
  fi
done
echo "ok=$ok fail=$fail"
```

Only after discovery passed repeatedly did the operator allow CSI to retry the stuck pods.

## What To Preserve In The Evidence

Keep enough evidence to prove the layer where the failure happened:

- pod event showing the CSI stage or mount failure.
- PVC, PV, StorageClass, and CSI driver name.
- VolumeAttachment state, especially if it already says `attached=true`.
- CSI node log with the `iscsiadm` or device discovery error.
- host routes to each storage portal.
- TCP/3260 checks to each portal.
- `iscsiadm -m iface` output.
- unbound discovery result.
- iface-bound discovery result.
- `strace` showing `SO_BINDTODEVICE` and `EHOSTUNREACH`.
- before and after `/etc/iscsi` backup paths.
- repeated post-change discovery results.
- final pod recovery state.

That evidence keeps the incident from collapsing into a vague “storage was down” summary.

## Practical Takeaway

If Kubernetes says the volume attached but the pod cannot stage it, inspect the host-side discovery path.

For iSCSI-backed CSI drivers, `No route to host` from `iscsiadm` does not always mean the Linux route table is wrong. If custom open-iscsi iface records exist, unbound discovery may bind to a storage NIC that cannot reach the selected portal.

Compare a failing legacy worker with a known-good template-built worker. If the good nodes have no custom iface records and discovery succeeds there, the fix may be configuration normalization, not a storage-array repair.

## References

- [Kubernetes ContainerCreating: Split Storage Failures From Missing Manifests](/field-notes/kubernetes-containercreating-storage-vs-manifest-triage/)
- [CSI Node Storage Diagnostics Need A Host Boundary](/field-notes/csi-node-storage-diagnostics-host-boundary/)
- [vSphere CSI Attach And Mount Checklist](/field-notes/vsphere-csi-attach-mount-checklist/)
