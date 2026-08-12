+++
title = 'Journal: When Storage Triage Turns Into Platform Maintenance'
date = 2026-08-12T00:00:00-05:00
draft = false
description = 'A maintenance journal from a vSphere CSI/CNS incident that expanded into GitOps containment, vCenter task correlation, CD-ROM remediation, node reboots, and lifecycle changes for safer storage maintenance.'
tags = ['kubernetes', 'vsphere', 'csi', 'vcenter', 'maintenance', 'gitops', 'rke2', 'storage', 'operations']
categories = ['posts']
+++

The maintenance started with one vSphere CSI log line:

```text
Volume with ID <cns-volume-id> has ExtendVolume task <task-id> pending on CNS.
```

That looked like a PVC resize problem. It became a broader platform maintenance event involving vSphere CNS backlog, Kubernetes `VolumeAttachment` state, GitOps self-heal, VM reconfigure locks, virtual CD-ROM cleanup, vSphere HA resets, node reboot debt, and a stop decision when the maintenance pattern created more impact than expected.

The important lesson was not a single command. It was how many control planes had to agree before the work could be called safe.

```text
Kubernetes PVC/PV/VolumeAttachment
  -> vSphere CSI operation records
  -> vCenter CNS task queue
  -> VM device state
  -> guest disk and kubelet state
  -> GitOps desired state
  -> node health and storage workload recovery
```

If any one layer was treated as authoritative by itself, the next action could have made the incident worse.

## Initial Finding

The reported CNS volume ID was mapped back to a PostgreSQL-style StatefulSet volume:

```text
CNS volume ID -> PV -> PVC -> StatefulSet pod
```

Kubernetes showed a mismatch that explained the initial symptom:

```text
PVC requested size: 100Gi
PVC current capacity: 20Gi
PVC condition: Resizing=True
PV capacity: 20Gi
VolumeAttachment: attached=false
attachError: DeadlineExceeded
```

That was the first important split: the incident was not only a resize. The active user-visible failure was attach/mount progress for the workload. The CSI controller was also retrying old work while vCenter still had queued or running backend tasks.

The replacement PVC was already bound at the intended size, but the pod was still stuck in `ContainerCreating` because the attachment path was not reconciled.

## Tests That Mattered

The useful tests were read-only and cross-layer.

Kubernetes state:

```bash
kubectl -n app-namespace get pvc app-data-old app-data-new -o wide
kubectl -n app-namespace describe pod app-db-0
kubectl get volumeattachments -o wide
kubectl -n vmware-system-csi get cnsvolumeoperationrequests.cns.vmware.com
```

CSI leadership and retry state:

```bash
kubectl -n vmware-system-csi get lease
kubectl -n vmware-system-csi get lease external-attacher-leader-csi-vsphere-vmware-com -o yaml
kubectl -n vmware-system-csi logs deploy/vsphere-csi-controller -c csi-attacher --since=30m
```

vCenter task state:

```bash
govc tasks -json -s queued -s running -n=300
govc tasks -json -s queued -s running -n=300 '/DC-Site-A/vm/K8s/worker-a-2'
```

Guest state:

```bash
ssh operator@192.0.2.24 'lsblk; findmnt; sudo dmesg | tail -100'
```

Those checks exposed the real shape:

- vCenter had non-cancelable CNS and VM reconfigure tasks queued or running.
- Some attach/detach retries were still being submitted by CSI controllers.
- A worker VM had a stale storage/device cleanup problem unrelated to the application PVC, but it held vCenter attention.
- vCenter task history and active task state did not always tell the same story unless queued/running states were queried explicitly.
- Kubernetes could show `attached=false` while vCenter and the guest already saw the disk.

That last state is dangerous. Patching `VolumeAttachment.status.attached=true` may appear to unblock the workload, but it bypasses the CSI controller's status path. That should require an explicit incident decision, not become a normal runbook step.

## Containment Attempt

The first containment goal was simple: stop adding new CSI work while vCenter drained the backend queue.

Scaling the vSphere CSI controller to zero was not enough because GitOps owned it. Live changes were quickly restored by nested Argo CD resources:

```text
root Application
  -> service ApplicationSet
  -> vSphere CSI ApplicationSet
  -> cluster vSphere CSI Application
  -> vSphere CSI controller Deployment
```

Several patches appeared to work, then self-heal restored the lower-level objects. That was a useful finding: pausing a GitOps-managed component requires walking the ownership chain, not patching the visible workload and hoping the change sticks.

The effective short-term pause became a scheduling block. Control-plane nodes eligible for the CSI controller received a temporary maintenance taint:

```bash
kubectl taint nodes cp-1 cp-2 cp-3 \
  storage-maintenance/freeze-csi=true:NoSchedule
kubectl -n vmware-system-csi delete pod -l app=vsphere-csi-controller
```

The desired replica count could still be restored to `3`, but the replacement controller pods remained `Pending` with no assigned node. That meant they were not submitting new CNS work.

The acceptance test was not "the Deployment says zero." It was:

```text
no running controller pods
latest queued CNS task timestamp stops advancing
existing backend tasks drain or fail without new submissions from that cluster
```

## VM Device Cleanup Was Not Harmless

The session also found stale virtual CD-ROM devices attached to long-lived Kubernetes VMs. Some were ISO-backed and connected, and vCenter could prompt for device-lock questions during removal.

At first glance, CD-ROM cleanup looks like inventory hygiene. In practice, it is a VM reconfigure operation. On stateful Kubernetes nodes, that means it can interact with:

- vCenter task queues.
- VM reconfigure locks.
- VMware Tools responsiveness.
- kubelet readiness updates.
- etcd and API server sensitivity to VM stun.
- storage driver reconciliation.

The safe pattern was changed to include:

- audit-only mode by default.
- `--execute` plus typed confirmation for state changes.
- role filters such as `api-lb`, `wrkr`, `mstr`, `etcd`, and `mntr`.
- include/exclude regexes for resuming partial runs.
- delay between VMs.
- Kubernetes health checks after each VM.
- explicit maintenance-window tracking.

That was the correct lifecycle improvement. But even with those controls, production runs still showed transient API and etcd symptoms during VM reconfigure tasks.

## Etcd Warnings Changed The Risk Model

During later site maintenance, the checks showed API readiness and etcd warnings around VM reconfiguration:

```text
leader failed to send out heartbeat on time
leader is overloaded likely from slow disk
peer i/o timeout on :2380
```

That evidence pointed more strongly at storage latency, VM stun, or host/datastore contention than at Kubernetes software failure. The apiserver symptoms were downstream: apiserver readiness failed because etcd was not healthy enough for the moment.

The lifecycle change is clear: etcd nodes should not be included in broad VM device hygiene sweeps unless the work has a specific etcd-safe plan.

Recommended order for future vSphere VM hygiene:

```text
1. API load balancers or non-Kubernetes support VMs
2. workers, one at a time
3. control-plane nodes, one at a time with etcd/API checks
4. etcd nodes only in a separate window or not at all unless required
```

Stop conditions should include:

- etcd leader churn.
- apiserver `/readyz` failures caused by etcd.
- repeated VM reconfigure tasks taking minutes instead of seconds.
- node `NotReady` persisting beyond the expected transient window.
- storage CSI pods failing to re-register after node maintenance.

## Reboot Debt Was A Separate Maintenance Track

While preparing follow-up maintenance, the team checked whether nodes actually needed RKE2 restarts. Kubernetes showed nodes and static pods healthy. Host checks told a different story: many older Ubuntu nodes had `/var/run/reboot-required` present because kernel packages had been installed months earlier.

That created a second maintenance track:

```text
CD-ROM removal: vCenter device hygiene
node reboots: operating-system kernel activation debt
```

Combining those in one window increased risk. It was operationally efficient, but it also made cause attribution harder. If a node became `NotReady`, was it the vCenter reconfigure, the reboot, the storage driver, or the workload rescheduling?

The better lifecycle pattern is to keep those as separate changes unless there is a strong reason to combine them.

For reboot windows, the useful gates were:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o wide
ssh operator@192.0.2.24 'test -f /var/run/reboot-required && echo reboot-required || echo clean'
ssh operator@192.0.2.24 'systemctl is-active rke2-server rke2-agent 2>/dev/null || true'
```

The reboot tool then worked one node at a time, verified host boot ID changed, waited for Kubernetes boot ID/Ready to reconcile, and uncordoned before moving on.

## Temporary Access Needs A Cleanup Contract

One site required a temporary DaemonSet to install passwordless sudo for the maintenance user. That unblocked controlled node reboots, but it created a new obligation: remove the privilege after the window.

The session ended with one environment fully cleaned:

```text
DaemonSet removed
sudoers file removed from all hosts
no background reboot/remediation processes left running
all nodes Ready
zero cordoned nodes
```

This should become a standard maintenance invariant. Temporary access is not complete when the work succeeds. It is complete when the access path is removed or explicitly transferred into permanent access management.

## Resolution Shape

The incident did not end with one universal fix. It ended with several scoped outcomes:

- The original storage investigation produced a safe triage path for CNS resize/attach confusion.
- vSphere CSI controller containment was proven to require effective runtime verification, not just GitOps object patches.
- CD-ROM cleanup scripts gained dry-run, confirmation, role filter, delay, health-check, and resume controls.
- Some environments were fully remediated and rebooted successfully.
- One production reboot sequence was intentionally stopped after impact exceeded the desired threshold.
- Temporary sudo access was cleaned up after stopping.
- Remaining node reboots and future datacenter windows were put on hold pending a less impactful CD-ROM removal method.

The most important resolution was the stop decision. Continuing because a script can continue is not operational discipline. When health checks show repeated impact, stop, restore the cluster to a clean state, and redesign the method.

## Lifecycle Changes

The maintenance session produced these durable changes.

1. Treat vCenter device changes as Kubernetes maintenance.

Removing a CD-ROM from a Kubernetes node is not a cosmetic vCenter task. It can trigger VM reconfigure locks and transient node or etcd symptoms. It belongs in the same risk class as other node maintenance.

2. Keep storage-controller pause procedures GitOps-aware.

Runbooks should document the ownership chain and the effective pause gate:

```text
desired object patched
controller pods not running
new backend task timestamps stop advancing
rollback path documented
```

3. Query active vCenter tasks explicitly.

Default task history is not enough. Use queued/running filters and VM-scoped checks. The absence of a task in recent history does not prove the backend is idle.

4. Split hygiene, reboot, and storage recovery windows.

Combining them can be justified, but the default should be separate windows with separate evidence bundles. This keeps blast radius and cause attribution clear.

5. Exclude or isolate etcd nodes from broad VM hygiene.

Etcd reacts poorly to storage latency and VM stun. If etcd VMs must be modified, use a separate role-specific plan with quorum checks and stop conditions.

6. Make temporary privileged access auditable and reversible.

Every DaemonSet, sudoers drop, host-access helper, or break-glass path needs a cleanup check in the maintenance closeout.

7. Convert successful manual investigations into lifecycle tests.

The next version of the maintenance tooling should test:

- vCenter task backlog before each VM.
- API and etcd readiness after each VM.
- node Ready and boot ID after each reboot.
- storage driver registration after worker reboots.
- no remaining CD-ROMs after device cleanup.
- no remaining privileged maintenance artifacts after cleanup.

## Related Runbooks

The tactical pieces from this incident are split into smaller notes:

- [vSphere CSI CNS ExtendVolume Triage](/field-notes/vsphere-csi-cns-extendvolume-triage/)
- [GitOps-Owned vSphere CSI Maintenance Pauses](/field-notes/gitops-owned-vsphere-csi-maintenance-pause/)
- [vSphere CD-ROM Host Device Cleanup With govc](/field-notes/vsphere-cdrom-host-device-cleanup-govc/)
- [vSphere HA Reset Evidence For Kubernetes Nodes](/field-notes/vsphere-ha-reset-evidence-kubernetes-nodes/)
- [Kubernetes Retained PV Missing PVC Rebind](/field-notes/kubernetes-retained-pv-missing-pvc-rebind/)
- [Kubernetes Maintenance Evidence Bundles Need A Redaction Plan](/field-notes/kubernetes-maintenance-evidence-bundles/)

The journal-level lesson is this: maintenance is not a list of commands. It is a controlled change system with evidence, containment, stop conditions, and cleanup.
