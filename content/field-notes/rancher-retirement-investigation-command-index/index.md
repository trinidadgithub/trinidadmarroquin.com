+++
title = 'Rancher Retirement: An Investigation Command Index'
date = 2026-11-21T00:00:00-06:00
draft = false
description = 'Intent-indexed commands for Rancher/RKE2 retirement: direct access, admission failures, controller ownership, PVC-to-attachment mapping, endpoint state, and guest versus VM verification.'
tags = ['rancher', 'rke2', 'kubernetes', 'jq', 'csi', 'storage', 'operations', 'decommissioning']
categories = ['field-notes']
series = ['Retiring Rancher-Managed Kubernetes']
+++

Companion reference for [Retiring Rancher-Managed Kubernetes](/posts/retiring-rancher-managed-kubernetes/).

These recipes are sanitized adaptations of the investigation in *Rancher Cluster Decommission Guide*. Each answers one question. They query state or analyze saved evidence; they are not an automated cluster-deletion sequence. The historical mutating procedure remains in the [phase-oriented runbook](https://github.com/trinidadgithub/trinidadmarroquin.com/blob/main/notes/rancher-rke2-decommissioning-runbook.md).

## Downloads

**[Download storage-map.jq](/field-notes/rancher-retirement-investigation-command-index/storage-map.jq)** — a local `jq` report joining saved Pods, PVCs, PVs, and VolumeAttachments. It preserves failed/deleting consumers, missing mappings, and unknown attachment status.

If your browser displays the script as text, use **Save Link As** to save it as `storage-map.jq`. See [Recipe 7](#7-build-the-storage-map) for the four required input files and invocation.

## Quick Index by Intent

| Question | Recipe | Result |
| --- | --- | --- |
| Am I using the downstream API directly? | [1. Verify the access path](#1-verify-the-access-path) | Selected endpoint and live identity check |
| What does Rancher actually own? | [2. Inspect management metadata](#2-inspect-management-metadata) | Provisioning and management evidence |
| Why has cleanup not created a pod? | [3. Inspect cleanup admission](#3-inspect-cleanup-admission) | Job events, namespace policy, pod template |
| Did cleanup finish and was policy restored? | [4. Check downstream completion](#4-check-downstream-completion) | Namespaces, agents, direct API and label state |
| What might recreate a workload? | [5. Follow desired-state ownership](#5-follow-desired-state-ownership) | Owners, managers, replica state and upgrade activity |
| Will scale-down retain the claims? | [6. Separate retention policies](#6-separate-retention-policies) | StatefulSet policy and PV reclaim policy |
| Which pods, claims, nodes and attachments are related? | [7. Build the storage map](#7-build-the-storage-map) | Downloadable local `jq` report |
| What remains stuck in deletion? | [8. Preserve storage exceptions](#8-preserve-storage-exceptions) | Timestamps, finalizers, attachment state and errors |
| Do old VIPs still have backends? | [9. Inspect endpoint state](#9-inspect-endpoint-state) | Service addresses and ready/unknown endpoint counts |
| Has recovery material actually left the cluster? | [10. Verify transfer evidence](#10-verify-transfer-evidence) | Snapshot identity, permissions and digest checks |
| Is the guest runtime stopped? | [11. Inspect the guest](#11-inspect-the-guest) | Services, processes, mounts and storage sessions |
| Is every VM accounted for after shutdown? | [12. Verify the external inventory](#12-verify-the-external-inventory) | Hypervisor evidence and owner handoff |

## Shared Setup and Evidence Capture

Use Bash, `kubectl`, and `jq` 1.6 or later. Keep the management context distinct from the retiring cluster. All examples use generic names; replace them with individually verified targets.

```bash
DIRECT_KCFG="$HOME/.kube/cluster-a-direct.yaml"
DIRECT_CTX='cluster-a-direct'
MGMT_CTX='rancher-management'
RANCHER_ID='replace-with-verified-management-id'
PROVISIONING_NS='fleet-default'
PROVISIONING_NAME='cluster-a'
NS='observability'

set -o pipefail
umask 077
k() { kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" "$@"; }
```

Use one evidence directory per cluster and collection session. Kubeconfigs, tokens and snapshots are restricted recovery material; even ordinary resource exports may contain sensitive workload configuration. Keep the raw evidence outside the website repository and publish only reviewed excerpts.

For a capture, require both a successful query and a valid List before promoting the file:

```bash
mkdir retirement-evidence-cluster-a
cd retirement-evidence-cluster-a

if k get pods -A -o json > pods.json.partial 2> pods.stderr \
   && jq -e '(.items | type) == "array"' pods.json.partial > /dev/null; then
    mv pods.json.partial pods.json
else
    printf '%s\n' 'Pod capture failed; inspect partial output and stderr.' >&2
fi
```

Run subsequent analysis only after capture succeeds. Do not hide API failures with `|| true` and interpret an empty filtered table as “nothing remains.” Captures are sequential observations, not an atomic cross-resource transaction; record their collection times and the target API identity.

## 1. Verify the Access Path

**Intent:** Prove access survives removal of Rancher's proxy. This reads local kubeconfig selection and queries the downstream cluster.

```bash
k config view --minify -o jsonpath='{.clusters[0].cluster.server}{"\n"}'
k cluster-info
k get nodes -o wide
```

The selected server must be the intended downstream endpoint, not a management-proxy URL. Verify TLS normally and match the returned node identities to the retirement inventory. Do not print a raw kubeconfig containing private keys into a shared log. If obtaining an RKE2 kubeconfig, use an approved restricted transfer and an endpoint covered by the server certificate; changing a URL alone does not establish usable direct access.

UAT passed this test before unregistration. Production established it afterward. The reusable order is the former.

## 2. Inspect Management Metadata

**Intent:** Investigate cluster lifecycle ownership from the management cluster, without conflating an access setting with imported status.

```bash
kubectl --context "$MGMT_CTX" get clusters.management.cattle.io "$RANCHER_ID" -o json |
  jq '{name: .metadata.name, display_name: .spec.displayName,
       owners: .metadata.ownerReferences,
       local_cluster_auth_endpoint: .spec.localClusterAuthEndpoint}'

kubectl --context "$MGMT_CTX" -n "$PROVISIONING_NS" \
  get clusters.provisioning.cattle.io "$PROVISIONING_NAME" -o json |
  jq '{name: .metadata.name, kubernetes_version: .spec.kubernetesVersion,
       machine_pools: .spec.rkeConfig.machinePools,
       machine_global_config: .spec.rkeConfig.machineGlobalConfig}'
```

Resource locations and schemas depend on Rancher version and cluster type. Correlate this with installation history, infrastructure declarations, and node-level agent state. A provisioning object alone does not establish VM ownership. `localClusterAuthEndpoint` is not an imported-cluster flag. One inactive system agent is supporting evidence about that node, not a complete provisioning audit.

## 3. Inspect Cleanup Admission

**Intent:** Distinguish no pod, waiting container, and a running cleanup. Replace the Job name with the observed one.

```bash
CLEANUP_NS='default'
CLEANUP_JOB='replace-with-observed-cattle-cleanup-job'
k -n "$CLEANUP_NS" get jobs,pods
k -n "$CLEANUP_NS" describe job "$CLEANUP_JOB"
k -n "$CLEANUP_NS" get events --sort-by=.metadata.creationTimestamp
k -n "$CLEANUP_NS" get job "$CLEANUP_JOB" -o json |
  jq '{conditions: .status.conditions, pod_template: .spec.template.spec}'
k get namespace "$CLEANUP_NS" -o json |
  jq '{name: .metadata.name,
       pod_security_labels: ((.metadata.labels // {}) |
         with_entries(select(.key | startswith("pod-security.kubernetes.io/"))))}'
```

The captured `FailedCreate` events named `restricted:latest` and specific missing container security settings. An empty label report did not prove the request was unrestricted. Inspect effective admission configuration as well as namespace labels.

Only after a pod exists and its container starts can logs explain its execution:

```bash
k -n "$CLEANUP_NS" logs "job/$CLEANUP_JOB" --timestamps --tail=100
```

Review pod-template output before sharing it; environment fields can expose configuration. A Job admitted into the API is not necessarily an admitted pod.

## 4. Check Downstream Completion

**Intent:** Verify target resources, continued API access, and policy restoration independently.

```bash
k get namespaces cattle-system cattle-fleet-system cattle-impersonation-system \
  --ignore-not-found
k get pods,jobs -A -o json |
  jq -r '.items[] | select(.metadata.name |
    test("cattle-cleanup|cattle-cluster-agent|fleet-agent")) |
    [.kind, .metadata.namespace, .metadata.name] | @tsv'
k get nodes
k get namespace "$CLEANUP_NS" -o json |
  jq '.metadata.labels["pod-security.kubernetes.io/enforce"]'
```

Use the actual component inventory for the installed version; a name regex is a search aid, not exhaustive proof. Compare enforcement labels with their recorded original state. The historical override was removed because the original label was absent. Other original values require exact restoration. A `privileged` namespace enforcement label affects the whole namespace's PSA enforcement, not only the cleanup pod.

The cleanup Job may remove itself. Its `NotFound` result alone does not establish successful target cleanup; the namespace and agent checks provide additional evidence.

## 5. Follow Desired-State Ownership

**Intent:** Identify the declaration and controllers capable of restoring replicas.

```bash
k -n "$NS" get deployments,statefulsets -o json |
  jq -r '.items[] | [.kind, .metadata.name,
    (.spec.replicas // 1), (.status.readyReplicas // 0),
    .metadata.generation, (.status.observedGeneration // 0),
    ([.metadata.ownerReferences[]? | .kind + "/" + .name] | join(",")),
    (.metadata.labels["app.kubernetes.io/managed-by"] // "")] | @tsv'

k -n "$NS" get deployment grafana -o json --show-managed-fields |
  jq '{desired: .spec.replicas, owners: .metadata.ownerReferences,
       managers: [.metadata.managedFields[]? | {manager, operation, time}]}'

k -n system-upgrade get deployments,plans,jobs,pods
```

Replace `grafana` and namespaces with observed resources. Query the owning custom resource if its type exists in the installation, for example `k -n "$NS" get prometheus,alertmanager`. Preserve desired and observed state: zero ready replicas can still mean desired replicas are one. An owner reference or field manager is not conclusive historical writer attribution; use audit events or controller logs where needed.

## 6. Separate Retention Policies

**Intent:** Check StatefulSet PVC handling and PV backend reclaim behavior as different policies.

```bash
k get statefulsets -A -o json |
  jq -r '.items[] | [.metadata.namespace, .metadata.name,
    (.spec.persistentVolumeClaimRetentionPolicy.whenScaled // "Retain"),
    (.spec.persistentVolumeClaimRetentionPolicy.whenDeleted // "Retain")] | @tsv'
k get pv -o json |
  jq -r '.items[] | [.metadata.name, .spec.persistentVolumeReclaimPolicy,
    (.spec.claimRef.namespace // ""), (.spec.claimRef.name // ""),
    (.spec.csi.driver // ""), (.spec.csi.volumeHandle // "")] | @tsv'
```

The first report displays the documented `Retain` default when the optional policy is absent. It does not inspect every other deletion mechanism. Neither policy report proves application backup or authorizes claim deletion.

## 7. Build the Storage Map

**Intent:** Join current Pod references to namespaced PVCs, bound PV names and VolumeAttachments without excluding failed or deleting pods.

Capture `pods.json`, `pvcs.json`, `pvs.json`, and `attachments.json` using the validated capture pattern above and these respective read-only queries:

```bash
k get pods -A -o json
k get pvc -A -o json
k get pv -o json
k get volumeattachments.storage.k8s.io -o json
```

Save each response to its named file; the commands above intentionally show the query shapes rather than overwriting an earlier capture. Download [storage-map.jq](storage-map.jq) into the evidence directory, then analyze locally:

```bash
jq -n \
  --slurpfile pods pods.json \
  --slurpfile pvcs pvcs.json \
  --slurpfile pvs pvs.json \
  --slurpfile attachments attachments.json \
  -f storage-map.jq > storage-map.json

jq '.counts, .claims_without_listed_pv,
  .pod_claims_without_listed_pvc, .attachments_without_listed_pv' storage-map.json
jq '.volumes[] | select(.attachments | length > 0)' storage-map.json
```

This is a new local report adapted from the transcript's separate queries, not a historical script. It requires one List document per input and checks basic item names and namespaces. It reports every listed PV, including those without consumers or attachments, and preserves unresolved joins separately.

Consumer matching uses namespace plus claim name. PVC-to-PV matching uses `.spec.volumeName`; PV claim references and UIDs are retained for comparison, not automatically declared consistent. Name reuse, sequential capture timing, inline/ephemeral volumes and backend identity require additional interpretation. A missing `status.attached` remains JSON `null`, distinct from `false`. No array ACL, iSCSI-session state or disposal decision is inferred.

## 8. Preserve Storage Exceptions

**Intent:** Explain a stuck resource using its own lifecycle fields rather than deleting its symptoms.

```bash
k -n default get pod test-pod-a -o json |
  jq '{name: .metadata.name, phase: .status.phase, node: .spec.nodeName,
       owners: .metadata.ownerReferences, deleting: .metadata.deletionTimestamp,
       finalizers: .metadata.finalizers}'
k -n default get pvc test-claim-a -o json |
  jq '{name: .metadata.name, pv: .spec.volumeName, phase: .status.phase,
       deleting: .metadata.deletionTimestamp, finalizers: .metadata.finalizers}'
k get volumeattachments.storage.k8s.io -o json |
  jq '.items[] | {name: .metadata.name, node: .spec.nodeName,
       pv: .spec.source.persistentVolumeName, attached: .status.attached,
       deleting: .metadata.deletionTimestamp, detach_error: .status.detachError}'
```

Use observed names. The production investigation showed failed pods with old deletion timestamps, Terminating claims, and three attachments still reporting `true`. `detachError: null` did not mean detachment had completed. Preserve a per-volume handoff with the guest, PV/claim, CSI handle, array identity, unresolved state, and responsible owner.

## 9. Inspect Endpoint State

**Intent:** Identify service addresses and count what EndpointSlices actually report.

```bash
k get services -A -o json |
  jq -r '.items[] | select(.spec.type == "LoadBalancer") |
    [.metadata.namespace, .metadata.name,
     ([.status.loadBalancer.ingress[]? | (.ip // .hostname)] | join(","))] | @tsv'

SERVICE='legacy-ingress'
k -n "$NS" get endpointslices.discovery.k8s.io \
  -l "kubernetes.io/service-name=$SERVICE" -o json |
  jq '{slices: (.items | length),
    endpoints: ([.items[].endpoints[]?] | length),
    explicitly_ready: ([.items[].endpoints[]? | select(.conditions.ready == true)] | length),
    readiness_unknown: ([.items[].endpoints[]? | select(.conditions.ready == null)] | length)}'
```

Unknown readiness is reported separately rather than silently called false. EndpointSlice counts are observations of endpoint entries, not unique clients or traffic measurements. An address may still be advertised after its backend disappears. DNS resolution, load-balancer routing and actual client usage need their own checks.

## 10. Verify Transfer Evidence

**Intent:** Identify snapshots and validate already-authorized recovery-material transfers.

On the selected etcd server, listing is read-only:

```bash
sudo rke2 etcd-snapshot ls
sudo sha256sum '/exact/path/to/selected-snapshot'
```

On the workstation, after approved transfer:

```bash
sha256sum '/restricted/backup/selected-snapshot'
stat -c '%n %s bytes %a permissions' '/restricted/backup/selected-snapshot'
```

Compare the source and destination digests; preserve the original RKE2 server token through the same restricted custody process. A matching digest proves transfer integrity, not a successful restore or application-volume backup. Use exact paths from the snapshot listing. An unprivileged shell may fail to expand a wildcard inside a root-only directory before `sudo` runs.

## 11. Inspect the Guest

**Intent:** Check service, process and mount state on the exact retiring node. These queries do not stop services.

```bash
hostname
systemctl is-active rke2-agent
systemctl is-enabled rke2-agent
sudo systemctl status rke2-agent --no-pager -l
sudo journalctl -u rke2-agent --since '15 minutes ago' --no-pager -n 80
sudo ps -eo pid,comm,args
findmnt -rn -o SOURCE,TARGET,FSTYPE
sudo iscsiadm -m session
sudo multipath -ll
```

Use `rke2-server` for a server-role node and storage tools only where applicable. A nonzero status from `is-active` can represent an inactive or failed unit; distinguish that from a query error. A process search can match its own command line. Inspect process identity and expected runtime paths rather than treating every text match as a workload.

Read host sessions and mounts against known CSI/backend mappings. The complete export does not show those checks resolving production's three attachment exceptions. `rke2-killall.sh`, service stop/disable, and power-off are mutating operations discussed in the series and runbook; they are not steps in this inspection recipe.

## 12. Verify the External Inventory

**Intent:** Check all enumerated VMs after API access has ended, including non-node API load balancers.

With `govc` configured for the intended vCenter and datacenter:

```bash
govc vm.info '/Datacenter/vm/retired-cluster/worker-a'
govc vm.info '/Datacenter/vm/retired-cluster/api-lb-a'
```

Repeat against the exact VM manifest. Record reported power state and immutable IDs where available. If a deleted VM is not found, a complete inventory/audit in the correct scope is needed to distinguish deletion from a wrong path or permissions problem. Kubernetes `NotReady`, a lost SSH session, and guest shutdown output are not substitutes for this inventory.

Keep separate dispositions for VMs, backend volumes, API and application VIPs, DNS, NetBox/IP assignments, monitoring, and recovery-material custody. The source's final VM-deletion confirmation is an operator report; it does not independently resolve each of those records.

## Sources and Series Links

- [Series overview and message-level evidence map](/posts/retiring-rancher-managed-kubernetes/)
- [Part 1: Shutting Down Kubernetes Is Not the Same as Decommissioning It](/field-notes/rancher-rke2-decommissioning-field-note/)
- [Part 2: Management cleanup](/posts/retiring-rancher-managed-kubernetes/management-cleanup/)
- [Part 3: Reconciliation and storage](/posts/retiring-rancher-managed-kubernetes/reconciliation-and-storage/)
- [Part 4: Shutdown and handoff](/posts/retiring-rancher-managed-kubernetes/shutdown-and-handoff/)
- [RKE2 backup and restore](https://docs.rke2.io/datastore/backup_restore)
- [Kubernetes Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
- [Kubernetes StatefulSet PVC retention](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#persistentvolumeclaim-retention)
- **After shutdown:** [Nimble storage investigation command index](/field-notes/nimble-storage-investigation-command-index/)
