+++
title = 'Zero Replicas Is Not a Shutdown Plan'
date = 2026-11-21T00:00:00-06:00
draft = false
description = 'Part 3 of Retiring Rancher-Managed Kubernetes: quiescing workloads at their owning layer, preserving claims, and explaining CSI attachments that remain after scale-down.'
tags = ['kubernetes', 'rke2', 'operators', 'csi', 'storage', 'decommissioning', 'observability']
categories = ['posts']
series = ['Retiring Rancher-Managed Kubernetes']
+++

Part 3 of [Retiring Rancher-Managed Kubernetes](/posts/retiring-rancher-managed-kubernetes/).

Grafana had been scaled down. Later, its Deployment wanted one replica again.

That observation was more useful than the earlier successful scale command. The command changed a field. It had not established lasting quiescence across the controllers and declarations capable of changing that field afterward.

The storage inventory delivered the same lesson from another direction. Seven stateful workloads reached zero replicas in each environment. UAT's attachment inventory became empty; production still had three attachments reporting `true`.

A shutdown plan needed to explain both differences before removing the API that could show them.

## Change the Owning Declaration

The seven observability StatefulSets did not all have the same owner. Four could be scaled directly in the recorded procedure. Two Prometheus instances and one Alertmanager instance were generated from operator custom resources.

For those three, the change belonged on the custom resources. The operator could then reconcile its generated StatefulSets to the requested state. Blindly scaling the child objects would leave the parent's declaration unchanged.

The conceptual paths were:

```text
Directly managed StatefulSet -> spec.replicas
Prometheus custom resource  -> operator -> generated StatefulSet
Alertmanager custom resource -> operator -> generated StatefulSet
GitOps declaration -> reconciler -> either of the above
```

Stopping an operator is not automatically the first step either. An operator may still be needed to carry out the final desired-state change. Identify the owner, change the supported declaration, observe convergence, then decide which controller is no longer needed.

Both clusters also had System Upgrade Controller Plans. The controller Deployment was scaled to zero and observed at `0/0`. That reduced a known source of change; it did not prove that an upstream reconciler could never restore it or that an already-running upgrade Job had stopped. Controller replicas, active Jobs, and upstream ownership are separate checks.

## The Grafana Return Did Not Identify Its Writer

In UAT, the Grafana Deployment had a controlling owner reference to a Grafana custom resource and a `managed-by` label naming the operator. A query for Grafana resources returned none. The operator Deployment was already at zero, while the Grafana Deployment's desired replicas were one.

Those observations did not identify the writer that restored replicas. An owner reference describes a relationship; it is not a timestamped audit trail. A label is even less conclusive. Historical owner metadata, another reconciler, or an overlapping change remained possibilities.

The Deployment was scaled again and a subsequent check showed `0/0`. Production similarly required another scale-down before its recorded zero state. The practical improvement was to re-read desired state and observed workload state after the change, rather than promote one successful API response into a permanent fact.

For live diagnosis, metadata such as `managedFields` can suggest field managers, but proving a specific historical write may require API audit events or controller logs.

## Retain Is a Policy, Not a Backup

The inspected StatefulSets had `Retain` PVC policies. That supported stopping their replicas while retaining claims. Many listed PVs, however, used a `Delete` reclaim policy.

These policies operate at different boundaries:

| Policy or state | What it addresses |
| --- | --- |
| StatefulSet PVC retention on scale-down | Whether that controller deletes its associated PVCs when scaling |
| PV reclaim policy | Backend disposition when the claim/PV lifecycle reaches reclamation |
| PVC `Bound` | A Kubernetes binding exists |
| Application backup | Recoverability of application data, requiring separate evidence |

Retaining a claim does not prove recoverability. Deleting a claim or namespace can enter a different lifecycle from scaling the workload. That distinction was particularly important because the goal was retirement, not a test of backend deletion behavior.

## Join the Objects Before Counting Them

The useful storage chain was:

```text
Pod -> namespaced PVC -> PV -> CSI VolumeAttachment -> node -> backend volume
```

Pod phase alone did not describe that chain. A failed pod could still reference a claim. A `Terminating` claim could still be associated with an attachment. An empty Kubernetes attachment list did not prove an empty array ACL or no host session.

In UAT, seven attachments corresponded to the seven active stateful consumers. After scale-down, no VolumeAttachments were listed and the inspected PVCs remained Bound. That established a clean Kubernetes-side checkpoint, not array-side deletion authority.

Production began with ten attachments. Seven cleared after the observability workloads stopped. Three remained, associated with old iSCSI test pods on monitoring nodes.

## Preserve the Exception Instead of Erasing Its Symptoms

The three test pods were `Failed`, with no controlling owner shown. A delete request printed “deleted,” but the command was interrupted and subsequent queries still found the resources. The pods' deletion timestamps predated the retirement, their claims were already `Terminating`, and their attachments still reported `attached=true` with no recorded detach error.

No detach error was not proof of successful detachment. The attachment objects were not themselves shown as deleting. The absence of pod finalizers did not establish that the whole storage workflow had finished.

The operator explicitly chose not to let those legacy test resources block permanent cluster retirement. The record then continued toward node shutdown. It does not show the suggested guest iSCSI/multipath checks or a successful array-side resolution before the monitors were reported off.

The defensible description is therefore **retirement continued with three documented storage exceptions**. It is not “all volumes detached.” A reusable handoff must name each attachment, claim, PV, node, backend mapping, unresolved condition, and responsible owner. Where the historical record lacks those checks, the article should preserve the gap rather than fill it with a success label.

Force-removing finalizers or attachment objects would have changed the API inventory without necessarily resolving host or array state. The point was to preserve an explainable transition, not manufacture an empty table.

## Quiescence Is a Relationship Between Layers

The final workload check must ask more than whether ready replicas are zero. Does the intended desired state remain zero? Have consuming pods terminated? Are claims retained as planned? Have attachments cleared or become explicitly owned exceptions? Is any upstream controller still asking for the workload to return?

Only then can the shutdown sequence decide when CSI, networking, and the API have performed their last useful reconciliation. [Part 4](/posts/retiring-rancher-managed-kubernetes/shutdown-and-handoff/) follows that boundary through the guest and hypervisor layers.

## Sources and Reading Order

User messages 83, 95, and 100 show UAT controller ownership and storage transitions; 153 and 156 show the Grafana discrepancy. Production messages 199, 238, 241, 244, 253, 256, and 259 show the corresponding controller and storage checks. The [companion command index](/field-notes/rancher-retirement-investigation-command-index/) includes a local storage-map report that keeps unresolved joins visible.

- **Previous:** [The Cluster Was Unregistered. The Agents Were Still Running.](/posts/retiring-rancher-managed-kubernetes/management-cleanup/)
- **Next:** [Keep the API Until Its Last Useful Check](/posts/retiring-rancher-managed-kubernetes/shutdown-and-handoff/)
- [Series overview](/posts/retiring-rancher-managed-kubernetes/)
