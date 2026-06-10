+++
title = 'Terraform vSphere Clone Customization Failures'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note for diagnosing Terraform vSphere clone failures caused by VMware guest customization inside the VM.'
tags = ['terraform', 'vsphere', 'vmware', 'packer']
categories = ['field-notes']
+++

Terraform can successfully ask vSphere to clone a VM and still fail during guest customization. In that case, the problem is usually inside the guest/template, not Terraform syntax.

## Symptom

Terraform reports an error like:

```text
Virtual machine customization failed
An error occurred while customizing VM ...
For details reference the log file /var/log/vmware-imc/toolsDeployPkg.log in the guest OS.
```

Terraform may leave the VM in place to help troubleshooting.

## First Checks

From the VM console or SSH if available:

```bash
sudo tail -n 200 /var/log/vmware-imc/toolsDeployPkg.log
sudo tail -n 200 /var/log/cloud-init.log
sudo tail -n 200 /var/log/cloud-init-output.log
systemctl status open-vm-tools --no-pager
```

Check VMware tools:

```bash
which vmtoolsd
vmware-toolbox-cmd -v
systemctl status open-vm-tools --no-pager
```

## Common Template Issues

- `open-vm-tools` is missing or not running.
- `hwclock` is missing on Ubuntu/Debian templates.
- cloud-init state was not cleaned before templating.
- SSH or network services are disabled in the template.
- vSphere customization and cloud-init are competing for the same network settings.

For Ubuntu templates, `hwclock` is provided by `util-linux-extra`:

```bash
sudo apt-get update
sudo apt-get install -y util-linux-extra open-vm-tools
command -v hwclock
```

## Retry Safely

For current Terraform versions, prefer `-replace` for a failed test VM:

```bash
terraform apply -replace='vsphere_virtual_machine.vm["lb1"]'
```

If the VM is managed inside a module:

```bash
terraform apply -replace='module.vm_group.vsphere_virtual_machine.vm["lb1"]'
```

## Verify The Plan

Before applying, save and inspect the plan:

```bash
terraform plan -out=tfplan
terraform show -no-color tfplan > plan.txt
grep -n "must be replaced\|forces replacement" plan.txt
```

Do not assume a replacement is safe just because the VM is a worker. Check the resource key, name, folder, datastore, network, and disks.

## Operating Model

- Packer should fix template defects.
- Terraform should clone and customize from a known-good template.
- vSphere guest customization should own only the settings you intentionally use it for.
- Bootstrap should handle guest configuration that must vary by environment.

If Terraform clone customization fails, get the guest logs before deleting the VM. They usually explain the real failure.
