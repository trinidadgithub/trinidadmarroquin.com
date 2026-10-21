+++
title = 'Shutting Down Kubernetes Is Not the Same as Decommissioning It'
date = 2026-10-20T00:00:00-05:00
draft = false
description = 'What two Rancher-managed RKE2 retirements taught about management cleanup, recovery evidence, storage detach, controllers, and the boundary between shutdown and reclamation.'
tags = ['rancher', 'rke2', 'kubernetes', 'decommissioning', 'storage', 'operations']
categories = ['field-notes']
+++

Powering off the nodes is a perfectly effective way to make a cluster unavailable. It is a poor definition of decommissioning.

Two independently installed RKE2 clusters, registered with Rancher and backed by vSphere VMs, were retired after replacement clusters were brought online. One was a larger former UAT environment with three dedicated etcd members; the other was a former production environment with five. The same operating principles applied to both, but the storage state did not. That difference is where a generic shutdown checklist would have become dangerous.

This account distinguishes command output and observed state from operator reports. The final shutdown of the production etcd servers is confirmed by the operator separately from the session PDF; the PDF ends with instructions for that step, not its execution output. The following is an operational analysis, not a claim that all physical resources have been reclaimed. A separate [decommissioning runbook](https://github.com/trinidadgithub/trinidadmarroquin.com/blob/main/notes/rancher-rke2-decommissioning-runbook.md) contains the reusable procedure and its stop gates.

## Find Out What Rancher Owns

Rancher's **Delete** action means different things for a registered cluster and one whose nodes Rancher provisioned. The management records for these clusters included provisioning `Cluster` resources, but the inspected specs did not define RKE2 machine pools or a managed Kubernetes version. On an inspected UAT etcd VM, `rancher-system-agent` was inactive while `rke2-server` was active. These findings supported the conclusion that Rancher managed access to independently installed RKE2 clusters; they were not, individually, proof of every node's lifecycle ownership.

That distinction determined whether removing the Rancher registration was a reasonable operation. It also exposed a dependency: the existing UAT kubeconfig addressed the Kubernetes API through Rancher's proxy. A direct RKE2 kubeconfig was tested against the downstream API before UAT was unregistered. All 19 nodes appeared Ready through that path. Production did not follow this order: direct access was established and tested *after* its Rancher entry was removed, when the proxy-based route was no longer suitable. The second path worked and returned 18 Ready nodes, but that timing made the runbook rule sharper: verify independent access before detaching Rancher.

## Preserve Recovery Material, Then Ask About Data

Both clusters had a final RKE2 etcd snapshot created before shutdown. In each case the recorded source and workstation snapshot SHA-256 digests matched. The server token was copied for both clusters; in production, its source and destination checksums also matched. These are meaningful checks on transfer integrity. They are not restore tests, and an etcd snapshot does not contain application data on persistent volumes. The session does not show a restore rehearsal or proof that recovery material reached approved long-term backup storage.

The storage inventory was the more important counterweight to the phrase “the workloads have migrated.” Many persistent volumes still existed and the listed CSI-backed PVs used a `Delete` reclaim policy. An unreferenced claim was not a disposable volume. Removing a namespace or claim could have triggered storage deletion; shutting down a VM did not require that deletion at all. Neither cluster's application-data retention decision is evidenced by a detailed owner-by-owner sign-off in the transcript. That remains a separate requirement before physical reclamation.

## An Absent Rancher Entry Was Not A Clean Cluster

After each cluster's management record disappeared, the downstream Rancher and Fleet agents remained. A `cattle-cleanup` Job existed, but its pod was rejected under `restricted:latest` Pod Security Admission. Job creation and cleanup completion were not the same observation.

The operator inspected Job events, observed `FailedCreate`, and used a temporary namespace enforcement override so the cleanup pod could be admitted. The exception applied to the **entire** `default` namespace, not just to Rancher. After the agents, namespaces, and cleanup Job disappeared, the temporary enforcement label was removed and its absence checked. A missing cleanup Job alone would not have been sufficient evidence: it could have deleted itself before completing, or failed for another reason. Here the downstream resource checks supplied the missing proof.

The operating lesson is wider than this Rancher version. Any management tool that cleans up through an in-cluster controller needs the cluster and its admission path alive long enough to finish. If a security policy blocks that controller, inspect the admission event and the scope of any exception before changing it. Do not substitute an indiscriminate namespace deletion for a failed cleanup Job.

## Stop Reconciliation At The Owning Layer

The System Upgrade Controller was observed with upgrade Plans in both environments and scaled to zero with `0/0` confirmed. A failed upgrade Job was visible in UAT; production's inspected plan list showed no active Job. Stopping the controller reduced the chance of a node upgrade interrupting retirement, but a GitOps or other upstream reconciler could have restored its replica count. The session does not establish a durable freeze of every external reconciler.

Seven stateful observability workloads in each cluster had `Retain` StatefulSet PVC policies. Four could be scaled as StatefulSets in the recorded procedure. Prometheus and Alertmanager StatefulSets were owned by an operator, so their *custom resources* were patched to request zero replicas. All seven StatefulSets were then observed at `0/0` in each cluster.

Grafana supplied the warning against declaring victory from a single replica check. After a deployment was scaled down, its desired replicas later returned to one. The UAT investigation found a Grafana owner reference even though the corresponding custom resource was not found; that metadata did not prove which controller had restored the value. The Grafana operator Deployment had been scaled to zero, the Grafana Deployment was scaled again, and `0/0` was observed. Production similarly required a second scale-down before a `0/0` result was recorded. When replicas return, inspect the owner and the declared state; a green command exit is not lasting quiescence.

## Storage Was The Difference Between The Clusters

UAT began with seven CSI `VolumeAttachment` objects tied to those stateful pods. After the seven workloads reached zero replicas, the attachment inventory was empty and the PVCs remained Bound. This verified that Kubernetes no longer reported those attachments. It did **not** independently verify array-side host mappings or authorize deleting the backed volumes.

Production began with ten attached volumes: seven associated with the observability workloads and three associated with failed iSCSI test pods on monitoring nodes. Scaling the seven StatefulSets released their seven attachments, leaving **three** reporting `attached=true`. The pods had deletion timestamps roughly two months old; their PVCs were already `Terminating`. A later pod delete request did not clear the attachments in the observed output. The remaining condition was treated as a documented storage exception, not silently converted into a successful detach. The source does not show a successful array-side check or the three attachments disappearing before the monitor shutdown was reported.

This was a consequential choice. Forcing removal of a `VolumeAttachment` or a PVC finalizer might have accelerated the appearance of completion while making the storage record less trustworthy, especially with `Delete` reclaim policies. Proceeding with an exception requires named storage ownership, an assessment of guest mounts and sessions, and a later array-side reconciliation. The transcript recommended local iSCSI and multipath checks for the three monitors, but does not show their results. Those checks must not be retroactively marked complete.

## Endpoint State Is Not Traffic Evidence

Both clusters still exposed LoadBalancer services backed by ingress and a metrics proxy. EndpointSlices showed healthy backends before shutdown. That showed the services *could* receive traffic; it did not show whether anyone still used their VIPs. In production, the operator explicitly approved turning off the legacy VIP backends. The transcript does not contain independent traffic measurements or DNS-resolution evidence establishing that no clients remained.

The ingress and proxy Deployments were scaled to zero, and their four services were checked for zero ready endpoints. This is stronger evidence than a successful scale command. It is also narrower than saying the VIPs were deallocated: a LoadBalancer object or address advertiser can outlive its backend. DNS, load-balancer routing, NetBox, and monitoring inventory belonged to a later cleanup phase.

## Shut Down In Dependency Order

The sequence used for the UAT cluster kept the Kubernetes API and CSI machinery available while applications and storage attachments were addressed: workers and monitoring nodes first, separate control-plane nodes after that, dedicated etcd members last. The master serving the direct kubeconfig was deliberately kept until the other masters were done. Two API load-balancer VMs were discovered outside the 19-node Kubernetes count. That changed the inventory from “19 nodes” to a larger VM retirement scope; Kubernetes node readiness alone could never prove those VMs were powered off.

On the first UAT worker, stopping `rke2-agent` left systemd reporting `failed` and containerd shims still running. The operator ran `rke2-killall.sh`, then checked processes, mounts, and multipath output. That script forcefully cleans up RKE2-managed processes and mounts; it is not an application shutdown method. It belongs after stateful workloads have stopped, not at the start of a decommission. The canary was also reported powered off in a vCenter screenshot. Later `NotReady` node entries showed the workers and monitors stopped reporting to Kubernetes; `NotReady` is not a VM power-state check. Some pod records still showed `Running` on retired nodes, while other controllers scheduled replacement pods on surviving nodes.

UAT's operator subsequently reported all nodes shut down, and the conversation treated the API load balancers as shut down too. The PDF does not include a per-VM final power-state inventory for all of them. For production, the operator reported workers and monitors powered off and later reported masters and API load balancers powered off. **The operator has separately confirmed that all production etcd servers were also shut down**, but their execution output and final vCenter power-state inventory are not in the PDF.

## The Boundary That Matters

Rancher registration removal, workload quiescence, CSI detachment, RKE2 service shutdown, VM power-off, and permanent infrastructure deletion are different states. Both cluster retirements reached reported node shutdown; production's three legacy storage attachments and the outstanding inventory work make it especially important not to call that verified storage reclamation.

The shutdown unblocked the next owners; it did not do their work for them. The remaining order was to inventory the legacy PVC-backed storage with the storage team, establish ownership and deletion approval, then remove powered-off VMs after the agreed retention period without touching shared storage. NetBox IP assignments and DNS records, monitoring targets and alerts, and the decommission record came afterward. A planned Terraform import for the former UAT cluster was no longer needed; the record does not show that its task was actually closed. The operator reported that neither retired cluster had Terraform state, a fact to recheck independently for any future retirement.

After Kubernetes goes offline, its CSI driver cannot complete the normal PVC/PV deletion workflow. Remaining backend volumes and any stale host mappings must instead be reconciled through the storage management interfaces, using the pre-shutdown PV-to-claim inventory. Keep the former UAT and production inventories separate; an approval for one cluster does not authorize deleting a similarly named volume in the other.

The reusable method is to keep the next dependency alive until its final useful check is done, and to give each irreversible step its own evidence. A snapshot checksum is not an application backup. A `0/0` Deployment is not proof of no traffic. `NotReady` is not `poweredOff`. And a powered-off VM can still have a storage volume, DNS record, or inventory entry with somebody's name on it.
