+++
title = 'KUBECONFIG Merge Order Can Shadow Fresh Rancher Tokens'
date = 2026-09-08T00:00:00-05:00
draft = false
description = 'A Kubernetes access field note on diagnosing kubectl 403 unauthenticated errors caused by duplicate user names across merged kubeconfig files.'
tags = ['kubernetes', 'rancher', 'kubectl', 'workstation', 'troubleshooting', 'operations']
categories = ['field-notes']
+++

A freshly downloaded kubeconfig can be valid and still fail when `kubectl` uses it.

One failure pattern is duplicate user names across a merged `KUBECONFIG`. Rancher-generated kubeconfigs often use the same user name, such as `rancher`, across multiple clusters or downloaded files. When several kubeconfig files are merged, the first user with that name can win. A stale token from an older file can shadow the fresh token from the file you just downloaded.

The symptom looks like a server-side authorization issue:

```text
Error from server (Forbidden): User "system:unauthenticated" cannot list resource "nodes"
```

The operator can still log in to the Rancher UI, and the new kubeconfig can work by itself. The merged config is the thing that is broken.

## Prove The New File Works Alone

Before changing anything, test the downloaded kubeconfig directly:

```bash
kubectl --kubeconfig ./new-rancher.yaml \
  --context cluster-a \
  get nodes
```

If that works, the cluster, user account, and new token are probably valid.

Then check the merged path:

```bash
echo "$KUBECONFIG"
kubectl config current-context
kubectl get nodes
```

If the standalone file works and the merged config fails, inspect merge order.

## Find Duplicate Users

List users in every file without printing tokens:

```bash
for file in ${KUBECONFIG//:/ }; do
  echo "=== $file ==="
  kubectl config view --kubeconfig "$file" \
    -o jsonpath='{range .users[*]}{.name}{"\n"}{end}'
done
```

Then check the merged view:

```bash
kubectl config view \
  -o jsonpath='{range .users[*]}{.name}{"\n"}{end}' \
  | sort | uniq -c | sort -rn
```

If multiple files define the same user name, do not assume the newest file is being used.

## Inspect Without Leaking Tokens

Avoid dumping full kubeconfig content into tickets or chat. Extract only names and token age clues.

Useful checks:

```bash
for file in ${KUBECONFIG//:/ }; do
  echo "=== $file ==="
  kubectl config view --kubeconfig "$file" --raw \
    -o jsonpath='{range .users[?(@.name=="rancher")]}{.name}{"\n"}{end}'
done
```

If you need to compare token presence, print lengths or hashes, not values:

```bash
for file in ${KUBECONFIG//:/ }; do
  kubectl config view --kubeconfig "$file" --raw -o json \
    | python3 -c '
import hashlib,json,sys
d=json.load(sys.stdin)
for user in d.get("users",[]):
    if user.get("name") == "rancher":
        token=user.get("user",{}).get("token","")
        digest=hashlib.sha256(token.encode()).hexdigest()[:12] if token else "no-token"
        print("rancher", len(token), digest)
'
done
```

This proves whether files differ without exposing bearer tokens.

## Fix The Merge Collision

There are three safe fixes.

First, put the fresh file earlier in `KUBECONFIG`:

```bash
export KUBECONFIG="$PWD/new-rancher.yaml:$HOME/.kube/config"
kubectl config view --flatten > /tmp/merged-kubeconfig.yaml
```

Second, rename users so they are unique before merging. If you edit by hand or script, make the user and context names unique together:

```text
user: rancher-cluster-a
context: cluster-a-rancher
```

Third, replace the stale token in the file that currently wins the merge. This can be acceptable on a personal workstation, but record which file was changed and avoid copying token values into notes.

## Verify The Actual Contexts

After remediation, verify the contexts that were failing:

```bash
kubectl config get-contexts
kubectl --context cluster-a get nodes
kubectl --context cluster-b get namespaces
```

If one context works and another fails, repeat the duplicate-user check. Large workstation kubeconfig sets often mix downloaded files, flattened configs, and old cluster-specific exports.

## Operating Rule

When a standalone kubeconfig works but the merged config returns `system:unauthenticated`, suspect local merge order before changing cluster RBAC.

Do not start by editing ClusterRoles or Rancher permissions. Prove which token `kubectl` is actually sending.

## References

- [Kubernetes Configure Access To Multiple Clusters](https://kubernetes.io/docs/tasks/access-application-cluster/configure-access-multiple-clusters/)
- [DevOps/SRE Linux Workstation](/field-notes/devops-sre-linux-workstation/)
- [SRE Agent Kubernetes Log Access RBAC](/field-notes/sre-agent-kubernetes-log-access-rbac/)
