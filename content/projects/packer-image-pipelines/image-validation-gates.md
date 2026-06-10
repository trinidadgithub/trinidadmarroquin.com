+++
title = 'Packer Image Validation Gates'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial validation gates for Packer-built images, including boot, access, agents, cloud-init, storage, and baseline configuration.'
tags = ['packer', 'images', 'validation']
categories = ['projects']
+++

A Packer build that completes is not necessarily a usable image.

Validation gates should prove that downstream provisioning can consume the image without rediscovering template defects.

## Build-Time Validation

During the build, validate:

- package installation.
- service enablement.
- guest agent status.
- SSH or WinRM access.
- cleanup scripts.
- cloud-init or customization readiness.

## Post-Build Validation

After the template is created, clone it in a test environment.

Check:

- VM boots cleanly.
- hostname customization works.
- primary network config works.
- SSH access works through expected users.
- guest tools report healthy.
- bootstrap logs are present.
- storage prerequisites are installed.

For Kubernetes node images, also validate container runtime, kubelet prerequisites, CSI prerequisites, and any required kernel modules or packages.

## Failure Handling

Failed validation should prevent promotion.

Do not fix a bad template with per-clone Terraform hacks. If every clone needs the same repair, the image is wrong.

## Acceptance Criteria

- Build succeeds.
- Clone test succeeds.
- Network and access are verified.
- Guest agents are healthy.
- Bootstrap can run idempotently.
- The image is promoted only after validation.

## References

- Packer documentation: Build Block.
- Packer documentation: Provisioners.
