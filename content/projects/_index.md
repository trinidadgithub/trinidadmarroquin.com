+++
title = 'Projects'
date = 2026-06-08T12:36:18-05:00
draft = false
description = 'Professional project areas covering platform operations, cloud platforms, virtualization, secrets management, infrastructure automation, image pipelines, delivery, and observability.'
+++

<div class="project-grid">
  <section class="project-card">
    <p class="eyebrow">Platform</p>
    <h2><a href="/projects/kubernetes-platform-operations/">Kubernetes Platform Operations</a></h2>
    <p>Operational work for production Kubernetes environments, including upgrade planning, node lifecycle, access patterns, backup expectations, and readiness checks.</p>
    <ul>
      <li><a href="/projects/kubernetes-platform-operations/rancher-fleet-standards/">Rancher-managed fleet organization and cluster standards.</a></li>
      <li><a href="/projects/kubernetes-platform-operations/upgrade-sequencing/">Upgrade sequencing, rollback planning, and maintenance windows.</a></li>
      <li><a href="/projects/kubernetes-platform-operations/platform-conventions/">Namespace, ingress, storage, and policy conventions that reduce drift.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/kubernetes-platform-operations/">More</a></p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Platform</p>
    <h2><a href="/projects/cloud-based-platforms/">Cloud Based Platforms</a></h2>
    <p>Cloud platform work focused on reliable foundations for infrastructure, application delivery, identity, networking, and operational visibility.</p>
    <ul>
      <li><a href="/projects/cloud-based-platforms/account-environment-organization/">Account, project, subscription, and environment organization.</a></li>
      <li><a href="/projects/cloud-based-platforms/networking-iam-guardrails/">Networking, IAM, logging, and guardrails for platform teams.</a></li>
      <li><a href="/projects/cloud-based-platforms/provider-operational-patterns/">Operational patterns broken down by provider and discipline.</a></li>
      <li><a href="/projects/cloud-based-platforms/aws-operational-patterns/">AWS-specific patterns for EKS, networking, IAM, and IoT.</a></li>
      <li><a href="/projects/cloud-based-platforms/gcp-operational-patterns/">GCP-specific patterns for GKE, project structure, IAM, and SRE discipline.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/cloud-based-platforms/">More</a></p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Virtualization</p>
    <h2><a href="/projects/vcenter-platform-administration/">vCenter Platform Administration</a></h2>
    <p>VMware vCenter work focused on stable virtualization foundations for application teams, platform services, and infrastructure automation.</p>
    <ul>
      <li><a href="/projects/vcenter-platform-administration/platform-hygiene/">Cluster, datastore, network, template, and permission hygiene.</a></li>
      <li><a href="/projects/vcenter-platform-administration/vm-lifecycle-runbooks/">Operational runbooks for VM lifecycle, capacity review, and incident response.</a></li>
      <li><a href="/projects/vcenter-platform-administration/automation-integration-points/">Integration points for Terraform, Packer, Kubernetes nodes, and backup workflows.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/vcenter-platform-administration/">More</a></p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Security</p>
    <h2><a href="/projects/secrets-management-with-vault/">Secrets Management With Vault</a></h2>
    <p>HashiCorp Vault deployment and operations work for centralizing secrets, tightening access, and giving teams safer ways to consume credentials.</p>
    <ul>
      <li><a href="/projects/secrets-management-with-vault/deployment-and-unseal-runbooks/">Vault deployment, initialization, unseal expectations, and operational runbooks.</a></li>
      <li><a href="/projects/secrets-management-with-vault/policy-auth-secrets-engines/">Policy design, authentication methods, and secrets engine organization.</a></li>
      <li><a href="/projects/secrets-management-with-vault/token-lease-audit-recovery/">Token, lease, audit, backup, and recovery practices for production use.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/secrets-management-with-vault/">More</a></p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Infrastructure</p>
    <h2><a href="/projects/terraform-infrastructure-modules/">Terraform Infrastructure Modules</a></h2>
    <p>Reusable Terraform patterns for infrastructure changes that need clear ownership, reviewable plans, safe promotion, and consistent state management.</p>
    <ul>
      <li><a href="/projects/terraform-vsphere-refactor/">Refactoring a vSphere Terraform repo into environment roots and shared modules.</a></li>
      <li><a href="/projects/terraform-infrastructure-modules/operational-module-boundaries/">Module boundaries that match operational ownership.</a></li>
      <li><a href="/projects/terraform-infrastructure-modules/plan-review-practices/">Plan review practices that improve change visibility before apply.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/terraform-infrastructure-modules/">More</a></p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Images</p>
    <h2><a href="/projects/packer-image-pipelines/">Packer Image Pipelines</a></h2>
    <p>Machine image builds for repeatable VM and node provisioning, with validation gates before images are published for downstream use.</p>
    <ul>
      <li><a href="/projects/packer-image-pipelines/base-image-hardening/">Base image hardening, patch cadence, and template retirement.</a></li>
      <li><a href="/projects/packer-image-pipelines/image-versioning/">Versioning that supports rollback, auditability, and change history.</a></li>
      <li><a href="/projects/packer-image-pipelines/image-validation-gates/">Validation steps for boot, access, agents, and baseline configuration.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/packer-image-pipelines/">More</a></p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Delivery</p>
    <h2><a href="/projects/cicd-pipeline-design/">CI/CD Pipeline Design</a></h2>
    <p>Pipeline work focused on clear promotion paths, repeatable tasks, controlled credentials, and failure output that helps teams recover quickly.</p>
    <ul>
      <li><a href="/projects/cicd-pipeline-design/validation-planning-apply-stages/">Validation, planning, and apply stages.</a></li>
      <li><a href="/projects/cicd-pipeline-design/helm-terraform-validation/">Helm and Terraform validation strategy.</a></li>
      <li><a href="/projects/cicd-pipeline-design/deployment-strategy-labs/">Deployment strategy labs.</a></li>
      <li><a href="/projects/cicd-pipeline-design/concourse-infrastructure-workflows/">Concourse workflows for infrastructure and platform repositories.</a></li>
      <li><a href="/projects/cicd-pipeline-design/concourse-windows-deployment/">Concourse CI/CD on Windows with Terraform.</a></li>
      <li><a href="/projects/cicd-pipeline-design/kafka-streams-terraform-pipeline/">Kafka Streams pipeline managed by Terraform.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/cicd-pipeline-design/">More</a></p>
  </section>

  <section class="project-card">
    <p class="eyebrow">Operations</p>
    <h2><a href="/projects/observability-incident-response/">Observability And Incident Response</a></h2>
    <p>Monitoring, alerting, and response practices that help operators make decisions instead of only collecting more data.</p>
    <ul>
      <li><a href="/projects/observability-incident-response/actionable-alerts-dashboards/">Actionable alerts, useful dashboards, and clear service ownership.</a></li>
      <li><a href="/projects/observability-incident-response/log-metric-naming/">Log and metric naming conventions.</a></li>
      <li><a href="/projects/observability-incident-response/post-incident-follow-up/">Post-incident follow-up tied to measurable system improvements.</a></li>
    </ul>
    <p class="card-more"><a href="/projects/observability-incident-response/">More</a></p>
  </section>
</div>
