+++
title = 'Terraform Refactor Notes: When Repo Cleanup Exposes Infrastructure Coupling'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'A practical SRE note on how refactoring a vSphere Terraform repo exposed coupling between Terraform, Packer, cloud-init, vSphere customization, netplan, bootstrap scripts, and iSCSI.'
tags = ['terraform', 'vsphere', 'packer', 'cloud-init', 'systems-thinking']
categories = ['notes']
+++

A Terraform refactor can look like a file organization problem until the first plan, clone, and bootstrap run.

The repo I was working on had the usual signs of age: copied environment roots, local state files, duplicated templates, inconsistent variable files, and old one-off directories that were still sitting beside active infrastructure. The obvious fix was to move toward a cleaner layout:

```text
environments/<site>/<env>/
modules/vsphere-vm-group/
templates/
archive/
```

That was the right direction. It was also only the beginning.

## The Refactor Was The Easy Part

The first pass was structural. Move active roots under `environments/`, preserve old state under `archive/`, keep templates available, and create a shared `vsphere-vm-group` module.

The design decision that mattered most was matching the module boundary to the real Terraform shape. The existing roots created VM groups from a map, so a VM group module made more sense than forcing everything through a single-VM abstraction.

That gave the repo a better operating shape:

- Site and environment roots became easier to find.
- Module behavior became reusable.
- Historical artifacts stopped cluttering active work.
- `terraform plan` became easier to reason about.

But then the refactor exposed the actual system.

## The Module Changed First-Boot Behavior

Moving VM creation into a module changed more than the address of the resource. The module also started injecting VMware guestinfo data for cloud-init:

```text
guestinfo.metadata
guestinfo.userdata
guestinfo.network-config
```

That meant the VM was no longer just a vSphere clone with guest customization. It was now a vSphere clone plus cloud-init plus bootstrap execution.

That matters because first boot was already being influenced by multiple systems:

- Packer built the template.
- vSphere customization set hostname, network, and DNS.
- Terraform provided the clone configuration.
- cloud-init consumed guestinfo data.
- Bootstrap scripts configured SSH, users, disks, and storage networking.

Once cloud-init was enabled and guestinfo userdata was injected, login behavior changed. SSH was reachable, but authentication failed. That was not a Terraform syntax problem. It was an ownership problem.

## Preserve Behavior Before Improving It

One lesson from this session: refactors should preserve behavior first.

If an environment root has special behavior, the module needs to support it explicitly before that root is converted. In this case, important behavior included:

- `wait_for_guest_ip_timeout = 0`
- disk UUID support for Kubernetes nodes
- two disks
- vSphere guest customization
- post-create power behavior
- cloud-init userdata
- bootstrap execution

The module could support those things, but they had to be treated as intentional inputs, not incidental details copied from an old `main.tf`.

## Network Ownership Was The Real Problem

The most useful discovery was that several systems were trying to influence networking.

VMware customization created:

```text
/etc/netplan/99-netcfg-vmware.yaml
```

The template also had older netplan files. In some cases both sets of files declared default routes. That produced errors like:

```text
Error: Conflicting default route declarations for IPv4
first declared in nic0 but also in ens192
```

That kind of conflict can disturb Kubernetes node communication, DNS resolution, kubelet behavior, storage paths, and bootstrap scripts. It is not just cosmetic drift.

The fix was to choose one authority. For the immediate path, VMware customization owned the primary NIC, hostname, gateway, and DNS. Bootstrap owned additional storage NICs and iSCSI setup. Cloud-init ran bootstrap but did not try to own the same network settings.

The useful rule became simple:

```text
one network authority per layer
```

## The Storage Lesson

The iSCSI work exposed another boundary.

The node needed to be storage-ready, but it did not need to see every disk immediately. For Kubernetes with CSI-backed storage, the sequence is:

```text
PVC -> CSI -> array creates volume -> array maps LUN -> node sees disk -> kubelet mounts volume
```

So a new node can have working iSCSI sessions and still not show a new disk in `lsblk` until the array maps a LUN to that node's initiator.

That distinction matters during troubleshooting. Connected to the array does not mean a volume is mapped. It only means the node is ready for the storage lifecycle to happen.

## What Changed Operationally

The end state was not just a cleaner repo. The real improvement was clearer ownership:

- Terraform owns VM intent and vSphere resources.
- Environment roots own site-specific values.
- Shared modules own repeated provisioning behavior.
- Packer owns the template baseline.
- cloud-init triggers first-boot behavior.
- Bootstrap owns environment-specific OS configuration.
- CSI owns persistent volume lifecycle.

That model is easier to operate because each layer has a job. When something fails, the question becomes sharper: which layer owns this behavior?

## Takeaways

- A Terraform refactor can reveal hidden coupling between infrastructure layers.
- Module boundaries should match the real resource shape before they are made more abstract.
- State moves are part of module refactors, not an afterthought.
- Do not let vSphere customization, cloud-init, and bootstrap all own the same network settings.
- Guest logs and generated OS config often explain more than Terraform plan output.
- A clean repo layout helps, but clear ownership is what makes the system operable.

The refactor succeeded because it forced the infrastructure model to become explicit. That is the real value of the work.
