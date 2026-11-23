+++
title = 'Keep the API Until Its Last Useful Check'
date = 2026-11-21T00:00:00-06:00
draft = false
description = 'Part 4 of Retiring Rancher-Managed Kubernetes: recovery material, endpoint retirement, runtime verification, etcd quorum, and post-shutdown ownership.'
tags = ['rancher', 'rke2', 'kubernetes', 'etcd', 'vsphere', 'operations', 'decommissioning']
categories = ['posts']
series = ['Retiring Rancher-Managed Kubernetes']
+++

Part 4 of [Retiring Rancher-Managed Kubernetes](/posts/retiring-rancher-managed-kubernetes/).

The shutdown sequence was not simply a list of machines. It was a list of observation and reconciliation paths that would disappear as each machine stopped.

Workers could stop while the API still showed node and storage state. The dedicated API servers could stop after the last Kubernetes checks. Dedicated etcd members came last. API load-balancer VMs needed their own entries because they were never part of the Kubernetes node list.

The recurring question was: what do I still need this component to tell me or finish doing?

## Preserve Recovery Material Before Removing Its Source

Both environments had a final RKE2 etcd snapshot taken before shutdown. The record shows matching source and workstation snapshot SHA-256 digests. Server tokens were copied too; production also had matching token digests.

Those checks established transfer integrity. They did not demonstrate a restore rehearsal or prove that the files reached approved long-term custody. An etcd snapshot preserves Kubernetes state, not the contents of application persistent volumes. RKE2's original server token is also recovery material because it protects bootstrap data stored in the datastore.

One small shell detail was consequential: a wildcard under a root-only directory did not expand in the unprivileged caller's shell merely because the command began with `sudo`. An exact snapshot filename worked. The snapshot had been saved; the failed glob had initially made its transfer look broken.

The better evidence record identifies the exact snapshot, original token, RKE2 version, destination, permissions, transfer check, and restoration procedure. Keep those artifacts outside the VMs scheduled for deletion. Publishing their contents is not part of preserving the engineering lesson.

## Separate Endpoint Retirement from Client Migration

The clusters still had four LoadBalancer services with ready backends: ingress services and a metrics proxy. EndpointSlices showed the services could route to healthy pods. That was not a measurement of actual client traffic.

After approval to retire the legacy production VIP backends, the relevant Deployments were scaled to zero. Subsequent EndpointSlice queries counted zero endpoints explicitly reporting `ready=true` for each service.

That established a backend-state observation. It did not establish that all clients had migrated, that DNS records had changed, or that the VIP stopped being advertised. LoadBalancer Service objects and address advertisement have lifecycles beyond a backend Deployment's replica count.

The same distinction applies to the API endpoint. Retire it only after no remaining operator or controller step depends on it, and inventory its dedicated VMs separately from application ingress services.

## Failed Service State Was Not a Process Inventory

The first UAT worker was a canary. After stopping and disabling `rke2-agent`, systemd reported `failed`, and the unit output still showed containerd shim processes. The service result and the remaining runtime were two separate observations.

The operator used the installed `rke2-killall.sh` cleanup script, then inspected processes, mounts, and multipath output. The recorded process search also matched its own `sudo pgrep` command lines. Those matches had to be read as command text, not mistaken for surviving application processes.

`rke2-killall.sh` forcefully cleans up runtime and networking/mount state; it is not graceful application shutdown. The application and storage checks belong before that operation. Stopping a service, disabling its next-boot activation, terminating residual runtime, and powering off the VM each answer different questions.

Kubernetes later showed workers and monitors as `NotReady`. That meant they were no longer reporting readiness to the API. Some pod records still said `Running`, while controllers placed replacement pods on remaining nodes. Neither API status was a direct hypervisor power-state observation.

## Plan the Last Useful Query

These environments separated roles across VMs. Their dependency sequence can be expressed as checkpoints:

| Checkpoint | Keep available | Last useful evidence |
| --- | --- | --- |
| Workload quiescence | Operators needed for shutdown, CSI, network, API, etcd | Desired/observed replicas, consumers, attachments and exceptions |
| Worker and monitor shutdown | API servers, etcd, required access paths | Node transitions plus independent guest/hypervisor checks |
| Dedicated API-server shutdown | Direct access through a surviving API server until final query | Final Pods/PVs/attachments/node inventory |
| Dedicated etcd shutdown | Required members until datastore work is complete | Snapshot custody and explicit decision to end quorum |
| Post-shutdown handoff | Hypervisor, array, DNS and inventory systems | Per-resource disposition outside Kubernetes |

This is not a universal sequence for clusters with combined control-plane/etcd roles. Adapt it to the actual services and dependencies. Even in these dedicated-role environments, keep the API server addressed by the direct kubeconfig until its final planned check, or deliberately move and retest that endpoint.

Three etcd members require two for quorum; five require three. Once the retirement deliberately crosses below a majority, the plan must not depend on continued datastore progress. After the API stops, `kubectl` is no longer the verification interface. Use the hypervisor and storage management systems instead.

Crossing that point is not a recipe for automatic disaster recovery. A later recovery decision needs its own reviewed procedure and may use preserved snapshots and tokens; it is not a casual partial restart.

## Finish the VM Inventory, Then Hand Off the Remaining Owners

UAT's 19-node count did not include its two API load-balancer VMs. A shutdown checklist derived only from `kubectl get nodes` would have omitted them.

The operator reported all UAT nodes shut down, then proceeded with production to unblock virtualization work. Production's later reports covered workers and monitors, then masters and load balancers. The complete export adds the final confirmation: all five production etcd nodes were powered off and the remaining VMs deleted. It explicitly left Nimble storage cleanup as the next chapter.

This is stronger closure evidence than the earlier incomplete transcript, but still an operator report. The export does not reproduce a complete final vCenter power/deletion inventory, the array-side resolution of the three storage exceptions, or proof of DNS and NetBox cleanup. The referenced screenshots are not embedded as readable images in this JSON source.

The closing record should therefore distinguish:

- Shutdown and VM deletion reported by the operator.
- Runtime, controller, and storage observations captured before shutdown.
- Storage exceptions transferred for array-side investigation.
- DNS, NetBox, VIP and monitoring records requiring their own disposition.
- Snapshot and token custody retained independently of the retired VMs.

Both legacy environments were reported to have no Terraform state. That fact removed a planned UAT import task; it did not authorize applying the same assumption to another cluster. Establish each environment's actual source of truth before editing inventory or infrastructure declarations.

The cluster could stop before every asset was reclaimed, provided the remaining work remained identifiable. The next investigation moved to the array: [The Cluster Was Gone. The Storage Wasn't.](/field-notes/the-cluster-was-gone-the-storage-wasnt/).

## Sources and Reading Order

Recovery observations appear in user messages 39, 43, 187, 190, and 196; guest runtime checks in 125, 130, 135, and 159; endpoint checks in 235; final production reports in 262, 265, and 268. The [command index](/field-notes/rancher-retirement-investigation-command-index/) provides the corresponding read-only investigation patterns.

[RKE2 backup and restore documentation](https://docs.rke2.io/datastore/backup_restore) describes the embedded-etcd snapshot commands and original server-token requirement when restoring to new hosts.

- **Previous:** [Zero Replicas Is Not a Shutdown Plan](/posts/retiring-rancher-managed-kubernetes/reconciliation-and-storage/)
- [Series overview](/posts/retiring-rancher-managed-kubernetes/)
- **Continue with the storage series:** [Decommissioning Beyond Kubernetes](/posts/decommissioning-beyond-kubernetes/)
