+++
title = 'Field Notes'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Practical operations references for Kubernetes, Rancher, vCenter, Terraform, Packer, Vault, cloud platforms, CI/CD, and observability.'
+++

Field Notes are practical operating references: commands, checks, failure modes, and recovery patterns that are useful during real infrastructure work.

<div class="project-grid">
  <section class="project-card">
    <p class="eyebrow">Platform</p>
    <h2><a href="/field-notes/kubernetes/">Kubernetes And Rancher</a></h2>
    <p>Cluster inspection, rollout triage, node health, namespace checks, Rancher-managed fleet behavior, and common failure signals.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Virtualization</p>
    <h2><a href="/field-notes/vsphere/">vCenter Operations</a></h2>
    <p>VM lifecycle checks, datastore and cluster review, template hygiene, snapshots, permissions, and platform integration touchpoints.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Infrastructure</p>
    <h2><a href="/field-notes/terraform/">Terraform Change Review</a></h2>
    <p>Plan inspection, state safety, provider behavior, module boundaries, promotion checks, and recovery steps for failed applies.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Images</p>
    <h2><a href="/field-notes/packer/">Packer Builds</a></h2>
    <p>Template build checks, image versioning, validation steps, common build failures, and release criteria before publishing images.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Security</p>
    <h2><a href="/field-notes/secrets/">Vault And Secrets</a></h2>
    <p>Secrets engine checks, token behavior, policy review, authentication methods, lease handling, and operational safety practices.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Cloud</p>
    <h2><a href="/field-notes/cloud/">Cloud Platforms</a></h2>
    <p>Operational notes for cloud-based platforms, account structure, identity, networking, cost awareness, and service-level troubleshooting.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Delivery</p>
    <h2><a href="/field-notes/cicd/">CI/CD Pipelines</a></h2>
    <p>Pipeline triage, credential checks, artifact flow, promotion behavior, Concourse patterns, and failure output worth preserving.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Operations</p>
    <h2><a href="/field-notes/observability/">Observability And Incidents</a></h2>
    <p>Alert review, dashboard checks, log queries, incident timelines, service ownership, and post-incident follow-up prompts.</p>
  </section>
</div>

<!-- These notes should stay short, opinionated, and operational. The goal is not to replace official documentation; it is to capture the judgment that makes the commands useful. -->
