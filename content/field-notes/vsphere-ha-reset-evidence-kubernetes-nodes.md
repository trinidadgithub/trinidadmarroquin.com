+++
title = 'vSphere HA Reset Evidence For Kubernetes Nodes'
date = 2026-08-05T00:00:00-05:00
draft = false
description = 'Field note for distinguishing vSphere HA resets from in-guest Kubernetes node reboots by correlating boot IDs, kernel activation, auth logs, Kubernetes events, and vCenter task/event history.'
tags = ['vsphere', 'vmware', 'kubernetes', 'rke2', 'incident-response', 'operations']
categories = ['field-notes']
+++

When Kubernetes nodes reboot during a storage incident, the cause matters. An in-guest reboot, a Rancher/system-upgrade action, a human SSH session, and a vSphere HA reset all have different follow-up work.

The useful pattern is to prove the reboot from multiple layers before assigning cause.

## Start With Kubernetes

Check node readiness, boot ID, kernel, and recent events:

```bash
kubectl get nodes -o wide
kubectl describe node cp-1 | grep -A5 -E 'Conditions:|Events:'
kubectl get events -A --sort-by=.lastTimestamp | grep -i 'reboot\|node'
kubectl get node cp-1 -o jsonpath='{.status.nodeInfo.bootID}{"\n"}{.status.nodeInfo.kernelVersion}{"\n"}'
```

Kubernetes can tell you that a node rebooted. It usually cannot tell you why.

If two control-plane nodes reboot at nearly the same timestamp, treat that as a high-signal clue. Simultaneous reboots are less likely to be a random operator SSH command on each node.

## Check The Guest

On each affected node, compare current and previous boots:

```bash
uptime -s
cat /proc/sys/kernel/random/boot_id
journalctl --list-boots
journalctl -b -1 -n 300 --no-pager
```

Look for a clean shutdown path:

```bash
journalctl -b -1 --no-pager \
  | grep -Ei 'systemctl reboot|shutdown|poweroff|reboot:|Reached target.*Shutdown|Stopped target'
```

Check whether a human session issued the reboot:

```bash
last -x | head -30
journalctl -b -1 _COMM=sudo --no-pager
journalctl -b -1 --no-pager | grep -Ei 'sudo|session opened|reboot|shutdown|poweroff'
```

If the previous boot lacks a clean shutdown sequence, that points away from a normal in-guest reboot and toward reset, power loss, host failure, or HA action.

## Check Package And Upgrade Paths

A reboot into a newer kernel does not prove the kernel was installed at that moment. The kernel may have been installed earlier and only activated by the reset.

Check package logs and upgrade controllers:

```bash
grep -Ei 'install|upgrade|linux-image|kernel' /var/log/apt/history.log /var/log/dpkg.log
kubectl -n system-upgrade get plans,pods,jobs -o wide
kubectl -n system-upgrade logs deploy/system-upgrade-controller --since=6h
```

If there is no matching upgrade job and no package install near the reboot, keep looking.

## Check vCenter Task And Event History

Query visible power/reset tasks first:

```bash
govc tasks -json -b=6h -n=500 \
  | jq -r '.Tasks[]? | select((.DescriptionId // "") | test("Power|power|Reset|reset|Shutdown|Standby")) | [
      .StartTime,
      .CompleteTime,
      .State,
      .DescriptionId,
      (.EntityName // ""),
      (.Reason.UserName // ""),
      .Key
    ] | @tsv'
```

Then inspect VM events:

```bash
govc events -vm '/DC-Site-A/vm/K8s-Cluster/cluster-a-cp-1' -n=100
```

Useful event phrases include:

```text
vSphere HA restarted this virtual machine
VMware Tools heartbeat failure
reset
powered on
migrating
```

If vCenter events show an HA reset due to VMware Tools heartbeat failure, and guest logs lack a clean shutdown, classify it as an infrastructure reset, not a human or Kubernetes upgrade action.

## Watch The Side Effects

A reset can undo an intentional maintenance shape. For example, a rebooted control-plane node may briefly allow paused controller pods to run again if the pause depended on node state, scheduling, or a just-deleted pod.

After a HA reset, recheck:

```bash
kubectl get nodes -o wide
kubectl -n vmware-system-csi get pods -o wide
kubectl describe nodes | grep -A3 '^Taints:'
kubectl get events -A --sort-by=.lastTimestamp | tail -50
```

If a storage controller was intentionally paused, verify that it is still paused. If it briefly restarted, check whether it submitted new vCenter CNS tasks before re-pausing it.

## Operating Rule

Do not stop at “the node rebooted.” Prove whether the reboot came from the guest, Kubernetes/Rancher automation, vCenter task history, or vSphere HA.

The classification changes the fix: upgrade cleanup, user-process review, host/HA investigation, or storage-controller containment.
