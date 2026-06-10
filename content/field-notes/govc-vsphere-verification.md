+++
title = 'govc Commands For vSphere VM Verification'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note with govc commands for finding VMs, checking NIC backing, guestinfo keys, and comparing working versus broken vSphere clones.'
tags = ['govc', 'vsphere', 'vmware', 'terraform']
categories = ['field-notes']
+++

`govc` is useful when Terraform says one thing and the VM behaves like something else. It gives a direct view into vSphere inventory, VM paths, NIC backing, and extra config.

## Load Environment

Use a clearly named helper file, not `vars.env` if it is only for `govc`:

```bash
source govc.env
govc about
```

Typical values:

```bash
export GOVC_URL='vcenter.example.com'
export GOVC_USERNAME='administrator@vsphere.local'
export GOVC_PASSWORD='...'
export GOVC_INSECURE=1
export GOVC_DATACENTER='VC-Austin'
```

## Find A VM Path

Search by VM name:

```bash
govc find / -type m -name 'AUS-1-wrkr-12-uat'
```

Example result:

```text
/VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-12-uat
```

Use that full path for later commands.

## Check NIC Backing

```bash
govc device.ls -vm /VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-12-uat
```

Example useful output:

```text
ethernet-0 VirtualVmxnet3 VLAN 232 k8s-UAT
ethernet-1 VirtualVmxnet3 iscsi test 1
ethernet-2 VirtualVmxnet3 iscsi test 2
```

Compare with a known-good neighbor:

```bash
govc device.ls -vm /VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-11-uat
govc device.ls -vm /VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-12-uat
```

This catches a common failure: the VM has a UAT IP address but is attached to an Internal VLAN port group.

## Inspect Extra Config

```bash
govc vm.info -e /VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-12-uat \
  | grep -i 'guestinfo\|ethernet\|disk.enableUUID'
```

Useful keys:

```text
guestinfo.userdata
guestinfo.userdata.encoding
guestinfo.metadata
guestinfo.network-config
disk.enableUUID
ethernet0.pciSlotNumber
```

## Connect A NIC Manually

For one-off repair while debugging:

```bash
govc device.connect -vm /VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-12-uat ethernet-0
```

Prefer fixing the template or Terraform config after confirming the cause.

## When To Use This

Use `govc` when:

- the guest cannot reach its gateway.
- Terraform `vm_network` looks correct but the VM is on the wrong port group.
- guestinfo userdata does not appear to run.
- you need to compare a broken clone against a working neighbor.
- you need the canonical vSphere VM path for troubleshooting commands.

`govc` is especially useful because it verifies what vCenter actually did, not what Terraform intended.
