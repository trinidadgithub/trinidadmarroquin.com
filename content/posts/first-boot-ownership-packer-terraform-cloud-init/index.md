+++
title = 'First-Boot Ownership Between Packer, Terraform, vSphere, Cloud-Init, And Bootstrap'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'A systems note on assigning clear ownership between Packer templates, Terraform vSphere clones, guest customization, cloud-init, bootstrap scripts, and CSI storage.'
tags = ['packer', 'terraform', 'vsphere', 'cloud-init', 'systems-thinking']
categories = ['notes']
+++

The hardest part of automating VM provisioning is not always creating the VM. It is deciding which layer owns first boot.

In one troubleshooting session, a Terraform refactor exposed a chain of hidden coupling between Packer, Terraform, vSphere customization, cloud-init, bootstrap scripts, netplan, SSH, and iSCSI. Each tool was doing something useful. The problem was that several of them were trying to own the same parts of the machine lifecycle.

That is where first-boot ownership matters.

## The Layers

The system had several layers:

- Packer built the Ubuntu template.
- Terraform cloned the VM through the vSphere provider.
- vSphere guest customization set hostname, primary network, gateway, and DNS.
- Terraform guestinfo injected cloud-init metadata and userdata.
- cloud-init ran first-boot commands.
- bootstrap scripts configured users, SSH, disks, iSCSI, and node-specific behavior.
- Kubernetes CSI handled persistent volume lifecycle later.

None of those layers is wrong. The failure mode appears when the boundaries are unclear.

## Packer Owns The Template Baseline

Packer should produce a template that is ready to be cloned. That means the image has the right packages and services installed, but it should not contain stale first-boot state.

Packer should own:

- OS package baseline.
- `open-vm-tools`.
- `cloud-init` installation and service enablement.
- `util-linux-extra` when VMware customization requires `hwclock`.
- bootstrap framework placement under a known path.
- cleaning cloud-init instance state before sealing.

Packer should not own per-clone identity. It should not leave a template thinking it has already completed the first boot of a real machine.

A practical pattern is to install only a static bootstrap entrypoint and unit into the image:

```text
/usr/local/bin/platform-bootstrap
/etc/systemd/system/platform-bootstrap.service
/var/lib/platform-bootstrap/
/var/log/platform-bootstrap.log
```

The entrypoint should be idempotent, expose `--version` and `--check`, log to a stable file, write machine-readable status, and create a completion marker only after success. It should not contain site values, passwords, tokens, server URLs, DNS settings, SSH keys, or cluster join config.

That keeps Packer responsible for placing the mechanism, while Terraform and cloud-init decide when to run it and what runtime values to provide.

Also separate Packer build success from bootstrap placement success. If a Packer build creates a VM but never reaches SSH, none of the file or shell provisioners ran. An empty `/opt`, missing `/usr/local/bin/platform-bootstrap`, or absent service unit usually means the build stopped at communicator reachability, not that cloud-init or Terraform failed later.

## Terraform Owns VM Intent

Terraform should describe the VM and the vSphere resources around it: folder, resource pool, datastore, network, CPU, memory, disks, template, and customization settings.

Terraform should own:

- VM inventory.
- site and environment input values.
- vSphere resource placement.
- module boundaries for repeated clone behavior.
- guestinfo keys when cloud-init is intentionally part of the clone flow.

Terraform should not be used to repair template defects during every clone. If a package is missing from the template, fix Packer. If a guest setting is environment-specific, pass it intentionally.

## vSphere Customization Owns Primary Network When Chosen

In this case, vSphere customization was already generating `/etc/netplan/99-netcfg-vmware.yaml` and setting the primary NIC, hostname, gateway, and DNS.

That is a valid model. The mistake is letting cloud-init or a template-era netplan file also own the same primary route.

The operating rule became:

```text
vSphere customization owns primary network
bootstrap owns additional storage networking
```

That eliminated conflicts between `99-netcfg-vmware.yaml`, old template netplan files, and cloud-init network config.

## Cloud-Init Should Trigger, Not Compete

Cloud-init is useful as the first-boot trigger. It can consume VMware guestinfo userdata and call a bootstrap entrypoint.

The useful pattern was minimal:

```yaml
#cloud-config
ssh_pwauth: true
disable_root: true
runcmd:
  - [ bash, -lc, 'mkdir -p /run/sshd' ]
  - [ bash, -lc, 'passwd -u ubuntu || true' ]
  - [ bash, -lc, 'systemctl enable --now ssh' ]
  - [ bash, -lc, '/usr/local/bin/platform-bootstrap' ]
```

The point is not that every site should use exactly that YAML. The point is that cloud-init should have a clear job. In this model, its job is to trigger bootstrap and avoid breaking the template user.

## Bootstrap Owns Guest Configuration

Bootstrap is where environment-specific guest configuration belongs when it cannot be cleanly represented as vSphere customization.

Bootstrap should own:

- final SSH policy.
- local users and sudo rules.
- data disk preparation.
- iSCSI networking and discovery when enabled for a data center.
- storage readiness checks.
- logging that continues even when a step fails.

The logging behavior matters. A bootstrap that exits on the first failure can hide the rest of the system state. For operations, it is often better to log failed steps and continue to a summary, especially when later checks provide useful evidence.

## CSI Owns Volume Lifecycle

iSCSI sessions can be active without new disks showing in `lsblk`. That is expected when Kubernetes CSI is responsible for creating and mapping volumes.

The storage model is:

```text
node is storage-ready
CSI creates volume
array maps LUN to node IQN
node sees disk
kubelet mounts volume
```

That distinction avoids chasing a false failure. No disk in `lsblk` does not necessarily mean iSCSI is broken. It may mean no LUN has been mapped yet.

## The Lesson

First boot needs an ownership model. Without one, every tool tries to be helpful and the result is fragile.

A good model is boring:

- Packer builds the baseline.
- Terraform declares the clone.
- vSphere customization owns primary network if you choose that path.
- cloud-init triggers bootstrap.
- bootstrap owns guest-specific operating system setup.
- CSI owns persistent storage lifecycle.

Once the boundaries are explicit, troubleshooting gets easier. Instead of asking why the VM is broken, you can ask a sharper question: which layer owns the behavior that failed?
