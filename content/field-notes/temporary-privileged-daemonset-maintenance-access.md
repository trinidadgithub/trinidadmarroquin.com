+++
title = 'Temporary Privileged DaemonSets Are Host Access Changes'
date = 2026-07-23T00:00:00-05:00
draft = false
description = 'A Kubernetes maintenance field note on using temporary privileged DaemonSets for host access, including authorization, scope, cleanup, and negative verification.'
tags = ['kubernetes', 'rke2', 'security', 'maintenance', 'operations']
categories = ['field-notes']
+++

Sometimes the maintenance path is blocked by host access, not Kubernetes health.

In one RKE2 reboot window, SSH worked to the nodes, but noninteractive sudo did not. The maintenance automation needed to reboot hosts and verify node-level state. The workaround was a temporary privileged DaemonSet that wrote a short-lived sudoers rule onto each node, then stayed alive only long enough for the maintenance window.

That pattern can be valid in a controlled emergency or tightly scoped window. It is also a host access change. Treat it with the same seriousness as adding an SSH key, changing a sudoers file, or granting a break-glass account.

## What The Pattern Does

The mechanism is simple:

```text
privileged DaemonSet
hostPath mount to the host filesystem
container writes a temporary host access rule
operator verifies noninteractive access
maintenance runs
operator removes the host rule
operator deletes the DaemonSet
operator verifies access is gone
```

The Kubernetes object is only the delivery mechanism. The real change is on every host where the DaemonSet schedules.

## Pre-Checks

Before applying anything, prove the current state:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o wide
kubectl -n kube-system get daemonset
```

Then check host access explicitly:

```bash
ssh ops-user@192.0.2.10 'true'
ssh ops-user@192.0.2.10 'sudo -n whoami'
```

Record the expected result. If `sudo -n` fails before the helper and succeeds after the helper, you can prove the helper changed access. If you skip the negative pre-check, you cannot prove what changed.

## Scope The Blast Radius

Do not apply a host-mutating DaemonSet casually to the entire cluster.

Decide up front:

- which nodes need the access.
- whether storage nodes should be excluded.
- whether control-plane nodes and worker nodes need different windows.
- how long the helper is allowed to exist.
- who approved the access change.
- where the cleanup evidence will be stored.

If the helper must run broadly, keep the window short and make cleanup a required step, not a follow-up ticket.

## Avoid Copy-Paste Blindness

A helper like this usually needs powerful settings:

```yaml
securityContext:
  privileged: true
volumes:
  - name: host-etc
    hostPath:
      path: /etc
```

Those two lines mean the pod can modify host configuration. The review question is not “does the YAML apply?” The review question is “are we intentionally allowing a Kubernetes workload to mutate host access control?”

Use a unique, temporary file name under `/etc/sudoers.d/` or the equivalent access-control location for the operating system. Do not edit the main sudoers file in place. Set restrictive permissions. Make the cleanup command remove only the file the helper created.

## Verify Positive Access

After rollout, verify both Kubernetes and host behavior:

```bash
kubectl -n kube-system rollout status daemonset/temporary-host-access --timeout=5m
kubectl -n kube-system get pods -l app=temporary-host-access -o wide
ssh ops-user@192.0.2.10 'sudo -n whoami'
```

The evidence should show:

```text
helper scheduled on intended nodes
noninteractive sudo works on intended nodes
non-target nodes were not modified or were intentionally included
```

If the helper does not schedule on a node, do not assume that node has access. If a node is tainted, cordoned, or unreachable, verify it separately.

## Run Maintenance, Then Clean Up Immediately

The helper exists to support the maintenance action. It should not outlive that action.

Closeout should remove both layers:

```text
remove host access file from every touched node
delete the DaemonSet
wait for DaemonSet pods to disappear
verify noninteractive sudo fails again
```

The negative verification matters:

```bash
ssh ops-user@192.0.2.10 'sudo -n whoami'
```

Expected result after cleanup:

```text
sudo: a password is required
```

Do not stop at `kubectl delete daemonset`. Deleting the DaemonSet removes the delivery pod. It does not prove the host file was removed.

## Evidence To Keep

Retain a small evidence bundle:

- pre-helper `sudo -n` failure.
- helper rollout status.
- post-helper `sudo -n` success on intended nodes.
- maintenance logs.
- host access file removal output.
- DaemonSet deletion or `NotFound` confirmation.
- post-cleanup `sudo -n` failure.

Redact hostnames, IPs, usernames, file names, and cluster names before sharing outside the operations boundary.

## Stop Criteria

Stop and reassess if:

- the helper schedules on unexpected nodes.
- the helper cannot be removed from a node.
- sudo remains passwordless after cleanup.
- a node is unreachable during cleanup.
- the DaemonSet uses broader host mounts than required.
- the access change was not explicitly approved for the window.

The most dangerous failure mode is a successful maintenance window with forgotten elevated access left behind.

## The Rule

A temporary privileged DaemonSet is not just Kubernetes automation. It is a distributed host mutation.

Use it only when the operational need is clear, keep it scoped to the maintenance window, and prove both sides of the change:

```text
before: access does not exist
during: access exists only where intended
after: access is gone
```

That final negative check is what turns a risky workaround into a controlled operational procedure.
