+++
title = 'Packer SSH Disconnects From Service Restarts'
date = 2026-09-17T00:00:00-05:00
draft = false
description = 'Field note for diagnosing Packer shell provisioner SSH disconnects caused by open-vm-tools, openssh-server, and package maintainer service restarts during vSphere Ubuntu template builds.'
tags = ['packer', 'vsphere', 'ubuntu', 'ssh', 'cloud-init', 'operations']
categories = ['field-notes']
+++

`expect_disconnect` is useful, but it is not a broom.

When a Packer `vsphere-iso` build fails with `Script disconnected unexpectedly`, the important question is whether the command already completed before SSH dropped. If the command was interrupted mid-package-install, telling Packer to expect the disconnect can turn a real partial install into a green build step.

## Symptom

The build reaches a shell provisioner and fails after cloud-init finishes:

```text
Provisioning with shell script: /tmp/packer-shell123456789
Cloud-init finished...
Synchronizing state of open-vm-tools.service with SysV service script...
Executing: /usr/lib/systemd/systemd-sysv-install enable open-vm-tools
Script disconnected unexpectedly.
```

The template may build successfully in one vSphere environment and fail in another because network convergence and VMXNET3 behavior differ by host, port group, or timing. Do not assume the template is safe just because a sibling environment happened to tolerate the restart.

## Identify The Disruptive Command

Start by splitting the provisioner mentally into commands that can affect the active SSH path:

```hcl
provisioner "shell" {
  inline = [
    "while [ ! -f /var/lib/cloud/instance/boot-finished ]; do sleep 1; done",
    "sudo systemctl enable --now open-vm-tools",
    "sudo apt-get update",
    "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y cloud-init open-vm-tools openssh-server lvm2 xfsprogs parted",
    "sudo systemctl enable cloud-init-local.service cloud-init.service cloud-config.service cloud-final.service",
  ]
}
```

The risky lines are:

```text
systemctl enable --now open-vm-tools
apt-get install ... openssh-server ...
```

Starting `open-vm-tools` can cause VMware Tools to re-evaluate guest networking. Installing or upgrading `openssh-server` can restart SSH. Either can drop Packer's communicator.

## Split Expected Disconnects Into Their Own Provisioner

If starting VMware Tools drops SSH after the command completes, isolate that operation:

```hcl
provisioner "shell" {
  inline = [
    "while [ ! -f /var/lib/cloud/instance/boot-finished ]; do echo 'Waiting for cloud-init...'; sleep 1; done",
    "echo 'Cloud-init finished.'",
  ]
}

provisioner "shell" {
  expect_disconnect = true
  inline = [
    "sudo systemctl enable --now open-vm-tools",
  ]
}

provisioner "shell" {
  pause_before = "10s"
  inline = [
    "echo 'SSH reconnected after open-vm-tools start.'",
  ]
}
```

Do not leave unrelated package installs after the risky command in the same inline array. If SSH drops, Packer may not run the remaining commands.

## Prevent Package Maintainer Restarts

If the disconnect happens during `apt-get install`, avoid treating that as success. The package manager may have been killed mid-install, leaving required binaries missing.

A safer pattern is to block service starts and restarts during the install, then enable services explicitly afterward:

```hcl
provisioner "shell" {
  inline = [
    "set -euo pipefail",
    "printf '#!/bin/sh\nexit 101\n' | sudo tee /usr/sbin/policy-rc.d >/dev/null",
    "sudo chmod 0755 /usr/sbin/policy-rc.d",
    "sudo apt-get update",
    "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y cloud-init open-vm-tools openssh-server lvm2 xfsprogs parted",
    "sudo rm -f /usr/sbin/policy-rc.d",
    "sudo systemctl enable cloud-init-local.service cloud-init.service cloud-config.service cloud-final.service",
    "sudo systemctl enable ssh.service open-vm-tools.service",
  ]
}
```

On Debian and Ubuntu, a `policy-rc.d` exit code of `101` tells maintainer scripts that service starts are not allowed. That lets package installation finish without restarting SSH underneath Packer.

Always remove `policy-rc.d` after the controlled install phase. It is a build-time guardrail, not template runtime policy.

## Validate The Package Outcome

Follow package installation with a validation stage. Check the actual binaries later bootstrap steps depend on:

```hcl
provisioner "shell" {
  inline = [
    "set -euo pipefail",
    "test -x /usr/bin/cloud-init",
    "test -x /usr/sbin/sshd",
    "test -x /usr/sbin/pvcreate",
    "test -x /usr/sbin/mkfs.xfs",
    "test -x /usr/sbin/parted",
    "test ! -e /usr/sbin/policy-rc.d",
  ]
}
```

This catches the bad case where `expect_disconnect` masked a partial `apt-get` run and the build progressed with missing storage or SSH tools.

## Environment-Specific Failures Are Still Template Bugs

It is tempting to explain this as a data-center quirk when only one environment fails. The better operating rule is:

```text
if a service restart can drop the Packer communicator, the template should model that boundary explicitly
```

One vSphere cluster may recover SSH fast enough that Packer never notices. Another may drop the TCP session. The shared template should be robust in both.

## Operating Rule

Use `expect_disconnect` only when the disconnect is the expected outcome of a complete command.

For Packer Ubuntu builds:

```text
1. Wait for cloud-init in a low-risk provisioner.
2. Isolate service starts that can drop SSH.
3. Use expect_disconnect only on that isolated provisioner.
4. Prevent package maintainer scripts from restarting SSH mid-install.
5. Remove policy-rc.d immediately after package installation.
6. Validate required binaries in a later provisioner.
7. Enable services explicitly after installation, not accidentally during it.
```

For related vSphere/cloud-init template checks, see [vSphere Guestinfo And Cloud-Init On Cloned VMs](/field-notes/vsphere-cloud-init-guestinfo/) and [Packer Template Sealing After Clone-Time Bootstrap](/field-notes/packer-template-sealing-after-clone-bootstrap/).
