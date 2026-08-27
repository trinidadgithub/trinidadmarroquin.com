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
    <p>Vault PKI, transit encryption, Kubernetes auth, rotation patterns, token behavior, policy review, lease handling, and operational safety practices.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Compliance</p>
    <h2><a href="/field-notes/security/">Security And Compliance</a></h2>
    <p>Pod security standards, Kubernetes audit logging, CIS benchmark review, and STIG-oriented baseline review practices for platform teams.</p>
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

  <section class="project-card">
    <p class="eyebrow">Resilience</p>
    <h2><a href="/field-notes/disaster-recovery/">Disaster Recovery</a></h2>
    <p>Full-site recovery planning, cross-region readiness checks, restore evidence, failover decisions, and operational proof before declaring recovery complete.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Cost</p>
    <h2><a href="/field-notes/finops/">FinOps And Cost Allocation</a></h2>
    <p>Kubernetes cost labels, request rightsizing, showback records, quota ownership, and capacity signals that connect engineering behavior to spend.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Networking</p>
    <h2><a href="/field-notes/service-mesh/">Service Mesh Operations</a></h2>
    <p>Mesh adoption boundaries, mTLS rollout, traffic policy ownership, sidecar behavior, and telemetry checks before moving user traffic.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Stateful Platforms</p>
    <h2><a href="/field-notes/database-operators/">Database Operators</a></h2>
    <p>PostgreSQL and MySQL operator ownership, backup/failover validation, replica health, storage assumptions, and restore evidence for Kubernetes databases.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Delivery</p>
    <h2><a href="/field-notes/gitops-operators/">GitOps Operators</a></h2>
    <p>ArgoCD and Flux reconciliation boundaries, sync ownership, drift response, prune safety, promotion evidence, and controller failure signals.</p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Delivery</p>
    <h2><a href="/field-notes/github-actions/">GitHub Actions CI</a></h2>
    <p>Workflow trigger design, permissions, runner trust boundaries, OIDC credentials, reusable workflows, concurrency controls, and artifact evidence.</p>
  </section>
</div>

<!-- These notes should stay short, opinionated, and operational. The goal is not to replace official documentation; it is to capture the judgment that makes the commands useful. -->
