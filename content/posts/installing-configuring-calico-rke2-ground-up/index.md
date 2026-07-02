+++
title = 'Installing And Configuring Calico On RKE2 From The Ground Up'
date = 2026-07-02T00:00:00-05:00
draft = false
description = 'A practical Calico installation and configuration guide for RKE2: CNI ownership, Tigera operator setup, IP pools, node address autodetection, validation, and related operations notes.'
tags = ['calico', 'rke2', 'kubernetes', 'networking', 'cni', 'tigera']
categories = ['notes']
+++

Calico is not just a YAML install. It becomes part of the cluster's trust model, routing behavior, NetworkPolicy enforcement, and incident response surface.

The important decisions happen before the first manifest is applied:

- who owns CNI installation.
- which node interface Calico should use.
- which pod CIDR the cluster will allocate from.
- whether encapsulation is VXLAN, VXLAN cross-subnet, IP-in-IP, or BGP.
- how operators will prove the install is healthy after upgrades and node replacement.

This guide is written for RKE2 clusters where Calico is installed and managed intentionally, not discovered later as a side effect of another installer.

## Pick One Ownership Model

Do not mix CNI ownership models.

There are two common approaches:

```text
RKE2-managed CNI
RKE2 config selects the CNI and RKE2 deploys/manages the manifests.

Self-managed Calico
RKE2 starts without a packaged CNI, then GitOps or an operator installs Calico.
```

Both can work. The failure mode is combining them: RKE2 installs one CNI while GitOps installs another, or an operator tries to reconcile resources already owned by the distribution.

For a platform team, I prefer an explicit self-managed Calico path when the environment needs version pinning, custom autodetection, NetworkPolicy conventions, or repeatable GitOps promotion. That usually means:

```yaml
# /etc/rancher/rke2/config.yaml
cni: none
```

Then install Calico through a controlled path such as ArgoCD, Flux, or a reviewed bootstrap stage.

If you use the RKE2-managed Calico option instead, keep the same design discipline but place the configuration in the RKE2-supported location for your version. The operating rules below still apply: one owner, explicit node IP selection, and real validation.

## Define The Network Inputs

Before installing Calico, write down the network contract.

Example:

```text
cluster: cluster-a-prod
node network: 192.0.2.0/24
pod network: 198.51.100.0/24
service network: 203.0.113.0/24
node interface: ens192
encapsulation: VXLAN cross-subnet
NetworkPolicy: enforced by Calico
```

The exact CIDRs are environment-specific. The point is to separate three different address spaces:

- node IPs: addresses used by Kubernetes nodes.
- pod IPs: addresses assigned to pods by Calico.
- service IPs: virtual service addresses assigned by Kubernetes.

Do not let Calico infer the node interface in a multi-homed environment unless you are comfortable with the outcome. If a node has management, storage, backup, and workload networks, autodetection can pick the wrong address.

## Install The Tigera Operator

For a self-managed install, the Tigera operator owns Calico components and reconciles the `Installation` custom resource.

Pin the manifest version instead of applying a floating URL in production:

```bash
kubectl apply -f tigera-operator-vX.Y.Z.yaml
```

Then verify the operator is running:

```bash
kubectl get pods -n tigera-operator
kubectl get crd | grep -E 'operator.tigera.io|projectcalico.org'
```

Expected early signal:

```text
tigera-operator   1/1   Running
```

At this point, the operator exists, but Calico is not fully configured until the `Installation` resource is applied.

## Create The Installation Resource

A minimal operator-managed install should be explicit about pod pools and node address autodetection.

Example:

```yaml
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  variant: Calico
  calicoNetwork:
    bgp: Disabled
    nodeAddressAutodetectionV4:
      cidrs:
        - 192.0.2.0/24
    ipPools:
      - name: default-ipv4-ippool
        cidr: 198.51.100.0/24
        encapsulation: VXLANCrossSubnet
        natOutgoing: Enabled
        nodeSelector: all()
```

This example says:

- Calico should use node addresses from `192.0.2.0/24`.
- Pods should receive addresses from `198.51.100.0/24`.
- VXLAN cross-subnet is used instead of assuming pure L3 routing between all nodes.
- outbound pod traffic is NATed when leaving the pod network.
- BGP is disabled.

For environments that intentionally use BGP, the design changes. You need route reflectors, peer policy, firewall rules, and failure-domain thinking. Do not enable BGP because it sounds more advanced. Use it because the network is designed to route pod CIDRs directly.

Apply the resource:

```bash
kubectl apply -f calico-installation.yaml
```

Then watch reconciliation:

```bash
kubectl get installation default -o yaml
kubectl get pods -n calico-system -o wide
kubectl get pods -n tigera-operator -o wide
```

## Operate Autodetection Through The Tigera Operator

In a Tigera operator-managed cluster, node IP autodetection is not a node-by-node setting to hand-edit first. The durable fix belongs in the `Installation` resource:

```text
spec.calicoNetwork.nodeAddressAutodetectionV4
```

When Calico selects the wrong interface or subnet, patch the operator source of truth so every `calico-node` pod receives the same intended policy.

Example patch:

```bash
kubectl --context cluster-a-prod patch installation.operator.tigera.io default \
  --type=merge \
  -p '{
    "spec": {
      "calicoNetwork": {
        "nodeAddressAutodetectionV4": {
          "firstFound": false,
          "cidrs": ["192.0.2.0/24"]
        }
      }
    }
  }'
```

Then wait for the operator-managed DaemonSet to roll:

```bash
kubectl --context cluster-a-prod -n tigera-operator get pods -o wide

kubectl --context cluster-a-prod -n calico-system rollout status \
  ds/calico-node \
  --timeout=10m
```

Confirm the operator accepted the patch:

```bash
kubectl --context cluster-a-prod get installation.operator.tigera.io default -o json \
  | jq -r '.spec.calicoNetwork.nodeAddressAutodetectionV4'
```

Expected shape:

```json
{
  "firstFound": false,
  "cidrs": [
    "192.0.2.0/24"
  ]
}
```

Also inspect what the rendered `calico-node` pod receives:

```bash
kubectl --context cluster-a-prod -n calico-system get ds calico-node -o json \
  | jq -r '.spec.template.spec.containers[]
      | select(.name == "calico-node")
      | .env[]?
      | select(.name == "IP_AUTODETECTION_METHOD" or .name == "IP" or .name == "FELIX_IPAUTODETECTIONMETHOD")
      | "\(.name)=\(.value)"'
```

Finally, verify at least one node annotation against its Kubernetes `InternalIP`:

```bash
kubectl --context cluster-a-prod get node worker-1 -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}{"\t"}{.metadata.annotations.projectcalico\.org/IPv4Address}{"\n"}'
```

The host portion should match:

```text
192.0.2.10    192.0.2.10/24
```

The safe remediation order is:

1. audit mismatched nodes.
2. patch the Tigera `Installation` resource.
3. wait for `calico-node` rollout.
4. validate node annotations.
5. only then use node-level remediation for stale nodes that did not refresh.

Node-level remediation usually means cordoning the affected node, optionally draining workers, deleting the `calico-node` pod on that node, waiting for the node to become `Ready`, and confirming `projectcalico.org/IPv4Address` now matches `InternalIP`. If the annotation still does not match, leave the node cordoned and investigate the operator config instead of repeatedly deleting pods.

## Verify Node Address Selection

The first serious verification is whether Calico chose the same node IP that Kubernetes reports as `InternalIP`.

```bash
kubectl get nodes -o json \
  | jq -r '.items[]
      | [
          .metadata.name,
          (.status.addresses[]? | select(.type == "InternalIP") | .address),
          (.metadata.annotations["projectcalico.org/IPv4Address"] // "NONE"),
          (.metadata.annotations["projectcalico.org/IPv4VXLANTunnelAddr"] // "NONE")
        ]
      | @tsv' \
  | column -t
```

Healthy shape:

```text
worker-1  192.0.2.10  192.0.2.10/24  198.51.100.10
worker-2  192.0.2.11  192.0.2.11/24  198.51.100.11
```

Problem shape:

```text
worker-1  192.0.2.10  203.0.113.10/24  198.51.100.10
```

That means Calico selected an address that does not match the node's Kubernetes `InternalIP`. In a multi-network vSphere or bare-metal environment, that is usually an autodetection problem.

Fix the autodetection policy first. Avoid hand-patching node annotations unless you are following a short-lived emergency runbook.

## Verify Calico Components

Check the Calico workloads:

```bash
kubectl get pods -n calico-system -o wide
kubectl get daemonset -n calico-system
kubectl get deployment -n calico-system
```

Look for:

- `calico-node` running on every schedulable node.
- Typha replicas running if your cluster uses Typha.
- no repeated restarts on `calico-node` or `calico-kube-controllers`.
- pods scheduled across expected failure domains.

Then inspect node-level readiness:

```bash
kubectl get nodes -o wide
kubectl describe node worker-1 | grep -A8 Conditions
```

If nodes are `NotReady`, do not assume Calico is the root cause. A bad CNI install can cause NotReady symptoms, but so can kubelet failure, compute pressure, disk pressure, certificate problems, or host firewall drift.

## Verify Pod Networking

Deploy a temporary test workload:

```bash
kubectl create namespace net-test

kubectl -n net-test run client \
  --image=curlimages/curl:latest \
  --restart=Never \
  --command -- sleep 3600

kubectl -n net-test run server \
  --image=nginx:stable \
  --restart=Never
```

Wait for both pods:

```bash
kubectl -n net-test get pods -o wide
```

Test basic service discovery and pod connectivity:

```bash
kubectl -n net-test expose pod server --port 80

kubectl -n net-test exec client -- \
  curl -sS -I http://server.net-test.svc.cluster.local
```

Then test cross-node scheduling by checking `-o wide`. If both test pods land on the same node, force one to another node or repeat until you test node-to-node pod traffic.

Cleanup:

```bash
kubectl delete namespace net-test
```

## Verify NetworkPolicy Enforcement

Calico is often installed because the platform wants real NetworkPolicy enforcement. Prove that policy works.

Create a namespace and a default-deny policy:

```bash
kubectl create namespace policy-test

kubectl -n policy-test apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
EOF
```

Then deploy a client/server pair and verify traffic is blocked until explicit allow rules are added. If NetworkPolicy objects apply but do not change traffic behavior, the cluster does not have enforcement working even if the CNI pods are running.

Cleanup:

```bash
kubectl delete namespace policy-test
```

## Host Firewall And Port Checks

Calico depends on node-to-node traffic. The exact ports depend on your encapsulation and routing mode.

For VXLAN, pay attention to UDP `4789`. For Typha, pay attention to TCP `5473`. For BGP designs, TCP `179` becomes part of the routing contract.

Useful checks:

```bash
sudo ss -lntup | grep -E '4789|5473|179' || true
sudo ip link show | grep -E 'vxlan.calico|cali'
sudo ip route | grep -E 'bird|cali|tunl|vxlan' || true
```

If the host firewall is managed separately, test it intentionally. Do not let unmanaged `ufw` or ad-hoc firewall rules coexist with Kubernetes networking unless the platform has a clear policy for that.

## Upgrade And Change Control

Treat Calico upgrades like platform changes, not application deploys.

Before changing Calico:

- capture current `Installation`, IPPools, BGPPeers, and FelixConfiguration.
- confirm node readiness.
- confirm pod networking with a test namespace.
- identify maintenance or rollback path.
- confirm the GitOps controller will not revert or race the change.

Useful snapshots:

```bash
kubectl get installation default -o yaml > calico-installation.before.yaml
kubectl get ippool -o yaml > calico-ippools.before.yaml
kubectl get felixconfiguration -o yaml > calico-felix.before.yaml
kubectl get nodes -o wide > nodes.before.txt
```

After the change, repeat the same captures and compare.

## Common Failure Modes

Wrong node IP selected:

```text
Calico IPv4Address host portion does not match Kubernetes InternalIP
```

Usually fixed by changing `nodeAddressAutodetectionV4`, then rolling Calico components according to the runbook.

Pods cannot reach pods on other nodes:

```text
same-node traffic works, cross-node traffic fails
```

Check encapsulation mode, host firewalls, MTU, and routing.

NetworkPolicy has no effect:

```text
policies exist, traffic still flows
```

Confirm Calico is the active CNI and policy engine, not merely installed alongside another CNI.

Clean audit shows zero targets:

```text
0 mismatch targets
```

That can mean every node is clean, not that the audit failed. Use all-node audit evidence before declaring success.

## Acceptance Criteria

Calico is ready when these are true:

- one system owns CNI installation.
- `calico-node` is running on expected nodes.
- Kubernetes node `InternalIP` matches Calico `IPv4Address` host portion.
- pod-to-pod traffic works across nodes.
- service DNS and ClusterIP access work.
- NetworkPolicy enforcement is proven with a deny/allow test.
- host firewall rules are compatible with the chosen Calico mode.
- Calico configuration is versioned and reviewed.
- operators know how to audit and remediate node IP autodetection drift.

## Related Field Notes

- [Calico IP Audit Zero Targets Does Not Mean Zero Nodes](/field-notes/calico-ip-audit-zero-targets/) — how to interpret mismatch-only Calico audit scripts.
- [DNS Drift Detector Calico Overlay False Positives](/field-notes/dns-drift-detector-calico-overlay-filter/) — why Calico overlay links should not be parsed as DNS search domains.
- [Remediation Audits With NotReady Nodes And Calico Checks](/field-notes/remediation-audits-notready-calico-inventory/) — how to keep NotReady nodes visible during remediation and Calico validation.
- [RKE2 kube-proxy CrashLoopBackOff After Upgrade Due To UFW](/field-notes/rke2-kube-proxy-crashloop-ufw-after-upgrade/) — reminder that host firewall drift can look like a Kubernetes dataplane failure.

The installation is only the beginning. The durable operating model is explicit CNI ownership, clear node IP selection, repeatable validation, and audit output that tells operators what was actually checked.
