+++
title = 'VMFS Heartbeat Loss Can Look Like Kubernetes Control Plane Instability'
date = 2026-10-02T00:00:00-05:00
draft = false
description = 'Field note for correlating vSphere VMFS heartbeat timeouts with RKE2 and etcd leadership loss while avoiding a false guest-filesystem diagnosis.'
tags = ['vsphere', 'vmware', 'rke2', 'etcd', 'kubernetes', 'storage', 'troubleshooting']
categories = ['field-notes']
+++

The Kubernetes symptom was real. It was not the best starting point.

RKE2 and etcd leadership were flapping around the same minutes that vSphere reported VMFS heartbeat timeouts on the datastore backing the cluster VMs. The useful part of the investigation was moving the boundary: from "what is wrong inside the Kubernetes nodes?" to "what happened to the datastore path under those nodes?"

## Incident Shape

The visible Kubernetes symptoms were control-plane and etcd instability:

```text
etcdserver: request timed out
leaderelection lost for rke2
leaderelection lost for rke2-etcd
remotedialer reconnects
```

The stronger evidence came from vCenter. The datastore backing the cluster VMs reported repeated VMFS heartbeat timeouts:

```text
event type: esx.problem.vmfs.heartbeat.timedout
datastore: datastore-prod
volume: vmfs-volume-example
hosts: esxi-1, esxi-2
```

The timestamps lined up with the Kubernetes disruption window:

```text
2026-10-01T19:01:22Z  VMFS heartbeat timeout
2026-10-01T19:01:36Z  VMFS heartbeat timeout
2026-10-01T19:01:37Z  VMFS heartbeat timeout
2026-10-01T21:02:07Z  VMFS heartbeat timeout
2026-10-01T22:02:01Z  VMFS heartbeat timeout
2026-10-01T23:02:25Z  VMFS heartbeat timeout
2026-10-01T23:03:07Z  VMFS heartbeat timeout
```

Later, the datastore was manually refreshed or expanded:

```text
2026-10-02T00:26:40Z  datastore capacity changed
old bytes: 2,199,828,561,920
new bytes: 2,289,754,439,680
delta:     89,925,877,760 bytes
delta:     about 83.75 GiB

2026-10-02T00:26:45Z  datastore alarm changed from Red to Yellow
```

That does not prove capacity was the sole root cause. It does show storage-layer intervention happened after the heartbeat incidents and before the alarm improved.

## Correlate Placement Before Blaming Pods

The next step was not to chase random control-plane logs. It was to ask which VMs were on the affected host and datastore path.

At the time of investigation, the affected ESXi host placement included most of the critical cluster roles:

```text
master-1
master-2
master-3
etcd-1
etcd-2
multiple workers, monitor nodes, and API load balancers
```

That placement matters. A storage heartbeat problem under one ESXi host is more serious when that host carries multiple control-plane and etcd-adjacent VMs. The failure may surface as Kubernetes lease churn, but the blast radius is decided by VM placement and datastore dependency.

## Check The Guest, But Do Not Stop There

The node journal check looked for guest-side storage failure patterns:

```bash
journalctl --since '2026-10-01 18:45:00 UTC' \
  --until '2026-10-02 00:45:00 UTC' --no-pager \
  | grep -Ei 'i/o error|buffer i/o|blk_update|ext4|xfs|scsi|reset|timeout|read-only|remount|filesystem|hung|blocked|etcdserver: request timed out|leader'
```

The useful negative evidence was this:

```text
no guest kernel I/O errors
no filesystem remount read-only
no EXT4/XFS corruption evidence
no block-device error pattern in the guest journals
```

The same journal window did show control-plane symptoms:

```text
master-2  2026-10-01T20:02:07Z  leaderelection lost for rke2
master-3  2026-10-01T23:02:16Z  leaderelection lost for rke2-etcd
master-1  2026-10-02T00:02:48Z  leaderelection lost for rke2
master-3  2026-10-02T00:02:48Z  leaderelection lost for rke2-etcd
```

There were also repeated etcd client timeout messages near the same windows:

```text
Failed to get etcd ClientURLs: etcdserver: request timed out
```

That combination is important. The guests were not clearly corrupting filesystems or remounting read-only. The control plane was losing leadership while the datastore layer was reporting heartbeat trouble.

## What Changed In The Interpretation

The first tempting interpretation was guest or Kubernetes failure:

```text
RKE2 is unstable.
etcd is timing out.
Maybe a node filesystem is full or read-only.
Maybe CSI is failing attach or mount operations.
```

The evidence supported a narrower interpretation:

```text
The strongest signal was vSphere-side datastore heartbeat loss.
The Kubernetes symptoms were likely downstream of storage path instability.
Guest filesystem failure was not supported by the journal evidence checked.
```

That distinction changes the next action. If the datastore is losing heartbeat, restarting Kubernetes components or chasing pod-level symptoms can hide the actual dependency problem.

## What The Evidence Supported

Observed evidence:

```text
vCenter reported repeated VMFS heartbeat timeouts for the Kubernetes datastore
events affected more than one ESXi host, with later repeats concentrated on one host
critical control-plane and etcd VMs were placed on the affected host/datastore path
RKE2 and etcd leadership symptoms occurred near the heartbeat event windows
guest journals did not show filesystem read-only remounts or kernel block I/O errors
datastore capacity changed later by about 83.75 GiB
datastore alarm changed from Red to Yellow shortly after the storage intervention
```

Interpretation during the investigation:

```text
This looked less like a guest filesystem-full incident and more like datastore path instability surfacing as Kubernetes control-plane churn.
```

Conclusion supported by the evidence:

```text
For Kubernetes VMs on vSphere, control-plane leadership loss can be a downstream symptom of datastore heartbeat/connectivity issues.
Correlate vCenter datastore events and VM placement before treating the incident as only Kubernetes-internal.
```

## Caveats

The vCenter UI event list was the authoritative source for the historical heartbeat events in this investigation. Command-line event retrieval did not reliably return the same historical UI events.

Current VM placement may not exactly equal placement at incident time if DRS or vMotion moved VMs. In this case, the observed placement matched the affected control-plane symptoms well enough to support the correlation, but the distinction should be recorded.

The datastore expansion and alarm transition are operationally relevant, but they do not by themselves prove the heartbeat issue was only capacity pressure. They are part of the timeline, not the entire root cause.

## Operating Rule

When RKE2 or etcd leadership is unstable on vSphere, check these layers together:

```text
1. vCenter datastore alarms and VMFS heartbeat events
2. ESXi hosts reporting the datastore event
3. VM placement for control-plane and etcd nodes
4. guest journal evidence for filesystem or block-device errors
5. Kubernetes leader-election and etcd timeout timestamps
6. datastore capacity or storage-path changes after the incident
```

If the storage layer is already reporting heartbeat loss, Kubernetes leadership errors are evidence to correlate, not the whole diagnosis.
