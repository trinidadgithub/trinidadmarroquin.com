+++
title = 'Cilium Readiness And CNI Ownership'
date = 2026-08-28T00:00:00-05:00
draft = false
description = 'Field note for validating Cilium as a Kubernetes CNI with clear ownership, node readiness, datapath checks, kube-proxy assumptions, Hubble visibility, and rollback evidence.'
tags = ['kubernetes-networking', 'cilium', 'kubernetes', 'cni', 'hubble', 'operations']
categories = ['field-notes']
+++

Cilium is not just a CNI swap. It changes the cluster datapath, policy engine, observability surface, and sometimes kube-proxy ownership.

Before treating it as production-ready, prove the network contract rather than stopping at Running pods.

## Define Ownership First

Write down what owns each layer:

```text
cluster bootstrap -> installs the selected CNI once
Cilium operator   -> reconciles Cilium configuration and identities
Cilium agents     -> enforce datapath and policy on each node
kube-proxy        -> enabled, replaced, or intentionally absent
platform team     -> node routing, firewall, MTU, upgrades, and rollback
app teams         -> service labels, ports, and policy intent
```

Do not let RKE2, Helm, GitOps, and manual manifests all believe they own CNI installation. One owner should install and upgrade the datapath.

## Readiness Checks

Capture the baseline before changing policy or enabling advanced features:

```bash
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
kubectl -n kube-system get ds cilium
kubectl -n kube-system get deploy cilium-operator
cilium status --wait
cilium connectivity test
```

Confirm:

- every schedulable node has a healthy Cilium agent.
- the operator is available.
- pod-to-pod traffic works across nodes.
- ClusterIP service routing works.
- DNS from pods works.
- NetworkPolicy or Cilium policy enforcement behaves as expected.
- kube-proxy replacement mode matches the design.

If `cilium status` is green but service traffic fails, inspect kube-proxy mode, node routes, host firewall rules, and Cilium agent logs before changing application manifests.

## Datapath Assumptions

Record the choices that affect operations:

- tunnel mode or native routing.
- MTU expectations.
- kube-proxy replacement setting.
- node CIDR and pod CIDR assumptions.
- encryption setting, if enabled.
- load balancer behavior.
- BGP or L2 announcement ownership, if used.

These choices determine what a network incident looks like. A VXLAN MTU issue, native-routing route gap, and kube-proxy replacement problem can all appear as "pods cannot reach service."

## Hubble As Evidence

Hubble is useful when it answers an incident question quickly:

```bash
hubble status
hubble observe --namespace app-ns --follow
hubble observe --from-pod app-ns/client --to-pod app-ns/server
hubble observe --verdict DROPPED
```

Use it to prove whether traffic is forwarded, dropped by policy, failing DNS, or never leaving the source workload.

## Failure Model

The common failure is a partial CNI ownership transition:

```text
old CNI artifacts remain -> Cilium installs successfully
-> nodes show Ready -> policy or service routing behaves inconsistently
-> teams debug applications while datapath ownership is mixed
```

The operating rule: Cilium readiness means CNI ownership, datapath mode, service routing, DNS, and policy enforcement are all proven together.
