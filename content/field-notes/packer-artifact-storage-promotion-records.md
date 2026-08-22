+++
title = 'Packer Artifact Storage And Promotion Records'
date = 2026-08-21T00:00:00-05:00
draft = false
description = 'Field note for retaining Packer build artifacts, validation evidence, metadata, and promotion records so image consumers can audit and roll back template changes.'
tags = ['packer', 'artifacts', 'images', 'cicd', 'validation', 'automation']
categories = ['field-notes']
+++

A Packer image pipeline produces more than a template. It produces evidence.

If the only durable output is "template exists in vSphere," operators lose the ability to answer the questions that matter during rollback or incident review:

- What source produced this template?
- Which Packer and plugin versions built it?
- Which variables were used, excluding secrets?
- Which validation gates passed?
- Which template was promoted to current?
- What changed from the previous image?

Artifact storage is the operating memory of the image factory.

## Store Build Evidence Separately From The Template

The vSphere template is the consumable artifact. It is not the full audit record.

Keep a separate build record per image version:

```text
image-version/
  manifest.json
  packer.log
  validation-summary.json
  package-baseline.txt
  checksums.txt
  promotion.json
```

The exact filenames do not matter. The boundary does.

The template answers "what can Terraform clone?" The build record answers "why do we trust it?"

## Keep Secrets Out Of Artifacts

Artifacts are useful because they are retained. That also makes them dangerous if the pipeline writes secrets into them.

Redact or avoid storing:

- vCenter passwords and access tokens.
- generated temporary passwords.
- SSH private keys.
- Windows unattend secrets.
- cloud-init userdata when it contains credentials.
- full environment variable dumps from CI tasks.

Prefer sanitized variable summaries over raw variable files:

```text
site=site-a
builder=vsphere-iso
os=ubuntu-24.04
role=k8s-node
image_version=ubuntu-2404-k8s-node-2026.08.21-1
git_commit=abc1234
packer_version=1.x.y
```

The evidence should let an operator reason about the build without exposing the credentials that made the build possible.

## Promotion Needs Its Own Record

Building a template and promoting it are different events.

A promotion record should identify:

- candidate image version.
- validation run or evidence bundle.
- target folder, tag, or `current` pointer.
- previous promoted version.
- operator or pipeline run that performed promotion.
- timestamp and rollback target.

That gives rollback a concrete input. Without it, rollback becomes an archeology exercise through vSphere inventory, CI logs, and Slack messages.

## Cross-Site Copies Need Local Evidence

If the image factory distributes templates across vSphere sites, keep evidence for each site-local copy.

At minimum, record:

- source template version.
- destination vCenter or site.
- copy time.
- destination template path or tag.
- site-local validation result.
- whether the site-local `current` pointer changed.

Do not assume a successful central build proves every site-local copy is usable. Datastores, clusters, networks, content libraries, permissions, and guest customization behavior can differ by site.

## Retention Rules

Keep artifacts long enough to support the operating model:

- current image evidence.
- previous rollback image evidence.
- deprecated image evidence until the deletion window expires.
- failed build logs long enough to debug recurring failures.

There is no value in retaining every verbose Packer log forever if nobody can find the promoted image record. Retention should favor traceability over hoarding.

## Failure Model

The failure pattern is simple:

```text
template promoted -> issue appears -> rollback needed
-> no promotion record -> no validation evidence
-> operators guess which image is safe
```

That is avoidable. Every promoted template should have a small, durable record linking source, build, validation, promotion, and rollback target.

The operating rule: if a VM can depend on an image, the image needs evidence that survives the build job.
