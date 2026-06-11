+++
title = 'Image Factory Workflow With vSphere And Packer'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Project page for the Packer-based image factory workflow: template pipeline, versioning strategy, cross-site distribution, validation gates, and the operating model that keeps node images consistent across the fleet.'
tags = ['packer', 'vsphere', 'images', 'automation', 'pipeline']
categories = ['projects']
+++

The image factory produces the node template that every cluster in every site boots from. If the factory is manual or inconsistent, every cluster inherits drift from its template.

This page collects the pipeline shape, versioning strategy, validation gates, and operating model for a Packer-based image factory with vSphere.

## Pipeline Shape

```mermaid
graph LR
    TRIGGER[Git Tag / Schedule] --> BUILD[Packer Build]
    BUILD --> VALIDATE[Boot + Validate]
    VALIDATE --> HARDEN[Apply Baselines]
    HARDEN --> TEMPLATE[Convert To Template]
    TEMPLATE --> TEST[Test Instance]
    TEST --> PROMOTE[Promote Template]
    PROMOTE --> CLEANUP[Cleanup Temp Resources]
```

## Template Versioning

Date-based versioning works for node templates because consumers (cluster autoscaler, Terraform modules) select images by a version string, not by semantic compatibility:

```text
ubuntu-2204-v2026.06.01
ubuntu-2404-v2026.05.15
```

The version is the build date. If a build fails validation, the previous version remains current. Rollback is selecting the previous date tag.

A `current` marker (e.g., folder or tag) is updated on each successful promotion. Consumers reference `current` and get the latest verified template.

## Build Image Source

The base image for Packer builds is a minimal OS ISO, not a previous template build. This avoids accumulating configuration drift across template generations.

Each build:

1. Mounts the OS ISO via vSphere.
2. Runs automated OS installation (autoinstall or kickstart).
3. Applies baseline configuration (agents, security policies, kernel parameters).
4. Hardens the image (remove unused packages, apply STIG or CIS baseline).
5. Converts to a vSphere template.
6. Boots a test instance from the template.
7. Runs validation checks against the test instance.
8. Promotes the template to production folders.

## Validation Gates

A build that fails any gate does not become a template:

| Gate | Check |
|---|---|
| Boot | VM boots and is reachable via SSH within timeout |
| Kernel | Expected kernel version and parameters |
| Networking | Correct interface names, DNS resolution, NTP sync |
| Agents | Required agents installed and running (VMTools, monitoring, security) |
| Storage | iSCSI initiator configured and can reach targets |
| Containerd | Installed and responds to `ctr version` |
| CIS/STIG | Baseline security checks pass |
| Cleanup | No build artifacts, SSH host keys rotated |

## Cross-Site Distribution

If the image factory serves multiple vSphere sites, each site should have a local copy of the template:

1. Build in the central vSphere instance.
2. Clone the template to each site's vSphere.
3. Verify the cloned template boots and passes validation in each site.
4. Update the site-local `current` pointer.

Site-local templates protect against vSphere link latency and provide a fallback if the central vSphere is unavailable.

## Operating Model

| Activity | Cadence |
|---|---|
| OS patch release | Build within 5 business days |
| CVSS 9+ kernel fix | Build within 24 hours |
| Agent version update | Build on request |
| Template refresh (no changes) | Monthly |
| Rollback drill | Quarterly |
| Site template validation | Weekly |

## Acceptance Criteria

- Every cluster node boots from a versioned, validated template.
- Template versions are traceable to a pipeline run and a Git commit.
- CIS/STIG baseline checks pass on every build.
- Site-local templates are independently validated.
- Rollback is selecting the previous date tag and rerunning the site distribution step.
