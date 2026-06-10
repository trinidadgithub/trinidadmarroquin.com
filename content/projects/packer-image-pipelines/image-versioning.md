+++
title = 'Packer Image Versioning'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial image versioning model for Packer-built VM templates with rollback, auditability, and change history.'
tags = ['packer', 'images', 'automation']
categories = ['projects']
+++

Image versioning should make rollback boring.

If operators cannot tell which template built a VM, what changed in that template, and whether it is safe to roll back, the image pipeline is incomplete.

## Version Format

Use a version format that carries time and intent:

```text
ubuntu-22.04-k8s-node-2026.06.10-1
ubuntu-22.04-base-2026.06.10-1
```

Include:

- OS family and version.
- purpose.
- build date.
- build sequence or semantic version.

## Metadata

Store metadata with the image:

- Git commit.
- Packer version.
- builder plugin versions.
- package manifest or important package versions.
- validation result.
- deprecation state.

In vSphere, use template names, notes, tags, or custom attributes consistently.

## Promotion

Separate build from promotion:

```text
build -> validate -> mark candidate -> promote -> consume
```

Terraform should consume promoted images, not whatever Packer happened to build most recently.

## Acceptance Criteria

- Every VM can be traced to an image version.
- Rollback image is known.
- Image metadata links to source.
- Promotion is explicit.
- Deprecated images are not silently consumed.

## References

- Packer documentation: HCL Templates.
- HashiCorp guidance on artifact and image workflows.
