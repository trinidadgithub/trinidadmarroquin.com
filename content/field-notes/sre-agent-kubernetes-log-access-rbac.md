+++
title = 'SRE Agent Kubernetes Log Access With Namespaced RBAC'
date = 2026-06-29T00:00:00-05:00
draft = false
description = 'Field note for granting an SRE agent read-only access to Kubernetes pod logs and events through least-privilege namespaced RoleBindings instead of broad ClusterRoleBindings.'
tags = ['kubernetes', 'rancher', 'rbac', 'argocd', 'kustomize', 'sre', 'security']
categories = ['field-notes']
+++

An SRE agent can authenticate to Rancher and still fail every useful workload call. Seeing clusters in Rancher does not automatically mean the account can read pods, logs, events, or namespace-scoped workloads in downstream clusters.

This pattern applies when an SRE automation identity reports symptoms like:

```text
namespaces is forbidden: User "u-example" cannot list resource "namespaces" in API group "" at the cluster scope
pods is forbidden: User "u-example" cannot list resource "pods" in namespace "app-namespace"
```

The important distinction is scope. The identity may have management-plane visibility and read-only node visibility, but no downstream project or namespace RBAC.

## Start With The Actual Request

Do not translate "can't get logs" into cluster-wide view access by default.

Break the request down into required Kubernetes permissions:

```text
get/list/watch pods
get pods/log
get/list events
get/list deployments
get/list replicasets
get/list services
get/list endpoints
```

Those can be granted with namespaced `RoleBinding`s that reference a read-only `ClusterRole`.

The permission that changes the risk profile is namespace discovery:

```text
list namespaces
```

`namespaces` is cluster-scoped. Granting it requires cluster-scoped RBAC, usually a `ClusterRoleBinding`. If the agent can be configured with explicit namespaces, skip namespace listing and keep access namespaced.

## Prefer Group Bindings Over User IDs

Bind an AD group or identity-provider group instead of a Rancher user ID when possible:

```yaml
subjects:
  - kind: Group
    name: "activedirectory_group://CN=sre-investigate,OU=groups,DC=example,DC=com"
```

Group bindings are easier to audit, rotate, and reuse across clusters. Direct user IDs such as `u-example` are harder to reason about later and couple the manifest to Rancher internals.

## Use An Existing Readonly ClusterRole

Define the capability package once as a `ClusterRole`:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: platform:readonly
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["events", "services", "endpoints"]
    verbs: ["get", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list"]
```

Then bind that role only inside the namespaces the SRE agent needs:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: platform:sre-investigate-readonly
  namespace: shared-infra
subjects:
  - kind: Group
    name: "activedirectory_group://CN=sre-investigate,OU=groups,DC=example,DC=com"
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: platform:readonly
```

A namespaced `RoleBinding` can reference a `ClusterRole`. That does not make the binding cluster-wide. The binding scope remains the namespace where the `RoleBinding` lives.

## Keep Namespace Lists Honest

Before generating RBAC for requested namespaces, verify they exist in the target clusters:

```bash
kubectl --context cluster-a-prod get namespaces
kubectl --context cluster-a-uat get namespaces
```

If requested namespaces do not exist, remove them from the change instead of shipping dead RoleBindings. Dead bindings create noise and make reviewers wonder whether the access request was understood.

Example decision:

```text
requested: app-namespace, shared-infra, argocd-app-namespace
exists:    shared-infra
ship:      shared-infra only
```

## Render Through GitOps

For a GitOps-managed RBAC repository, update the generator inventory rather than hand-editing generated overlays:

```yaml
bindings:
  - group:
      name: sre_investigate
      dn: "CN=sre-investigate,OU=groups,DC=example,DC=com"
    role: readonly
    scope:
      environment: prod
      clusters: all
    namespaces:
      - shared-infra
```

Then regenerate:

```bash
python3 rbac/hack/generate-overlays/generate.py
```

The generated output should create namespaced `RoleBinding`s in each intended overlay and should not introduce `ClusterRoleBinding`.

## Validate The Rendered Access

Build the changed overlays:

```bash
kubectl kustomize rbac/overlays/prod/cluster-a >/tmp/prod-cluster-a-rbac.yaml
kubectl kustomize rbac/overlays/uat/cluster-a >/tmp/uat-cluster-a-rbac.yaml
```

Confirm the expected subject and namespace appear:

```bash
grep -n 'sre-investigate\|namespace: shared-infra' /tmp/prod-cluster-a-rbac.yaml
```

Confirm broad access was not introduced:

```bash
grep -R 'kind: ClusterRoleBinding' rbac/overlays/prod rbac/overlays/uat || true
grep -R 'secrets\|pods/exec\|pods/portforward' rbac/overlays/prod rbac/overlays/uat || true
```

After ArgoCD syncs, validate with impersonation or the target identity where possible:

```bash
kubectl --context cluster-a-prod auth can-i get pods \
  --as='u-example' \
  -n shared-infra

kubectl --context cluster-a-prod auth can-i get pods/log \
  --as='u-example' \
  -n shared-infra

kubectl --context cluster-a-prod auth can-i list namespaces \
  --as='u-example'
```

Expected minimum-access result:

```text
get pods in shared-infra       yes
get pods/log in shared-infra   yes
list namespaces                no
```

That `no` is intentional if the SRE gateway is configured with explicit namespaces.

## Risk Rating

For a customer-facing cluster, this change is usually moderate risk, not trivial:

```text
2/5 when limited to specific namespaces and read-only resources
3/5 or higher if expanded to all namespaces or cluster-scoped discovery
4/5+ if secrets, exec, port-forward, or write verbs are added
```

The difference between 2/5 and 3/5 is usually scope creep. A few namespaced `RoleBinding`s for logs and events are very different from fleet-wide `view` or namespace discovery across every cluster.

## Review Checklist

- The identity is an AD/group subject, not a brittle Rancher user ID.
- The rendered objects are `RoleBinding`, not `ClusterRoleBinding`.
- The bound role does not include secrets, exec, port-forward, impersonation, or write verbs.
- The namespaces exist in the target clusters.
- Generated files were produced by the generator, not hand-edited.
- `kubectl kustomize` succeeds for all affected overlays.
- The SRE agent operator understands whether namespaces must be configured explicitly.

The safest fix is not "give the agent view everywhere." It is to grant the smallest namespaced read path that lets the agent collect logs and events, then expand only when the next concrete requirement proves it is necessary.
