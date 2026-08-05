+++
title = 'vSphere CD-ROM Host Device Cleanup With govc'
date = 2026-08-05T00:00:00-05:00
draft = false
description = 'Field note for auditing and cleaning up vSphere VM CD-ROM devices that remain backed by Host Device instead of Client Device, including govc limits around powered-on VMs.'
tags = ['vsphere', 'vmware', 'govc', 'vcenter', 'operations']
categories = ['field-notes']
+++

A connected or host-backed virtual CD-ROM can become operational noise during VM maintenance. It can trigger device-lock prompts, confuse vMotion or storage work, and leave operators answering vCenter questions that have nothing to do with the actual change. If the VM is already locked by storage or vMotion tasks, clear the task contention first; see [vSphere CSI CNS ExtendVolume Triage](/field-notes/vsphere-csi-cns-extendvolume-triage/).

For long-lived Kubernetes nodes and platform VMs, a CD-ROM is often unnecessary after provisioning. If one remains, it should be either disconnected as a client device or removed intentionally.

## Audit The Device

Find the target VMs, then inspect CD-ROM state:

```bash
govc find /DC-Site-A/vm/K8s-Cluster/NonProd -type m | while read -r vm; do
  echo "VM: $vm"
  govc device.info -vm "$vm" 'cdrom-*' 2>/dev/null \
    | awk '/^Name:|Label:|Summary:|Connected:|Start connected:/ { print "  " $0 }' \
    || echo "  No CD-ROM device"
done
```

Useful states:

```text
Remote ATAPI  -> Client Device
ATAPI ...     -> Host Device or host-backed CD-ROM
Connected     -> whether the device is currently connected
Start connected -> whether it reconnects on boot
```

The goal for an unused CD-ROM is either:

```text
No CD-ROM device
```

or:

```text
Summary:          Remote ATAPI
Connected:        false
Start connected:  false
```

## Try The Non-Destructive Path First

For a VM that still has a CD-ROM, eject and disconnect the specific device:

```bash
vm='/DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-01'

cdrom="$(govc device.info -vm "$vm" 'cdrom-*' \
  | awk '/^Name:/ { name=$2 } /Label: *CD\/DVD drive 1/ { print name; exit }')"

timeout 20s govc device.cdrom.eject -vm "$vm" -device "$cdrom" || true
govc vm.question -vm "$vm" -answer=0 >/dev/null 2>&1 || true

timeout 20s govc device.disconnect -vm "$vm" "$cdrom" || true
govc vm.question -vm "$vm" -answer=0 >/dev/null 2>&1 || true

govc device.info -vm "$vm" "$cdrom" \
  | awk '/^Name:|Label:|Summary:|Connected:|Start connected:/ { print }'
```

`govc vm.question` is useful because vCenter may ask whether it should override a device lock. Answer only the expected device question; do not blindly answer unrelated VM prompts in a broad loop without inspecting the result.

## Know The govc Limitation

Some VMs have CD-ROM devices on an AHCI/SATA controller. In some `govc` builds, `govc device.cdrom.add` can only add a CD-ROM to an IDE controller. vSphere may also refuse to hot-add an IDE CD-ROM to a powered-on VM.

That means this sequence can be unsafe if run casually against powered-on VMs:

```text
remove AHCI CD-ROM
attempt govc device.cdrom.add
add fails because only IDE is supported or hot-add is blocked
VM is left with no CD-ROM device
```

That final state may be acceptable if CD-ROMs are not required. It is not acceptable if the runbook expected to replace the device immediately.

## Choose The Desired End State

For server VMs that do not need virtual media, no CD-ROM is usually cleaner than a host-backed device. Verify and record that choice:

```bash
govc find /DC-Site-A/vm/K8s-Cluster/NonProd -type m | while read -r vm; do
  if govc device.info -vm "$vm" 'cdrom-*' >/dev/null 2>&1; then
    echo "HAS CDROM: $vm"
  else
    echo "NO CDROM:  $vm"
  fi
done
```

If the VM must keep a CD-ROM and `govc` cannot hot-add the desired client-device backing, repair it during a maintenance window while the VM is powered off, or use a vSphere UI/API path that can add the correct controller/device type safely.

## Maintenance Repair Pattern

For VMs where a CD-ROM must exist and power-off is acceptable:

```bash
vm='/DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-01'

govc vm.power -off "$vm"
govc device.cdrom.add -vm "$vm"

cdrom="$(govc device.info -vm "$vm" 'cdrom-*' \
  | awk '/^Name:/ { print $2; exit }')"

govc device.disconnect -vm "$vm" "$cdrom" || true
govc vm.power -on "$vm"

govc device.info -vm "$vm" 'cdrom-*' \
  | awk '/^Name:|Label:|Summary:|Connected:|Start connected:/ { print }'
```

Do this only with normal VM maintenance controls: workload drain if the VM is a Kubernetes node, expected boot validation, and rollback criteria.

## Operating Rule

Do not treat virtual CD-ROM cleanup as harmless inventory polish.

Audit first, decide whether the desired state is “client device disconnected” or “no CD-ROM,” and understand whether your `govc` version can add the replacement device to a powered-on VM before removing anything.
