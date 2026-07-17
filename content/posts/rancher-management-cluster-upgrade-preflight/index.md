+++
title = 'Rancher Management Cluster Upgrades Need More Than A Version Target'
date = 2026-07-15T00:00:00-05:00
draft = false
description = 'A practical Rancher and RKE2 upgrade runbook pattern covering stabilization, worker replacement, backups, stale RKE1 artifacts, Helm upgrade recovery, and post-upgrade validation.'
tags = ['rancher', 'rke2', 'kubernetes', 'upgrades', 'operations', 'backup', 'helm']
categories = ['posts']
+++

Rancher management-cluster upgrades are not just a Helm command. They are a sequence of readiness gates.

The version target matters, but it is not the first question. The first question is whether the management cluster is stable enough to survive the change.

In one upgrade run, the desired path was straightforward on paper:

```text
Rancher first, then Kubernetes/RKE2.
```

The actual work exposed the operational details that make or break the window: stale workers, version skew, node join scripts, root filesystem pressure, backup transfer permissions, Rancher pre-upgrade hooks, Fleet health, and downstream cluster impersonation.

## The Seven-Step Shape

For a Rancher-managed RKE2 environment, keep the sequence explicit:

1. Stabilize the management cluster.
2. Take full backups and current-state captures.
3. Upgrade Rancher before Kubernetes.
4. Normalize old worker skew to the current management-cluster version.
5. Upgrade control-plane and etcd nodes to the target Kubernetes/RKE2 minor.
6. Upgrade workers to the target Kubernetes/RKE2 minor.
7. Validate Rancher, Fleet, downstream clusters, and platform add-ons.

The order is deliberate. Rancher must support the Kubernetes/RKE2 version it is about to manage. Worker capacity must exist before control-plane changes. Backups must be proven before any irreversible step.

## Stabilize Before Upgrading

Do not start by upgrading the broken cluster you wish you had. Start by stabilizing the cluster you actually have.

Baseline checks:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running
kubectl get events -A --sort-by=.lastTimestamp
kubectl get pdb -A
kubectl get pods -A -o wide | egrep 'rancher|cattle|fleet|ingress|metallb|calico'
```

Stop and fix first if you find:

- a long-term `NotReady` worker still carrying old DaemonSet pods.
- only one schedulable worker for management workloads.
- version skew where control-plane nodes are current but workers are several minors behind.
- `FreeDiskSpaceFailed` events on control-plane nodes.
- Rancher/Fleet/webhook pods already unhealthy.
- unresolved storage or ingress issues that would obscure upgrade failures.

If a worker is permanently dead and no longer hosting useful state, remove it from Kubernetes before the upgrade:

```bash
kubectl get pods -A --field-selector spec.nodeName=worker-3 -o wide
kubectl delete node worker-3
```

Then add replacement workers before draining or upgrading the remaining old workers.

## Worker Replacement Has Its Own Traps

When joining new RKE2 workers, retrieve the node token from a control-plane node:

```bash
sudo cat /var/lib/rancher/rke2/server/node-token
```

Be careful with how scripts write the token into `/etc/rancher/rke2/config.yaml`. A line break after `token:` changes the YAML shape and can leave the agent with an empty token or invalid join config.

Good shape:

```yaml
server: https://192.0.2.10:9345
token: K<redacted>::server:<redacted>
node-label:
  - role=worker
  - os=Linux
  - cluster=cluster-a
```

Avoid setting the Kubernetes reserved display-role label through kubelet `--node-labels`:

```text
node-role.kubernetes.io/worker
```

Modern kubelet validation rejects unknown labels in the `kubernetes.io` and `k8s.io` namespaces. If the agent repeatedly logs this, it is not waiting on the server. Kubelet is exiting:

```text
Kubelet exited: exit status 1
failed to validate kubelet flags: unknown 'kubernetes.io' or 'k8s.io' labels specified with --node-labels
```

Use a normal custom label during join, then set the display role after the node is registered:

```bash
kubectl label node worker-4 node-role.kubernetes.io/worker= --overwrite
```

The display role is for operator readability. It should not break node registration.

## Fix Disk Pressure Before The Window

RKE2 control-plane nodes can accumulate old runtime data, etcd files, containerd content, and logs. If events show disk pressure, check root filesystem usage and the main consumers:

```bash
df -h
sudo du -xh /var/lib/rancher/rke2 | sort -h | tail -30
sudo du -xh /var/lib/kubelet | sort -h | tail -30
sudo du -xh /var/log | sort -h | tail -30
```

If vSphere has already grown the virtual disk but the guest still sees the old partition/LVM size, rescan and grow carefully:

```bash
lsblk
sudo pvs
sudo vgs
sudo lvs

sudo growpart /dev/sda 3
sudo pvresize /dev/sda3
sudo lvextend -r -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv
df -h
```

Do this before the upgrade. Root filesystem pressure during a Rancher or RKE2 upgrade turns every symptom into a false lead.

## Backups Need Transferable Evidence

Take an RKE2 etcd snapshot from a control-plane node:

```bash
sudo rke2 etcd-snapshot save --name pre-upgrade-$(date +%Y%m%d-%H%M%S)
```

Then back up control-plane state from every control-plane node:

```text
/etc/rancher/rke2/
/var/lib/rancher/rke2/server/db/
/var/lib/rancher/rke2/server/tls/
RKE2 service/config files used by the host
```

Do not assume the snapshot is easy to copy as your user. RKE2 snapshots are often root-owned under the server DB path. If `scp` cannot read the directory, copy the snapshot to a temporary path with safe ownership first:

```bash
sudo cp /var/lib/rancher/rke2/server/db/snapshots/pre-upgrade-* /tmp/
sudo chown operator:operator /tmp/pre-upgrade-*
```

Capture Rancher and cluster state next:

```bash
helm list -A > helm-list-all-namespaces.txt
helm list -n cattle-system > helm-list-cattle-system.txt
helm get values rancher -n cattle-system -o yaml > rancher-helm-values.yaml
helm status rancher -n cattle-system > rancher-helm-status.txt

kubectl get nodes -o wide > kubectl-get-nodes-wide.txt
kubectl get pods -A -o wide > kubectl-get-pods-all-wide.txt
kubectl get crds > kubectl-get-crds.txt
kubectl get events -A --sort-by=.lastTimestamp > kubectl-get-events-all.txt
kubectl get secrets -n cattle-system > kubectl-get-secrets-cattle-system.txt
kubectl get namespaces --show-labels > kubectl-get-namespaces-labels.txt
```

Verify archives, do not just create them:

```bash
for file in *.tgz; do
  tar tzf "$file" >/dev/null && echo "OK: $file"
done
```

Exit criteria for the backup step:

- etcd snapshot exists and is copied off the control-plane node.
- config/tls/db archives exist for every control-plane node.
- archives pass `tar tzf`.
- Rancher Helm values and status are captured.
- current Kubernetes state captures are present.

## Upgrade Rancher Before Kubernetes

Before changing Kubernetes/RKE2 minor versions, confirm the Rancher target supports the desired downstream and local cluster targets.

Preserve current Rancher values:

```bash
helm get values rancher -n cattle-system -o yaml > rancher-helm-values.yaml
```

Then upgrade with Helm:

```bash
RANCHER_TARGET_VERSION="2.14.3"

helm upgrade rancher rancher-stable/rancher \
  --namespace cattle-system \
  --version "$RANCHER_TARGET_VERSION" \
  -f rancher-helm-values.yaml
```

If the pre-upgrade hook fails with `BackoffLimitExceeded`, inspect the hook logs before retrying. One important failure mode is stale RKE1 provisioning artifacts blocking Rancher 2.12+ upgrades:

```text
Rancher v2.12+ does not support RKE1.
Detected RKE1-related resources.
NodeTemplate: 2
```

Check whether stale node templates exist and whether any active node pools reference them:

```bash
kubectl get nodetemplates.management.cattle.io -A -o wide
kubectl get nodepools.management.cattle.io -A -o wide
kubectl get clusters.provisioning.cattle.io -A
```

If the `NodeTemplate` objects are stale and no `NodePool` objects reference them, remove the stale artifacts, delete the failed hook job, and retry:

```bash
kubectl delete nodetemplate.management.cattle.io -n cattle-global-nt <template-name>
kubectl delete job -n cattle-system rancher-pre-upgrade

helm upgrade rancher rancher-stable/rancher \
  --namespace cattle-system \
  --version "$RANCHER_TARGET_VERSION" \
  -f rancher-helm-values.yaml
```

Do not delete provisioning artifacts blindly. The safety check is that they are stale and not referenced by active node pools.

## Validate The Rancher Upgrade

Validate from the inside out:

```bash
kubectl rollout status deploy/rancher -n cattle-system --timeout=10m
helm --namespace cattle-system list
kubectl -n cattle-system get deploy rancher -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl get pods -n cattle-system -o wide
kubectl get pods -n cattle-fleet-system -o wide
kubectl get pods -n cattle-fleet-local-system -o wide
kubectl get bundles -A
kubectl get clusters.provisioning.cattle.io -A
```

Check the browser path and unauthenticated API behavior through the real hostname:

```bash
curl -k -I https://rancher.example.com/dashboard/
curl -k -I https://rancher.example.com/v3
```

Expected signals:

- Rancher deployment rolled out.
- Helm shows the target Rancher chart and app version.
- `rancher/rancher:<target>` is running.
- Rancher pods are ready.
- webhook is running.
- Fleet controller and local Fleet agent are running.
- managed clusters are visible.
- `/dashboard/` returns `200`.
- `/v3` may return `401` when unauthenticated, which still proves the endpoint is reachable.

## Watch For Post-Upgrade Rancher Symptoms

After a major Rancher upgrade, downstream clusters may briefly report Fleet or agent churn. Do not assume every UI warning is fatal, but do not ignore these patterns:

```text
fleet-agent ... Pending termination
0/1 Bundles Ready
unable to create impersonator account
failed to get secret for service account: cattle-impersonation-system/...
```

Use both management-cluster and downstream-cluster checks:

```bash
kubectl get bundles -A
kubectl get bundledeployments -A
kubectl get clusters.provisioning.cattle.io -A
kubectl get pods -A | egrep 'fleet|cattle|rancher'
```

If a downstream kubeconfig fails through Rancher impersonation, verify whether direct cluster access works before blaming Kubernetes itself. The failing layer may be Rancher-generated impersonation, not the downstream API server.

## Rewrite The Runbook After The First Upgrade

The first management cluster is where the runbook learns. Before touching the next dev or production Rancher cluster, add checks for what actually happened:

- remove or document stale RKE1 `NodeTemplate` artifacts before Rancher 2.12+.
- confirm no active `NodePool` references before deleting old templates.
- validate root filesystem capacity on every control-plane node.
- prove backup archives and etcd snapshots are readable off-node.
- verify replacement workers can join without reserved kubelet labels.
- label display roles after join instead of breaking kubelet startup.
- capture Rancher Helm values before the upgrade and after the upgrade.
- verify which `system-upgrade-controller` Plans are active before each hop.
- validate Fleet bundles and downstream impersonation after the UI loads.

## Operating Rule

Do not treat Rancher upgrade readiness as “Rancher supports the target Kubernetes version.”

Upgrade readiness means the management cluster is stable, worker capacity exists, disk pressure is gone, backups are verified, stale provisioning artifacts are understood, and Rancher/Fleet/downstream cluster health can be proven before moving on to Kubernetes itself.

Related:

- [Rancher RKE2 Minor Hops When UI Metadata And GitOps Plans Disagree](/posts/rancher-rke2-minor-hop-gitops-suc/)
- [Rancher RKE2 Upgrade Pods Mutate The Host Filesystem](/field-notes/rancher-rke2-upgrade-pods-host-filesystem/)
- [When A Latent Rancher Worker Upgrade Becomes An Outage](/posts/rancher-system-upgrade-controller-latent-worker-risk/)
- [Emergency Stop For Rancher System Upgrade Controller](/field-notes/rancher-system-upgrade-controller-emergency-stop/)
- [Kubernetes Upgrade Sequencing](/projects/kubernetes-platform-operations/upgrade-sequencing/)
