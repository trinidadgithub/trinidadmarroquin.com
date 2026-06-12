+++
title = 'vSphere Guestinfo And Cloud-Init On Cloned VMs'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note for verifying Terraform guestinfo userdata, cloud-init state, and first-boot behavior on vSphere Ubuntu clones.'
tags = ['vsphere', 'cloud-init', 'terraform', 'packer']
categories = ['field-notes']
+++

Terraform can inject cloud-init data into vSphere clones through VMware guestinfo keys. That only works if the template is built to let cloud-init run on first boot.

## Symptom

Terraform creates or replaces the VM, but the expected `userdata.yaml` behavior does not happen. Bootstrap does not run, SSH is not configured, or `/var/log/platform-bootstrap.log` is missing.

## Check Guestinfo From vSphere

Use `govc` to inspect the VM extra config:

```bash
source govc.env
govc vm.info -e /DC-Site-A/vm/K8s-Cluster/OpsTools/cluster-a-api-lb-01 \
  | grep 'guestinfo\|disk.enableUUID'
```

Look for keys like:

```text
guestinfo.metadata
guestinfo.metadata.encoding
guestinfo.userdata
guestinfo.userdata.encoding
guestinfo.network-config
guestinfo.network-config.encoding
```

If the keys are not present, Terraform did not inject them. Check whether the environment is still using a root-level `vsphere_virtual_machine` resource instead of the shared module.

## Check Cloud-Init In The Guest

From the VM console or SSH:

```bash
cloud-init status --long
sudo tail -n 200 /var/log/cloud-init.log
sudo tail -n 200 /var/log/cloud-init-output.log
```

If cloud-init is disabled, you may see:

```text
status: disabled
detail: cloud-init disabled by cloud-init-generator
```

In that state, guestinfo can be present but ignored.

## Template Requirements

The Packer-built template should have:

- `cloud-init` installed.
- `open-vm-tools` installed.
- no `/etc/cloud/cloud-init.disabled` file.
- cloud-init services enabled for cloned VMs.
- instance state cleaned before templating.
- VMware datasource available.

Useful template checks:

```bash
ls -l /etc/cloud/cloud-init.disabled
systemctl is-enabled cloud-init-local cloud-init cloud-config cloud-final
systemctl is-enabled open-vm-tools
```

Before sealing the template:

```bash
sudo rm -f /etc/cloud/cloud-init.disabled
sudo cloud-init clean --logs --machine-id
sudo truncate -s 0 /etc/machine-id
sudo systemctl enable cloud-init-local cloud-init cloud-config cloud-final open-vm-tools
sudo shutdown -h now
```

## Terraform Pattern

In the module, guestinfo injection usually looks like this:

```hcl
extra_config = {
  "guestinfo.userdata" = base64encode(
    templatefile("${var.template_path}/userdata.yaml", {
      name         = each.value.name
      ssh_username = var.ssh_username
      public_key   = var.public_key
      admin_password = var.admin_password
    })
  )
  "guestinfo.userdata.encoding" = "base64"
}
```

## Caution

Do not test first-boot cloud-init behavior by enabling cloud-init on an already-customized clone unless the VM is disposable. Cloud-init may re-run identity, user, or network steps and break access.

Fix the template, replace the test VM, and verify from logs.
