+++
title = 'RKE2 Worker Join Failures From Calico Wrong Interface Selection'
date = 2026-07-15T00:00:00-05:00
draft = false
description = 'Field note for diagnosing RKE2 worker replacement failures where agent load balancer timeouts, duplicate node identity, and Calico node IP autodetection drift point at different layers of the same problem.'
tags = ['rke2', 'kubernetes', 'calico', 'networking', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

Replacing an RKE2 worker can look like a token, hostname, or API availability problem when the real issue is lower in the node networking path.

One useful pattern is to separate three signals that often appear together:

- the RKE2 agent cannot reach the supervisor through its local load balancer.
- the Kubernetes API reports duplicate node identity or stale node password state.
- Calico advertises an address from the wrong interface or subnet.

Those symptoms are related, but they are not all fixed in the same place.

## Symptom

The replacement worker starts `rke2-agent`, but the service never settles:

```text
rke2-agent: failed to get CA certs: Get "https://127.0.0.1:6444/cacerts": context deadline exceeded
rke2-agent: Waiting to retrieve kube-proxy configuration; server is not ready
```

The `127.0.0.1:6444` address is not the Kubernetes API server itself. It is the node-local RKE2 agent load balancer. A timeout there means the local agent process could not establish a working upstream path to the configured server endpoint.

Do not stop at the localhost address. Check what the agent is trying to reach.

```bash
sudo systemctl status rke2-agent --no-pager
sudo journalctl -u rke2-agent -n 200 --no-pager
sudo cat /etc/rancher/rke2/config.yaml
sudo ss -lntp | grep -E '6444|9345|6443' || true
```

The expected agent config shape is small:

```yaml
server: https://cluster-a-api.example.com:9345
token: REDACTED
node-name: worker-1
```

If the token line is malformed, fix that first. If the server URL is wrong or DNS points at the wrong place, fix that first. If both are correct, move down the stack.

## Separate Join Identity From Network Reachability

RKE2 may also report node identity errors:

```text
Node password rejected, duplicate hostname or contents of /etc/rancher/node/password may not match server node-passwd entry
```

That is a different class of problem than an API timeout.

For a true node replacement, make the lifecycle explicit:

```bash
kubectl get nodes -o wide
kubectl delete node worker-1

sudo systemctl stop rke2-agent
sudo rm -rf /etc/rancher/node
sudo rm -rf /var/lib/rancher/rke2/agent
sudo systemctl start rke2-agent
```

Only do this on the replacement node after confirming it is not a running production member you still need. The point is to avoid mixing stale node password state with the new machine's join attempt.

If the agent still cannot reach the supervisor after identity cleanup, the remaining problem is likely connectivity, host routing, firewalling, certificate trust, proxy settings, or CNI/node IP behavior.

## Check The Address Calico Selected

When the worker finally appears, or when comparing against healthy nodes, check the Kubernetes node address next to the Calico annotation:

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
worker-1  192.0.2.10  169.254.10.25/24  198.51.100.10
```

That mismatch means Kubernetes and Calico disagree about the node address. In a multi-homed vSphere environment, Calico's default autodetection can choose a storage, backup, migration, or otherwise non-primary interface. The node may look partially alive while pod networking and node-to-node paths fail in confusing ways.

## Fix The Source Of Truth

Do not hand-edit `projectcalico.org/IPv4Address` as the durable fix. In a Tigera operator-managed install, fix the `Installation` resource so every Calico node gets the same address selection policy.

Example using an intended node CIDR:

```bash
kubectl patch installation default --type merge -p '{
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

Then roll or restart Calico components according to the platform runbook and re-check the node annotations.

If the cluster is not operator-managed, update the configured Calico autodetection method in the actual deployment source of truth. The principle is the same: make interface selection deterministic instead of relying on `firstFound` in a multi-network host.

## Triage Order

Use this order to avoid chasing the wrong layer:

1. Confirm `/etc/rancher/rke2/config.yaml` has a valid `server`, token, and `node-name`.
2. Confirm DNS and direct TCP reachability to the RKE2 supervisor endpoint on `9345`.
3. Confirm local `127.0.0.1:6444` is created by the agent, not mistaken for a remote API address.
4. Clear stale node identity only after deleting or intentionally replacing the old Kubernetes node object.
5. Compare Kubernetes `InternalIP` with Calico `projectcalico.org/IPv4Address`.
6. Fix Calico autodetection at the operator or manifest source of truth.
7. Revalidate node readiness, CoreDNS, kube-proxy, and cross-node pod traffic.

## Acceptance Criteria

The replacement is healthy when these are true:

- `rke2-agent` is active without repeated `127.0.0.1:6444` timeout loops.
- the node name is unique and has no stale password conflict.
- Kubernetes `InternalIP` uses the intended primary node network.
- Calico `IPv4Address` matches the intended node network, not a storage or auxiliary subnet.
- pods can communicate across nodes.
- the autodetection setting is versioned in the cluster's source of truth.

The key lesson is that an RKE2 worker join failure may expose multiple issues in sequence. Fix token and node identity problems when they are real, but still verify Calico node IP selection before declaring the replacement complete.
