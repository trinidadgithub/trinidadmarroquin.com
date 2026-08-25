# trinidadmarroquin.com

Personal site for Trinidad Marroquin, built with [Hugo](https://gohugo.io/) and the [PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme.

The site is intentionally simple: fast static pages, readable content, and practical writing about SRE, DevOps, Kubernetes, Terraform, Packer, Rancher, Concourse, and observability.

## Local Development

Install Hugo, then run:

```bash
hugo server
```

Build the static site:

```bash
hugo
```

Generated files are written to `public/`.

## Content

Main pages live in `content/`:

- `content/_index.md` - home page
- `content/about.md` - about page
- `content/projects.md` - project writeups
- `content/resume.md` - resume page
- `content/posts/` - blog posts

Site configuration lives in `hugo.toml`.

## Coverage Roadmap

Content gaps are closed in focused clusters. Current coverage highlights include:

- Observability & Incident Response: SLO burn-rate alerting, SLO dashboard design, incident review, and on-call escalation practices.
- Kubernetes Platform Operations: RKE2, Longhorn, Calico, ingress, cert-manager, Velero, cluster autoscaler, node maintenance, and operational evidence patterns.
- Secrets Management With Vault: PKI, transit encryption, Kubernetes auth, rotation patterns, policy design, leases, audit, and recovery practices.
- Security And Compliance: pod security standards, Kubernetes audit logging, CIS benchmark review, and STIG-oriented Linux baseline review practices.
- Terraform Infrastructure Modules: module composition, remote state design, provider versioning and upgrade, state movement, and plan review practices.
- Packer Image Pipelines: Linux and Windows template lifecycle, HCL2 migration, artifact storage, sealing, validation gates, and promotion records.
- vCenter Platform Administration: cluster boundaries, DRS and resource pool operations, tag/custom attribute ownership, govc verification, and vSphere automation guardrails.
- Disaster Recovery: full-site recovery planning, cross-region failover readiness, DR evidence bundles, etcd snapshot recovery, and Velero workload restore practices.
- FinOps And Cost Allocation: Kubernetes cost labels, request rightsizing, showback and chargeback decision records, quota ownership, and capacity-cost review practices.
- Service Mesh Operations: mesh adoption boundaries, mTLS rollout, traffic policy ownership, sidecar behavior, and telemetry/debugging checks.
- Infrastructure Automation: Terraform, Packer, vSphere, NetBox, Concourse, and GitOps-oriented workflows.

Local planning notes for future content gaps are kept out of Git.

## Resume

The resume page links to `/resume.pdf`. To publish a PDF resume, add it here:

```text
static/resume.pdf
```

Hugo will serve it at:

```text
https://trinidadmarroquin.com/resume.pdf
```

## Theme

This site uses PaperMod from `themes/PaperMod`. Keep theme customizations minimal so the site remains easy to update and maintain.
