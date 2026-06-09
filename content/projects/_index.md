+++
title = 'Projects'
date = 2026-06-08T12:36:18-05:00
draft = false
description = 'Professional project areas covering platform operations, cloud platforms, virtualization, secrets management, infrastructure automation, image pipelines, delivery, and observability.'
+++

<div class="project-grid">
  <section class="project-card">
    <p class="eyebrow">Platform</p>
    <h2>Kubernetes Platform Operations</h2>
    <p>Operational work for production Kubernetes environments, including upgrade planning, node lifecycle, access patterns, backup expectations, and readiness checks.</p>
    <ul>
      <li>Rancher-managed fleet organization and cluster standards.</li>
      <li>Upgrade sequencing, rollback planning, and maintenance windows.</li>
      <li>Namespace, ingress, storage, and policy conventions that reduce drift.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Platform</p>
    <h2>Cloud Based Platforms</h2>
    <p>Cloud platform work focused on reliable foundations for infrastructure, application delivery, identity, networking, and operational visibility.</p>
    <ul>
      <li>Account, project, subscription, and environment organization.</li>
      <li>Networking, IAM, logging, and guardrails for platform teams.</li>
      <li>Operational patterns that can later be broken down by provider and discipline.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Virtualization</p>
    <h2>vCenter Platform Administration</h2>
    <p>VMware vCenter work focused on stable virtualization foundations for application teams, platform services, and infrastructure automation.</p>
    <ul>
      <li>Cluster, datastore, network, template, and permission hygiene.</li>
      <li>Operational runbooks for VM lifecycle, capacity review, and incident response.</li>
      <li>Integration points for Terraform, Packer, Kubernetes nodes, and backup workflows.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Security</p>
    <h2>Secrets Management With Vault</h2>
    <p>HashiCorp Vault deployment and operations work for centralizing secrets, tightening access, and giving teams safer ways to consume credentials.</p>
    <ul>
      <li>Vault deployment, initialization, unseal expectations, and operational runbooks.</li>
      <li>Policy design, authentication methods, and secrets engine organization.</li>
      <li>Token, lease, audit, backup, and recovery practices for production use.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Infrastructure</p>
    <h2>Terraform Infrastructure Modules</h2>
    <p>Reusable Terraform patterns for infrastructure changes that need clear ownership, reviewable plans, safe promotion, and consistent state management.</p>
    <ul>
      <li><a href="/projects/terraform-vsphere-refactor/">Refactoring a vSphere Terraform repo into environment roots and shared modules.</a></li>
      <li>Module boundaries that match operational ownership.</li>
      <li>Plan review practices that improve change visibility before apply.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Images</p>
    <h2>Packer Image Pipelines</h2>
    <p>Machine image builds for repeatable VM and node provisioning, with validation gates before images are published for downstream use.</p>
    <ul>
      <li>Base image hardening, patch cadence, and template retirement.</li>
      <li>Versioning that supports rollback, auditability, and change history.</li>
      <li>Validation steps for boot, access, agents, and baseline configuration.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Delivery</p>
    <h2>CI/CD Pipeline Design</h2>
    <p>Pipeline work focused on clear promotion paths, repeatable tasks, controlled credentials, and failure output that helps teams recover quickly.</p>
    <ul>
      <li>Validation, planning, and apply stages.</li>
      <li>Credential handling, resource design, and branch-based promotion.</li>
      <li>Concourse workflows for infrastructure and platform repositories.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Operations</p>
    <h2>Observability And Incident Response</h2>
    <p>Monitoring, alerting, and response practices that help operators make decisions instead of only collecting more data.</p>
    <ul>
      <li>Actionable alerts, useful dashboards, and clear service ownership.</li>
      <li>Log and metric naming conventions.</li>
      <li>Post-incident follow-up tied to measurable system improvements.</li>
    </ul>
  </section>
</div>
