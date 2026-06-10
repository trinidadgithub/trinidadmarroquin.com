+++
title = 'iSCSI Bootstrap Readiness For Kubernetes Nodes'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note for preparing Kubernetes nodes with iSCSI networking, discovery, sessions, and CSI-ready storage behavior.'
tags = ['kubernetes', 'iscsi', 'storage', 'netplan', 'vsphere']
categories = ['field-notes']
+++

A Kubernetes node can be storage-ready before any new disk appears in `lsblk`. With CSI-backed storage, the disk appears only after the array maps a LUN to the node.

## Target State

For a node with primary and iSCSI networks:

```text
ens192  -> service network, default route, DNS
iscsi01 -> 169.253.0.x/24
iscsi02 -> 169.253.1.x/24
```

The node should have:

- deterministic netplan.
- reachable storage portals.
- `open-iscsi` installed and enabled.
- an initiator name.
- successful target discovery.
- persistent iSCSI node startup.

## Verify Network First

```bash
ip -br addr
ip route
ping -c 3 169.253.0.11
ping -c 3 169.253.1.11
```

If portal pings fail, stop and fix networking before touching iSCSI.

## Install And Enable iSCSI

```bash
sudo apt-get update
sudo apt-get install -y open-iscsi
sudo systemctl enable --now iscsid
sudo systemctl enable --now open-iscsi
```

Check the service:

```bash
systemctl status iscsid --no-pager
```

## Initiator Name

Check the current initiator:

```bash
cat /etc/iscsi/initiatorname.iscsi
```

Regenerate if needed:

```bash
sudo cp -a /etc/iscsi/initiatorname.iscsi /var/tmp/initiatorname.iscsi.backup.$(date +%F-%H%M%S) 2>/dev/null || true
echo "InitiatorName=$(sudo /sbin/iscsi-iname)" | sudo tee /etc/iscsi/initiatorname.iscsi
sudo systemctl restart iscsid
```

## Discover And Login

Discover targets:

```bash
sudo iscsiadm -m discovery -t sendtargets -p 169.253.0.11
sudo iscsiadm -m discovery -t sendtargets -p 169.253.1.11
```

Login to all discovered nodes:

```bash
sudo iscsiadm -m node --login
```

Make sessions persistent:

```bash
sudo iscsiadm -m node -o update -n node.startup -v automatic
```

Verify:

```bash
sudo iscsiadm -m session
sudo iscsiadm -m session -P 3 | grep -i 'Attached scsi disk' || true
lsblk
```

## Why No Disk May Appear Yet

If sessions exist but `lsblk` shows no new disk, that can be correct.

CSI flow:

```text
PVC created
CSI asks array to create volume
array maps LUN to node IQN
node sees disk
kubelet mounts volume for pod
```

Before the array maps a LUN, the node can be connected to the array but have no new block device.

## Bootstrap Pattern

For data centers with iSCSI arrays, make this opt-in through environment values:

```bash
ENABLE_ISCSI=true
ISCSI_PORTALS="169.253.0.11 169.253.1.11"
ISCSI_TARGET_IQN="iqn.2007-11.com.nimblestorage:austin-g5f6a0959b70c5587"
ENABLE_MULTIPATH=false
```

Then run the storage stage before any bootstrap step that expects attached storage devices.

## Operating Model

- Bootstrap prepares the node for storage.
- CSI owns volume creation and LUN mapping.
- The array remains the authority for volume lifecycle.
- Kubernetes consumes the resulting devices through the CSI workflow.
