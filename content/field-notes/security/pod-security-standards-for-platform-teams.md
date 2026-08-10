+++
title = 'Pod Security Standards For Platform Teams'
date = 2026-08-10T00:00:00-05:00
draft = false
description = 'Operational field note for enforcing Kubernetes pod security standards, admission enforcement strategy, namespace exemptions, and the failures that show up in production.'
tags = ['kubernetes', 'security', 'pod-security', 'rbac', 'platform-engineering', 'operations', 'compliance']
categories = ['field-notes']
+++

Pod Security Standards are the default answer for "make workloads run non-privileged" in Kubernetes.

They replace the removed PodSecurityPolicy admission controller with three policies, Baseline, Restricted, and Privileged, that can be enforced or audited per namespace. The model is simple, but production mistakes come from exemptions, admission confusion, and treating the label as the control.

This note covers operating Pod Security Standards on real clusters.

## Know The Three Policies

- **Privileged**: unrestricted, for system workloads that legitimately need it.
- **Baseline**: allows the default Kubernetes behavior while preventing known privilege escalation. Good starting point for most non-system namespaces.
- **Restricted**: the hardened target. No privileged containers, no host network, strict volume and capability limits.

Baseline is the pragmatic default. Restricted is the goal where the workload can satisfy it. Privileged is a documented exception, not a default.

## Enforcement Modes

Each namespace label takes a mode:

```text
pod-security.kubernetes.io/enforce: baseline|restricted|privileged
pod-security.kubernetes.io/audit: baseline|restricted|privileged
pod-security.kubernetes.io/warn: baseline|restricted|privileged
```

- **enforce**: admission blocks violating pods.
- **audit**: violating pods are allowed and recorded in audit events.
- **warn**: violating pods are allowed and surface a warning to the user.

Use `enforce` for the namespace's agreed level. Use `audit` and `warn` to shorten the runway before enforcing a higher level.

## Where Enforcement Actually Runs

The labels are honored by an admission controller or by a validating webhook implementation. Verify yours is actually active before relying on enforcement:

```bash
kubectl get ns <namespace> -o json | jq '.metadata.labels'
kubectl get validatingwebhookconfigurations -o wide | grep -i pod-security
```

If the webhook is missing or broken, labels with `enforce` can exist with no enforcement happening. Label state is not the same as admission state.

## Set The Default, Then Override

Standard platform pattern: apply a default policy at the platform level and let teams lower or raise it deliberately.

```bash
kubectl label ns --all pod-security.kubernetes.io/enforce=baseline
kubectl label ns kube-system pod-security.kubernetes.io/enforce=privileged
```

Walk every namespace and classify it before labelling:

- platform system namespaces that run privileged components.
- application namespaces that can satisfy Baseline.
- application namespaces working toward Restricted.
- legacy namespaces that need audit-only for a defined window.

Classify first, label second. Guessing labels as a batch push leads to broken deployments and emergency relaxations.

## Restricted Workload Reality

Restricted still blocks a lot of real workloads.

Typical Restricted blockers on application containers:

```text
securityContext.privileged: true
securityContext.capabilities.add: SYS_ADMIN
securityContext.seccompProfile: not set
securityContext.runAsUser: 0
securityContext.runAsNonRoot: not set
hostNetwork: true
hostPID, hostIPC: true
emptyDir and volume restrictions per policy
```

Before promising Restricted, verify the application manifest can satisfy:

- `runAsNonRoot: true` and a non-root `runAsUser`.
- `allowPrivilegeEscalation: false`.
- `seccompProfile` set to `RuntimeDefault` or a custom localhost profile.
- only allowed capabilities.
- no host namespaces.

## Exemption Discipline

Privileged namespaces and workload-level exemptions are where pod security goes soft.

For workloads that must bypass the namespace level, prefer clarifying why the platform default is wrong for this workload:

- Node-level agents that truly need host access.
- CSI or storage helper pods.
- CNI components.
- Legacy workloads with an explicit migration ticket.

An exemption without an owner and a review date is a debt item, not a solution. Record it in the namespace:

```text
pod-security.kubernetes.io/enforce: privileged
# owner: storage-platform
# review: next platform audit
```

## Detection And Triage Commands

List namespace policy state:

```bash
kubectl get namespaces -o custom-columns=NS:.metadata.name,ENFORCE:.metadata.labels["pod-security.kubernetes.io/enforce"],AUDIT:.metadata.labels["pod-security.kubernetes.io/audit"]
```

Check whether admission is actually loaded:

```bash
kubectl get validatingwebhookconfigurations -o custom-columns=NAME:.metadata.name,PATHS:'.webhooks[*].clientConfig.service'
```

Look for pods failing with policy violations:

```bash
kubectl get events -A | grep -i -E "pod security|policy|forbidden"
```

## Common Failure Modes

### Label Present, No Enforcement

The webhook is disabled, removed, or misconfigured. The label looks correct and nothing is blocked.

### Batch Label Push Breaks Workloads

A whole namespace set is flipped to Restricted before manifests are ready. Operators respond by flipping everything back to Privileged, which removes the control entirely.

### Restricted Read As "No Root Only"

Restricted requires `runAsNonRoot`, seccomp profile, and `allowPrivilegeEscalation: false`, in addition to no root. Missing any one keeps the pod out of compliance.

### Privileged As The Default Shape

System workloads are shipped in a single Privileged namespace, so policy coverage looks complete while most workloads run unconstrained.

### Enforcement Is Confused With Policy

Labels say Baseline, but workload manifests still request privileged features. Nothing blocks them because the label allows the privileges they request.

## Review Checklist

- Does the cluster have an active admission implementation for pod security labels?
- Is there a written default level for application namespaces?
- Are privileged namespaces enumerated and owned?
- Is Restricted the target, with Baseline as the staged path?
- Do workload manifests satisfy the level they claim before promotion?
- Are exemptions documented with owners and review dates?
- Is there a scheduled audit of namespace policy state?
- Do system workloads justify Privileged instead of inheriting a default?

## Practical Takeaway

Pod Security Standards only enforce what is actually wired into admission.

Set a sane platform default, classify namespaces before labelling, treat Privileged as a documented exception, and verify that labels map to working enforcement. The control is the admission path plus the labels, not the labels alone.

## References

- [Kubernetes Ingress Operations Checklist](/field-notes/kubernetes-ingress-operations-checklist/)
- [Temporary Privileged Daemonset Maintenance Access](/field-notes/temporary-privileged-daemonset-maintenance-access/)
- [Kubernetes Maintenance Evidence Bundles](/field-notes/kubernetes-maintenance-evidence-bundles/)