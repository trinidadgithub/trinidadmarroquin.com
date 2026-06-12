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
export GOVC_DATACENTER='DC-Site-A'
```

## Find A VM Path

Search by VM name:

```bash
govc find / -type m -name 'cluster-a-worker-02'
```

Example result:

```text
/DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-02
```

Use that full path for later commands.

## Check NIC Backing

```bash
govc device.ls -vm /DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-02
```

Example useful output:

```text
ethernet-0 VirtualVmxnet3 VLAN 232 k8s-nonprod
ethernet-1 VirtualVmxnet3 iscsi test 1
ethernet-2 VirtualVmxnet3 iscsi test 2
```

Compare with a known-good neighbor:

```bash
govc device.ls -vm /DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-01
govc device.ls -vm /DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-02
```

This catches a common failure: the VM has a nonproduction IP address but is attached to the wrong port group.

## Inspect Extra Config

```bash
govc vm.info -e /DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-02 \
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
govc device.connect -vm /DC-Site-A/vm/K8s-Cluster/NonProd/cluster-a-worker-02 ethernet-0
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
