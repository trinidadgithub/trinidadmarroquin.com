+++
title = 'Ubuntu Unattended Upgrades Are Kubernetes Node Changes'
date = 2026-07-20T00:00:00-05:00
draft = false
description = 'A Kubernetes operations article on why Ubuntu unattended upgrades should be disabled on production nodes and replaced with controlled patch windows, especially when systemd, udev, iSCSI, multipath, and CSI storage are involved.'
tags = ['ubuntu', 'kubernetes', 'rke2', 'updates', 'iscsi', 'multipath', 'csi', 'operations']
categories = ['notes']
+++

Ubuntu unattended upgrades are useful on ordinary servers and workstations. On Kubernetes nodes, they are production changes.

That distinction matters because a Kubernetes worker is not just a Linux host. It is part of a larger control loop that includes kubelet, the container runtime, CNI, CSI, storage paths, systemd units, udev device handling, and sometimes iSCSI or multipath. A package update that is safe in isolation can become disruptive when it lands outside a maintenance window.

## The Failure Pattern

The incident pattern looks like this:

```text
unattended-upgrades starts during normal operations
core OS packages change
systemd, udev, or device-management triggers run
storage or network services churn
iSCSI / multipath / block-device handling stalls or resets
CSI node plugin loses registration or stops responding
kubelet volume operations fail on the node
the node becomes degraded or NotReady
```

The exact package list varies, but updates to components such as `systemd`, `udev`, `libudev`, `libsystemd`, PAM/NSS systemd libraries, or kernel-adjacent packages deserve special attention. They participate in process supervision, device events, service restart behavior, and block-device discovery.

That is the same control plane that Kubernetes storage relies on.

## Why Storage Nodes Are Sensitive

Kubernetes storage paths are layered:

```text
application pod
kubelet volume manager
CSI node plugin
filesystem mount
block device
multipath / iSCSI / storage network
array target
```

If device handling stalls under `udev`, if multipath commands block, or if iSCSI sessions churn, kubelet does not see that as a neat package-update event. It sees mount operations timing out, CSI calls failing, plugin sockets disappearing, or volumes that cannot detach cleanly.

The most important diagnostic line in this class of incident is usually not "package upgraded". It is a kubelet or event message like:

```text
driver name csi.example.com not found in the list of registered CSI drivers
```

That means the failure crossed a boundary. It is no longer just storage noise. Kubelet has lost the node-local storage interface it needs to manage volumes.

## Correlation Evidence To Collect

When investigating a node that went `NotReady` after unattended upgrades, collect the timeline before rebooting if possible.

Start with unattended-upgrades:

```bash
sudo journalctl -u unattended-upgrades \
  --since "2026-07-20 06:00" \
  --until "2026-07-20 08:00" \
  --no-pager

sudo grep -h "Packages that will be upgraded" \
  /var/log/unattended-upgrades/unattended-upgrades.log*

sudo less /var/log/unattended-upgrades/unattended-upgrades-dpkg.log
```

Then check the host services and kernel around the same window:

```bash
sudo journalctl --since "2026-07-20 06:00" --until "2026-07-20 08:00" --no-pager | \
  grep -Ei 'apt|unattended|systemd|udev|iscsi|multipath|containerd|kubelet'

sudo journalctl -k --since "2026-07-20 06:00" --until "2026-07-20 08:00" --no-pager | \
  grep -Ei 'scsi|reset|lun|multipath|iscsi|blk|i/o|timeout|hung|blocked'
```

From Kubernetes, correlate node and volume symptoms:

```bash
kubectl describe node worker-1
kubectl get events -A --sort-by=.lastTimestamp | \
  grep -Ei 'worker-1|FailedMount|NodeNotReady|KubeletNotReady|CSI|VolumeFailed'
```

The strongest case is a timeline where unattended upgrades begin, core device or service packages are installed, udev or systemd activity increases, storage paths churn, and kubelet then reports CSI or mount failures on the same node.

## Disable Automation, Not Patching

The fix is not to stop patching Ubuntu nodes. The fix is to stop patching them silently.

For production Kubernetes nodes, prefer this posture:

```text
unattended-upgrades disabled
apt timers disabled or masked
package changes scheduled in maintenance windows
nodes cordoned and drained before disruptive updates
reboots handled intentionally
post-update checks required before uncordon
```

Disabling unattended upgrades does create a responsibility: the platform team must own patch cadence. That is still safer than letting a node restart services or touch device-management packages while stateful workloads are running.

## Manual Node Patch Pattern

Use the normal Kubernetes maintenance flow:

```bash
kubectl cordon worker-1
kubectl drain worker-1 --ignore-daemonsets --delete-emptydir-data
```

Patch the host:

```bash
sudo apt update
apt list --upgradable
sudo NEEDRESTART_MODE=a apt upgrade -y

if [ -f /var/run/reboot-required ]; then
  sudo reboot
fi
```

After the node returns:

```bash
kubectl get node worker-1 -o wide
kubectl describe node worker-1
kubectl uncordon worker-1
```

For storage-backed clusters, add checks for the node-local storage stack:

```bash
sudo iscsiadm -m session
sudo multipath -ll
sudo journalctl -u kubelet -n 100 --no-pager
```

The point is sequencing. Update one node or one controlled batch at a time, with a clear stop condition if storage, CSI, CNI, or kubelet health degrades.

## Operational Rule

Treat Ubuntu package updates on Kubernetes nodes like cluster changes, not background hygiene.

That means they need:

- inventory scope.
- maintenance windows.
- drain and uncordon steps.
- pre-checks for CSI, CNI, and node readiness.
- post-checks for storage sessions, kubelet, and workload recovery.
- audit output showing which nodes were updated and which still need attention.

For the companion audit and disable pattern, see [Disabling Ubuntu Unattended Upgrades On Kubernetes Nodes](/field-notes/ubuntu-unattended-upgrades-kubernetes-nodes/).
