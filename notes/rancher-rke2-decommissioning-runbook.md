# Rancher-Managed RKE2 Cluster Decommissioning Runbook

This runbook is for an approved retirement of an RKE2 cluster registered with Rancher. It separates **operational shutdown** from **deletion/reclamation**. It is an operator procedure, not a script; no command is safe merely because it appears here. The accompanying [field note](../content/field-notes/rancher-rke2-decommissioning-field-note.md) explains the evidence behind the gates.

## Scope and execution record

Complete a separate record for each cluster. Record the command, time, operator, redacted output location, decision, and approver at every gate. Do not paste kubeconfigs, RKE2 server tokens, snapshots, Secret bodies, or customer identifiers into tickets or this repository.

| Field | Fill before starting |
| --- | --- |
| Change / approval ID; operator; maintenance window | `...` |
| Retiring cluster; replacement cluster; application owner approval | `...` |
| Rancher management context and cluster ID | `MGMT_CTX`, `RANCHER_ID` |
| Provisioning namespace/name and ownership classification | `PROVISIONING_NS`, `PROVISIONING_NAME` |
| Downstream direct kubeconfig and explicit context | `DIRECT_KCFG`, `DIRECT_CTX` |
| Exact node-to-VM list, roles, hosts, API endpoint kept until last | `...` |
| Stateful workload, PVC/PV, CSI driver, VIP, and external-dependency inventory | `...` |
| Storage exceptions, owners, deadlines, and cleanup tickets | `...` |
| Backup location, retention period, and rollback decision point | `...` |

Example variables below are **placeholders**, not values for a particular site. Validate `kubectl config get-contexts` and `kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" config view --minify` before relying on either path. Prefer a **direct** downstream API endpoint that remains available after Rancher unregisters the cluster. Use a different credential for the management context; never confuse the management cluster with the retiring one.

```bash
MGMT_CTX='<management-context>'
RANCHER_ID='<verified-rancher-cluster-id>'
PROVISIONING_NS='<rancher-provisioning-namespace>'
PROVISIONING_NAME='<rancher-provisioning-resource-name>'
DIRECT_KCFG='<path-to-restricted-downstream-kubeconfig>'
DIRECT_CTX='<verified-direct-context>'
```

In this runbook, `$DIRECT_CTX` must refer to an entry **in** `$DIRECT_KCFG`, not a similarly named Rancher proxy context. Inspect its server URL and certificate validity without printing client keys. Every mutating example is **manual and conditional**; copy only after its phase's go/no-go decision. If a resource type, role layout, or backend differs, adapt the procedure and record why. Avoid loops over unknown names.

## Phase 1 — Assessment

**Purpose:** Establish what Rancher owns, what the cluster still serves, and what will remain after power-off. Rancher's Delete action on an imported/registered cluster is not equivalent to deletion of a Rancher-provisioned cluster.

**Preconditions:** Named change owner and target; confirmation that replacement services exist; access to the Rancher management cluster and downstream API; inventory of all VM and non-node components. No mutation in this phase.

**Commands (read-only examples):**

```bash
kubectl --context "$MGMT_CTX" get clusters.management.cattle.io "$RANCHER_ID" -o json \
  | jq '{name:.metadata.name,displayName:.spec.displayName,provider:.metadata.labels["provider.cattle.io"]}'
kubectl --context "$MGMT_CTX" -n "$PROVISIONING_NS" \
  get clusters.provisioning.cattle.io "$PROVISIONING_NAME" -o json \
  | jq '{name:.metadata.name,kubernetesVersion:.spec.kubernetesVersion,
         rkeConfig:.spec.rkeConfig,localClusterAuthEndpoint:.spec.localClusterAuthEndpoint}'
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" cluster-info
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get nodes -o wide
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get deploy,sts,ds,jobs,pods -A
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get pdb -A
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get pvc -A
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get pv -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,STORAGECLASS:.spec.storageClassName
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get volumeattachments.storage.k8s.io -o wide
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get svc,ingress -A
```

Read the pod-to-PVC map rather than guessing from namespace or pod phase:

```bash
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get pods -A -o json |
  jq -r '.items[] | . as $pod | .spec.volumes[]?
    | select(.persistentVolumeClaim != null)
    | [$pod.metadata.namespace,$pod.metadata.name,$pod.status.phase,
       .persistentVolumeClaim.claimName,$pod.spec.nodeName] | @tsv'
```

**Expected results / validation:** The exact target matches Rancher's display name and management ID; direct API returns the intended nodes; the node/VM count includes dedicated API load balancers and other VMs *outside* Kubernetes; workloads, PDBs, PV reclaim policies, CSI attachments, ingress VIPs, DNS names, backup and external clients have owners. Inspect provisioning specs, node provisioning method, and any Rancher system agent: a provisioning resource by itself does **not** prove Rancher provisions VMs; `localClusterAuthEndpoint` is not an imported-cluster flag. Validate Rancher behavior for the actual cluster type before using its UI Delete action.

**STOP / NO-GO:** Ambiguous Rancher ownership; Rancher is the only usable API route; unexplained pods/PVCs/VIPs; shared replacement-cluster dependency; no application/data owner decision; missing VM or PDB inventory. A healthy replacement cluster and ready EndpointSlices do **not** prove the old VIP receives no client traffic.

**Recovery:** None needed; assessment is read-only. Resolve ownership and dependency gaps before setting a shutdown window.

## Phase 2 — Preflight and GO/NO-GO

**Purpose:** Preserve a recovery point and ensure controllers or admission policy will not subvert the sequence. etcd data is *not* application-volume data.

**Preconditions:** Phase 1 passed; restore-material custodian and independent backup destination identified; application and network owners approve service retirement; scope excludes replacement environments. Snapshot source must be an RKE2 server participating in the embedded etcd cluster.

**Commands:** Review namespaces, upgrades, StatefulSet retention and external endpoints before change:

```bash
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n system-upgrade get deployments,plans,jobs,pods
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  get sts -A -o json | jq -r '.items[] |
    [.metadata.namespace,.metadata.name,.spec.replicas,
     (.spec.persistentVolumeClaimRetentionPolicy.whenScaled // "Retain"),
     (.spec.persistentVolumeClaimRetentionPolicy.whenDeleted // "Retain")] | @tsv'
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  get svc -A -o json | jq -r '.items[] | select(.spec.type=="LoadBalancer") |
    [.metadata.namespace,.metadata.name,
     ([.status.loadBalancer.ingress[]? | (.ip // .hostname)] | join(","))] | @tsv'
```

For the **approved snapshot operation**, on an identified etcd VM:

```bash
SNAP_NAME='<unique-pre-decommission-name>'
sudo rke2 etcd-snapshot save --name "$SNAP_NAME"
sudo rke2 etcd-snapshot ls
```

Record the **exact** snapshot filename and path from the output. Transfer it and the RKE2 server token via an approved restricted channel to storage outside the retired VMs, then compare source and destination SHA-256 and verify restricted permissions. Do not publish either file or a kubeconfig. Avoid unprivileged shell wildcards against root-only snapshot directories: the recorded production attempt failed to expand a glob, while an exact filename worked. Record backup location and a restore plan. A matching checksum validates transport integrity, **not** recoverability; an application-data backup or explicit disposal approval is a separate gate.

Before any changes, record owning controllers (Prometheus/Alertmanager/Grafana custom resources, Helm/GitOps, upgrade Plans) and decide how to prevent replica restoration. A zero-replica System Upgrade Controller Deployment is one option **if** no running upgrade Jobs remain and its upstream owner will not restore it:

```bash
# Only after inspecting jobs, ownership and approval:
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n system-upgrade scale deployment/system-upgrade-controller --replicas=0
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n system-upgrade get deployments,plans,jobs,pods
```

**Expected results / validation:** Source/destination snapshot digests match; server token is independently secured; application backups or disposal decisions are recorded; upgrade controller remains `0/0` and no live upgrade Job can restart a node; direct API remains functional; exact VIP ownership and actual client-use evidence or owner sign-off are recorded. PDBs and termination grace periods are reviewed: do not assume a drain is necessary for permanent retirement, or bypass a blocking PDB without an application decision. Obtain a **GO** from application, storage, network, Rancher/platform, virtualization, and backup owners as applicable.

**STOP / NO-GO:** Missing/untested transfer, absent server token, pending data-retention decision, active upgrade/reconciliation, unknown CSI attachment or unapproved VIP, or direct API not tested. Do not treat a local snapshot or a `Retain` StatefulSet policy as a backup of application data.

**Recovery:** Restore disabled controllers from their recorded previous replica count *only while the cluster and its upstream definitions remain intact*. Backup checks are additive. Once Rancher is unregistered or API access is lost, recovery needs a separate owner-approved plan.

## Phase 3 — Workload and management shutdown

**Purpose:** Remove Rancher management while the API still works, stop application writers at their owner layer, and allow CSI to detach before stopping nodes. The ordering of Rancher detach versus the application scale-down can vary, but neither may deprive the other's controllers of a live API.

**Preconditions:** Phase 2 GO; independently installed/registered cluster classification verified; direct API path and backups available; application shutdown approved. If Rancher provisioned the nodes, **STOP** and use its provisioning-specific lifecycle plan instead of the following UI detach path.

**Commands and checkpoints:** For a verified registered cluster, the operator uses Rancher **Cluster Management → selected cluster → Delete** (confirm its displayed name and ID); this is **not** a generic `kubectl delete` instruction. From the management cluster verify the exact record is gone; from the still-live downstream cluster verify the cleanup *separately*:

```bash
kubectl --context "$MGMT_CTX" get clusters.management.cattle.io "$RANCHER_ID"
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  get ns cattle-system cattle-fleet-system cattle-impersonation-system --ignore-not-found
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get jobs,pods -A
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" get nodes
```

`NotFound` on the Rancher entry proves **unregistration**, not removal of downstream agents. In both source clusters a cleanup Job remained at `0/1` without a pod; `describe job` showed `FailedCreate` under `restricted:latest` Pod Security Admission. If this happens, inspect the exact Job and namespace policy before considering any exception:

```bash
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n default describe job '<observed-cattle-cleanup-job>'
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  get namespace default -o json | jq '.metadata.labels'
```

The historical workaround set `pod-security.kubernetes.io/enforce=privileged` on `default` and later removed it. This is a **namespace-wide** relaxation, not a pod-scoped exception. It requires a separate time-boxed security decision, recorded original labels, control of other pod creation during the window, and immediate restoration to the *original* state. Do not apply it merely because cleanup is slow; act only on an observed PSA denial. Verify cleanup by disappearance of agents/namespaces and a responsive direct API, **not** by the cleanup Job disappearing alone (it may remove itself). If the original label was absent, restore its absence and re-read it; if the original had another value, restore that exact value rather than blindly removing it.

With workload owners present, stop writes and jobs using application-specific procedures. Map **Pod → PVC → PV → VolumeAttachment → backend owner**. Confirm StatefulSet `whenScaled/whenDeleted` retention before changing replicas. For a directly owned StatefulSet, a targeted example is:

```bash
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n '<namespace>' scale statefulset '<approved-name>' --replicas=0
```

For operator-owned Prometheus/Alertmanager, change the **owning custom resource**, not just the generated StatefulSet (only if this resource type and field exist in that installation):

```bash
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n '<namespace>' patch prometheus '<approved-name>' --type=merge -p '{"spec":{"replicas":0}}'
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n '<namespace>' patch alertmanager '<approved-name>' --type=merge -p '{"spec":{"replicas":0}}'
```

Do not apply these examples to databases without an approved shutdown and backup plan. Re-check actual replicas, Pods and PVCs, and the **specific** CSI attachment records; keep the CSI driver, API and needed network services running until normal detachment finishes. A bound PVC can remain after attachment disappears. Neither condition alone proves array mappings are gone. For a stuck, preexisting attachment: inspect pod/PVC deletion timestamps, finalizers, guest mount/iSCSI/multipath state and storage-array mappings. Do **not** force-delete Pods/VolumeAttachments, remove finalizers or delete PVCs simply to make the dashboard empty. Continue only on a signed, specific exception with a storage owner and follow-up record; otherwise STOP.

Once storage consumers are quiescent, retire approved ingress/proxy Deployments and check both replicas **and** ready EndpointSlice backends. Example (replace placeholders only after identifying the workload and its owner):

```bash
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n '<namespace>' scale deployment '<approved-ingress-deployment>' --replicas=0
kubectl --kubeconfig "$DIRECT_KCFG" --context "$DIRECT_CTX" \
  -n '<namespace>' get endpointslices \
  -l 'kubernetes.io/service-name=<approved-service>' -o json \
  | jq '[.items[].endpoints[]? | select(.conditions.ready == true)] | length'
```

Zero ready backends does not deallocate the Service VIP or demonstrate that no clients *wanted* to reach it. Stop observability after its evidence has been exported, and keep CSI, DNS/CNI and the control plane until final checks. Watch for Grafana, GitOps, Helm or another reconciler restoring replicas; in the source a Grafana Deployment returned to desired `1` after scaling down and needed ownership review and a second scale-down.

**Expected results / validation:** Management record absent; downstream Rancher/Fleet components absent or individually explained; direct API still works; approved active workload replica counts and consuming Pods reach zero (failed, stuck Pods require explicit exception records); retained PVCs still match disposition decisions; CSI attachment inventory is empty **or** contains only explicitly approved, mapped exceptions; approved ingress services have zero ready backends. Save redacted before/after inventories and sign off unresolved objects.

**STOP / NO-GO:** Rancher cleanup pod blocked without a reviewed remedy; admission exception not restored; a retired application pod reappears; PDB or graceful termination blocks shutdown; unexplained attachment, writer, ingress route, or GitOps reconciling replica counts. Failed test pods are not evidence of detached volumes.

**Recovery:** Restore source custom resources or previous replica values only while operator, CSI and API are available, and revalidate storage attachment and app health. Before reversing Rancher detach, establish a separate re-registration plan; recreating its management record is not equivalent to undoing a UI Delete.

## Phase 4 — Infrastructure shutdown

**Purpose:** Stop guest workloads and RKE2 in dependency order, preserve API access until the last API-dependent check, then power off only the listed VMs. `NotReady` is not proof of `poweredOff`.

**Preconditions:** Phase 3 sign-off; no unexpected application Pods, volumes or PDB obligations; storage exceptions signed by the storage owner with guest and array checks; direct API available; complete VM list includes nodes *and* API load balancers; hypervisor operator has a power-state verification method. Confirm whether a node runs `rke2-agent`, `rke2-server`, or combined roles: the historical order applies to **dedicated** worker/monitor, control-plane and etcd VMs.

**Commands (on the specific guest after confirming `hostname` and role):**

```bash
hostname
systemctl is-active rke2-agent             # worker / monitoring node
sudo systemctl stop rke2-agent
sudo systemctl disable rke2-agent
sudo systemctl is-active rke2-agent
sudo systemctl is-enabled rke2-agent
sudo pgrep -af '[c]ontainerd-shim|[k]ubelet|[k]ube-proxy' || true
findmnt -rn -o TARGET | grep -E '^(/run/k3s|/var/lib/kubelet/pods)(/|$)' || true
sudo multipath -ll                       # if applicable to this host/storage
```

Inspect a `failed` service state and journal rather than interpreting it as an active process: the UAT canary had a failed unit and surviving containerd shims. Only after application shutdown and verifying no required volume mounts, if residual RKE2 processes remain and the node is approved for retirement, consider the locally installed `sudo /usr/local/bin/rke2-killall.sh`, then **repeat** the checks. It forcefully terminates processes and changes network/mount state; it is not a substitute for graceful application termination. Do not use `rke2-uninstall.sh` for a reversible shutdown. Use `sudo shutdown -h now` only after the node-level gate passes. Check the VM's **Powered Off** state independently in the hypervisor; SSH disconnect and Kubernetes `NotReady` do not prove that state.

Proceed one worker at a time (a canary first), then monitoring nodes after their storage exceptions are settled or explicitly accepted. Before stopping control-plane VMs, take the final API snapshot of nodes, Pods and attachments and confirm independent recovery artifacts. For dedicated control-plane-only nodes, repeat the guest verification using `rke2-server` and keep the direct-kubeconfig API server until last. Verify remaining API access between control-plane nodes. After the last API server stops, all remaining verification is through SSH/hypervisor/storage systems, not kubectl.

Stop dedicated etcd nodes last, one at a time. For three members, quorum requires two; for five, three. Deliberately crossing below quorum is a **one-way retirement checkpoint**: no later step may depend on the live Kubernetes API or writable etcd. Do not remove individual members to "fix" quorum. Confirm etcd is actually stopped on each node before guest shutdown, then verify power state. Dedicated API load balancers may be powered off when their *exclusive* ownership and lack of remaining API clients are confirmed; exact timing relative to etcd can differ by environment. They are not Kubernetes nodes and need their own inventory. If they hold a VIP, establish the failover/shutdown order with the network owner.

**Expected results / validation:** Each VM marked powered off by vCenter (or the site's hypervisor), recorded against the approved node/VM manifest; surviving masters/etcd healthy while API checks are still needed; no unexpected processes or mounts before each guest shutdown. Host-level iSCSI/multipath output must be interpreted against the known PV and array mapping inventory, not only as empty/nonempty.

**STOP / NO-GO:** A target name mismatch, still-running application, newly attached PVC, unexplained iSCSI session or array mapping, failed guest shutdown, shared LB service, loss of API before planned final check, or no vCenter power-state confirmation. An approved exception must name the precise PVs, guests, array owner and deferred resolution; it is not a blanket storage clearance.

**Recovery:** Before etcd quorum is deliberately lost, power on only approved nodes and restore the original `rke2-*` enablement and workloads under an explicit recovery plan. After quorum is lost, recovery requires the independently preserved snapshot/token and a separately reviewed restore procedure; do not improvise a partial cluster restart.

## Phase 5 — Post-shutdown verification

**Purpose:** Prove what actually stopped, without mistaking stale Kubernetes status for host state or treating incomplete inventory as completion.

**Preconditions:** All scheduled shutdown actions reported; hypervisor and backup/storage owners available; signed exception list accessible. Do not depend on a shut-down Kubernetes API.

**Commands (read-only, from approved management systems):**

```bash
# Run only after configuring govc for the correct vCenter and datacenter.
govc vm.info '<exact-inventory-path-to-retired-vm>'
# Review the reported Power state for EVERY node and dedicated API LB.
sha256sum '<approved-external-snapshot-copy>'
```

If `govc` is not available, use the hypervisor's inventory/export. Storage owners inspect array-side host mappings for all previously attached volumes; network owners inspect VIP advertisement/routing and DNS; inventory owners check records against the exact retired cluster. Keep recovery artifacts access-controlled and separately from this repository.

**Expected results / validation:** Every enumerated VM has an externally reported powered-off state; Rancher registration and downstream agents were verified removed *before* shutdown; backups and signed storage exceptions exist; all still-advertised VIPs and inventory records are assigned to cleanup tickets. Output must show the complete list, not merely a screenshot of one canary.

**STOP / NO-GO:** Missing VM in inventory, powered-on LB, incomplete snapshot custody, unknown backend storage mappings, or replacement-cluster/shared-resource ambiguity. Mark as **shutdown reported / verification incomplete** if command output is not available. The historical UAT PDF includes a canary vCenter check and the operator's later "all nodes" report, not a complete per-VM export. The production etcd shutdown is operator-confirmed separately; its execution output and final VM power inventory are not in the PDF.

**Recovery:** If an intended VM remains on, re-enter Phase 4 after determining why. If a wrong VM was stopped, halt the whole procedure and coordinate restoration with its owner before any further deletion.

## Phase 6 — Final decommission and cleanup (separately authorized)

**Purpose:** Retire records and physical assets without conflating a powered-off cluster with reclaimed storage or deleted infrastructure.

**Preconditions:** Phase 5 verified or formally documented as incomplete; retention period elapsed; explicit storage, virtualization, DNS/network and application owner approval for each class of resource. Verify no shared dependency on replacement clusters. The source says the two legacy clusters were not in Terraform state, but verify that for *each new environment*; do not run `terraform state rm`, `destroy`, or import because of this example.

**Commands:** This phase has **no generic deletion command**. Use the storage and hypervisor owners' approved change plans and APIs to reconcile PV/PVC-to-array IDs, VM disks and host mappings. Reconcile Terraform declarations/state if present; retire old DNS/VIPs, NetBox IP assignments and VM records, monitoring targets, certificates and backup retention through their owners. Record resource IDs, pre/post inventory, approvers, and rollback or retention disposition per item. Treat stale `Terminating` claims and `Delete` reclaim policies as a separate storage investigation. Once the cluster is offline, CSI cannot finish normal Kubernetes-driven detach/deletion workflows.

**Expected results / validation:** Approved assets and records absent or explicitly retained; array side independently checked; no cluster-specific alerts/DNS answers/VIP advertisements remain unless another owner has accepted them; decommission evidence and recovery artifacts archived for the approved retention period. Close the record only when every exception is resolved or transferred with an accountable owner.

**STOP / NO-GO:** Shared datastore/LUN, unclear PV ownership, absent retention authorization, unverified production test attachments, or missing evidence of the replacement's independence.

**Recovery:** DNS/inventory records may be restorable; storage and VM deletion may not be. Document the exact recovery capability and retention window before approving each deletion. Do not restart the retired Kubernetes cluster simply to clear objects without a separate risk assessment.

## Evidence provenance from the two historical retirements

The UAT record contains a direct API check showing 19 Ready nodes before Rancher detach; a source/destination snapshot checksum match; Rancher management record `NotFound` followed by downstream cleanup checks; a PSA-blocked cleanup Job and later removal of its temporary enforcement override; System Upgrade Controller `0/0`; seven StatefulSets `0/0`, zero VolumeAttachments and bound claims; four ingress/proxy Deployments `0/0` with zero ready backends; a worker canary's runtime and vCenter power-state checks. The operator then reported all nodes shut down. The PDF does not establish final per-VM vCenter inventory, data-owner approvals, array-side reclamation, or DNS/NetBox cleanup.

The production record contains 18 Ready nodes before and after direct kubeconfig recovery, matching snapshot checksums and matching server-token checksums, Rancher management and downstream agent cleanup, restored admission label, System Upgrade Controller `0/0`, four ingress/proxy backends with zero ready endpoints, seven StatefulSets `0/0`, and seven of ten CSI attachments clearing. Three long-stuck test attachments and their `Terminating` PVCs remained. Workers/monitors and later masters/API load balancers were reported powered off. **The operator separately confirms all production etcd servers were shut down.** Their shutdown outputs, array-side checks and final complete vCenter inventory are not present in the PDF. These are evidence gaps, not a reason to describe the three attachments as detached.
