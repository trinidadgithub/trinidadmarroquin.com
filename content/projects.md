+++
title = 'Projects'
date = 2026-06-08T12:36:18-05:00
draft = false
description = 'Project areas for Kubernetes, Terraform, Packer, CI/CD, Rancher, and observability work.'
+++

These project areas are starting points for writeups. Each one should explain the problem, constraints, design choices, and what changed operationally.

<div class="project-grid">
  <section class="project-card">
    <p class="eyebrow">Platform</p>
    <h2>Kubernetes Platform Operations</h2>
    <p>Cluster operations, upgrades, node lifecycle, add-on management, access patterns, backup expectations, and production readiness checks.</p>
    <ul>
      <li>Rancher-managed fleet organization.</li>
      <li>Upgrade notes and rollback planning.</li>
      <li>Namespace, ingress, storage, and policy conventions.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Infrastructure</p>
    <h2>Terraform Infrastructure Modules</h2>
    <p>Reusable Terraform patterns for infrastructure that needs to be reviewed, promoted, and changed safely.</p>
    <ul>
      <li>Module boundaries that match ownership.</li>
      <li>State layout and environment promotion.</li>
      <li>Plan review practices and change visibility.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Images</p>
    <h2>Packer Image Pipelines</h2>
    <p>Machine image builds for repeatable node and VM provisioning with validation before publication.</p>
    <ul>
      <li>Base image hardening and patch cadence.</li>
      <li>Versioning for rollback and auditability.</li>
      <li>Simple validation steps before use.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Delivery</p>
    <h2>CI/CD Pipeline Design</h2>
    <p>Pipeline work focused on clear promotion paths, repeatable tasks, and useful failure output.</p>
    <ul>
      <li>Validation, planning, and apply stages.</li>
      <li>Credential handling and resource design.</li>
      <li>Concourse workflows for infrastructure repositories.</li>
    </ul>
  </section>

  <section class="project-card">
    <p class="eyebrow">Operations</p>
    <h2>Observability And Incident Response</h2>
    <p>Monitoring and alerting work that helps operators make decisions instead of only collecting data.</p>
    <ul>
      <li>Actionable alerts and useful dashboards.</li>
      <li>Log and metric naming conventions.</li>
      <li>Post-incident follow-up tied to system changes.</li>
    </ul>
  </section>
</div>

## Writeup Format

Project posts should stay practical and include:

- The operational problem being solved.
- Constraints and assumptions.
- Design choices and rejected alternatives.
- Failure modes and rollback expectations.
- What became easier to operate after the change.
