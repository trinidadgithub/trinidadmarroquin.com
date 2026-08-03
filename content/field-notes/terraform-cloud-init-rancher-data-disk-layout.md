+++
title = 'Terraform Cloud-Init Ownership For Rancher Data Disks'
date = 2026-07-16T00:00:00-05:00
draft = false
description = 'Field note for making Terraform and cloud-init own the second-disk layout for RKE2/Rancher workers: attach, partition, mount /var/lib/rancher, bind container logs, and verify after replacement.'
tags = ['terraform', 'vsphere', 'cloud-init', 'rke2', 'rancher', 'storage', 'operations']
categories = ['field-notes']
+++

Attaching a second vSphere disk is not the same as using it.

In one worker replacement, Terraform correctly attached a second disk to the VM, Packer correctly placed the static bootstrap entrypoint, and cloud-init completed. But the guest still showed the second disk as blank and unmounted:

```text
sda
  sda1  /boot/efi
  sda2  /
sdb     <blank>
```

The result was subtle: bootstrap succeeded, but `/var/lib/rancher` stayed on the operating-system disk. For an RKE2 node, that means Rancher/RKE2 state and container log growth can still fill `/` even though Terraform created a data disk.

## Ownership Boundary

Use this split:

- Packer places static bootstrap resources in the template.
- Terraform attaches the intended VM disks.
- Terraform-rendered cloud-init owns guest disk layout and mount behavior.
- Bootstrap runs after the mounts exist.
- RKE2 uses the mounted paths normally.

Do not expect the vSphere provider's `disk` block to partition, format, or mount anything inside the guest. It only changes VM hardware.

## Intended Layout

A clean RKE2 worker layout is:

```text
/dev/sda   operating system disk
/dev/sdb1  LABEL=rancher-data  mounted at /var/lib/rancher
```

Treat `/dev/sdb1` as an example, not a contract. In vSphere clones, Linux disk enumeration can differ between otherwise similar nodes. One worker may see the data disk as `/dev/sdb`, while another may see the root disk on `/dev/sdb` and the data disk on `/dev/sda`. The durable contract should be the filesystem label, UUID, or a discovery step that excludes the current root disk.

Keep OS logs on the OS disk. Put Rancher/Kubernetes-heavy logs on the Rancher data disk through bind mounts:

```text
/var/lib/rancher/log/pods        -> /var/log/pods
/var/lib/rancher/log/containers  -> /var/log/containers
```

That keeps noisy workload/container logs from consuming the root filesystem while avoiding a broad `/var/log` mount that can complicate OS debugging.

## Cloud-Init Shape

The Terraform-rendered userdata should describe the disk setup before it starts bootstrap. If disk naming is stable in your environment, cloud-init `disk_setup` can be enough:

```yaml
#cloud-config
ssh_pwauth: true
disable_root: true

disk_setup:
  /dev/sdb:
    table_type: gpt
    layout: true
    overwrite: false

fs_setup:
  - label: rancher-data
    filesystem: ext4
    device: /dev/sdb1
    overwrite: false

mounts:
  - [ "LABEL=rancher-data", "/var/lib/rancher", "ext4", "defaults,nofail", "0", "2" ]

runcmd:
  - [ bash, -lc, 'mkdir -p /run/sshd' ]
  - [ bash, -lc, 'mkdir -p /var/lib/rancher/log/pods /var/lib/rancher/log/containers /var/log/pods /var/log/containers' ]
  - [ bash, -lc, 'grep -qs " /var/log/pods " /etc/fstab || echo "/var/lib/rancher/log/pods /var/log/pods none bind,nofail 0 0" >> /etc/fstab' ]
  - [ bash, -lc, 'grep -qs " /var/log/containers " /etc/fstab || echo "/var/lib/rancher/log/containers /var/log/containers none bind,nofail 0 0" >> /etc/fstab' ]
  - [ bash, -lc, 'mountpoint -q /var/log/pods || mount /var/log/pods' ]
  - [ bash, -lc, 'mountpoint -q /var/log/containers || mount /var/log/containers' ]
  - [ bash, -lc, '/usr/local/bin/platform-bootstrap' ]
```

The important details are `overwrite: false` and running bootstrap after the mounts. The userdata is safe for fresh clones, but it is not a casual live-migration tool for existing nodes that already have data.

When disk naming is not stable, do not hard-code `/dev/sdb`. Use a boot-time helper that discovers the non-root disk, labels it, and mounts by label:

```bash
root_source="$(findmnt -n -o SOURCE /)"
root_parent="$(lsblk -no PKNAME "$root_source" | head -n1)"
root_disk="/dev/${root_parent}"
data_disk="$(lsblk -dn -o NAME,TYPE | awk '$2 == "disk" {print "/dev/" $1}' | grep -vx "$root_disk" | head -n1)"

if [ -z "$root_parent" ] || [ -z "$data_disk" ]; then
  echo "no non-root data disk found" >&2
  exit 1
fi

if ! blkid -L rancher-data >/dev/null 2>&1; then
  parted -s "$data_disk" mklabel gpt mkpart primary ext4 0% 100%
  partprobe "$data_disk"
  mkfs.ext4 -L rancher-data "${data_disk}1"
fi

mkdir -p /var/lib/rancher
grep -qs ' /var/lib/rancher ' /etc/fstab || \
  echo 'LABEL=rancher-data /var/lib/rancher ext4 defaults,nofail 0 2' >> /etc/fstab
mountpoint -q /var/lib/rancher || mount /var/lib/rancher
```

The helper should be idempotent: if `LABEL=rancher-data` already exists, it should not repartition anything. Bootstrap should still run after the mount exists.

Validate the cloud-init file before rebuilding nodes:

```bash
cloud-init schema --config-file templates/userdata.yaml
```

## Replacement Flow

For existing Kubernetes workers, prefer rolling replacement over in-place repartitioning:

```bash
kubectl cordon worker-5
kubectl drain worker-5 --ignore-daemonsets --delete-emptydir-data
kubectl delete node worker-5
```

Then replace only that VM through Terraform:

```bash
terraform plan \
  -target='module.vm_group.vsphere_virtual_machine.vm["worker5"]' \
  -replace='module.vm_group.vsphere_virtual_machine.vm["worker5"]' \
  -out=tfplan-replace-worker5-disklayout

terraform apply tfplan-replace-worker5-disklayout
```

Using `-target` should be intentional and temporary. It is useful during a controlled one-node replacement when you specifically want to avoid pushing userdata or template changes to unrelated existing VMs in the same run.

Before applying, inspect the saved plan and confirm the replacement scope:

```text
1 to add, 0 to change, 1 to destroy
only module.vm_group.vsphere_virtual_machine.vm["worker5"]
```

## Verification

After the VM boots, verify outside and inside the guest.

Terraform/vSphere state:

```bash
terraform state show 'module.vm_group.vsphere_virtual_machine.vm["worker5"]' \
  | grep -E 'default_ip_address|power_state|vmware_tools_status|template_uuid'
```

Expected external state:

```text
power_state          = "on"
vmware_tools_status  = "guestToolsRunning"
default_ip_address   = "192.0.2.25"
```

Guest checks:

```bash
cloud-init status --long
df -h
lsblk -f
findmnt /var/lib/rancher /var/log/pods /var/log/containers
cat /etc/fstab
sudo cat /var/lib/platform-bootstrap/status.json
```

Also verify the root disk and data disk are not the same device:

```bash
findmnt -n -o SOURCE /
findmnt -n -o SOURCE /var/lib/rancher
lsblk -f
blkid -L rancher-data
```

Healthy shape:

```text
/dev/sda2  /
/dev/sdb1  /var/lib/rancher
/dev/sdb1  /var/log/pods
/dev/sdb1  /var/log/containers
```

`findmnt` should show `/var/log/pods` and `/var/log/containers` as bind mounts backed by the Rancher data disk.

## Operating Rule

Do not stop at “Terraform attached the disk.”

For Rancher/RKE2 nodes, the acceptance test is that the guest mounted the data disk where RKE2 actually writes heavy state, cloud-init completed without errors, bootstrap ran after the mount existed, and container log paths cannot fill the OS disk during normal workload churn. Verify that on every worker; older nodes may still need live bind-mount correction even after the template is fixed for future clones.
