+++
title = 'Turning Packer Template Builds Into A Concourse Workflow'
date = 2026-07-14T00:00:00-05:00
draft = false
description = 'A practical SRE article on moving multi-site Packer template builds into Concourse while handling secrets, worker placement, network reachability, ISO behavior, and log hygiene.'
tags = ['concourse', 'packer', 'vsphere', 'cicd', 'kubernetes', 'secrets', 'networking']
categories = ['posts']
+++

Packer template builds are a good fit for CI/CD because they are repeatable, expensive enough to benefit from automation, and easy to forget after the first successful run. They also expose every hidden dependency in the platform: repository access, vCenter permissions, ISO availability, DNS, routing, worker placement, and secret handling.

The goal was not just to make one template build pass. The goal was to make template builds runnable per site from Concourse, with enough visibility to debug failures and enough guardrails to avoid leaking credentials.

## Start With The Smallest Useful Pipeline

The first useful shape was simple:

```text
clone template repo -> packer init -> packer build for one site
```

That proved the runtime container could reach the repository, install or use Packer plugins, read the site variable file, and talk to vCenter. Once a single site worked, the pipeline could fan out into site-specific jobs:

```text
build-site-a
build-site-b
build-site-c
```

Parallelism mattered because template builds spend a lot of time waiting on remote infrastructure. If sites use separate vCenter managers and independent storage, running builds in parallel is reasonable. If several sites share one vCenter or datastore, serialize those jobs or use Concourse serial groups so the pipeline does not create artificial contention.

The important design choice is to model real infrastructure boundaries. Do not parallelize because Concourse can. Parallelize where the underlying platforms are independent enough to tolerate it.

## Treat Local Secrets As Temporary Plumbing

During a proof of concept, it is common to start with a local `vars.yaml` file passed to `fly set-pipeline`:

```bash
fly -t ci set-pipeline \
  -p packer-templates \
  -c concourse/pipeline.yaml \
  -l concourse/vars.yaml \
  -n
```

That is acceptable only as temporary plumbing. The durable model should be Concourse variable interpolation backed by a credential manager:

```yaml
params:
  GITLAB_TOKEN: ((gitlab-token))
  VCENTER_USERNAME: ((site-a-vcenter-username))
  VCENTER_PASSWORD: ((site-a-vcenter-password))
```

The pipeline should not require committing `secrets.pkrvars.hcl`. It should either pass sensitive values as `-var` arguments from Concourse variables or generate a temporary secrets file inside the task from environment variables.

If the long-term target is Vault, keep the variable names stable from the start. Concourse can read `((name))` from a local vars file during the POC and later resolve the same names through Vault. That makes the migration a credential-backend change instead of a pipeline rewrite.

## Keep Secrets Out Of Job Logs

The fastest way to leak secrets is to run shell tasks with full trace output while echoing generated files:

```bash
set -x
echo "VCENTER_PASSWORD=${VCENTER_PASSWORD}"
```

Avoid that pattern. Use trace output around safe commands only, or explicitly disable tracing before materializing secrets:

```bash
set -euo pipefail

apk add --no-cache git
git clone --depth 1 "$REPO_URL" repo

set +x
cat > secrets.auto.pkrvars.hcl <<EOF
vcenter_username = ${VCENTER_USERNAME@Q}
vcenter_password = ${VCENTER_PASSWORD@Q}
EOF
set -x

packer init templates/ubuntu-24-04.pkr.hcl
packer build -force \
  -var-file=environments/site-a/variables.pkrvars.hcl \
  -var-file=secrets.auto.pkrvars.hcl \
  templates/ubuntu-24-04.pkr.hcl
```

Also review clone URLs. An HTTPS clone command with a token embedded in the URL can appear in logs if the shell prints commands. Prefer Concourse resources or commands that avoid echoing credentials. If a token expires, rotate it and redeploy the pipeline, but also use the incident to remove any logging path that prints the token.

## Make Packer Logs Useful Without Drowning The Job

Packer debug logging is useful when a build hangs during SSH or vSphere provisioning:

```bash
PACKER_LOG=1 PACKER_LOG_PATH=packer.log packer build ...
```

For CI, decide whether the log belongs in the console or as an artifact. Console logs are convenient during a POC, but verbose plugin output can bury the signal. A better production pattern is:

```text
normal console output -> concise operator status
packer.log           -> retained artifact for deep debugging
```

Useful console signals include:

- the site being built.
- the selected Concourse worker.
- the vCenter endpoint name, sanitized if necessary.
- whether the build reached VM creation, SSH wait, provisioning, cleanup, and template conversion.
- a link or artifact name for the full Packer log.

That gives operators enough context without making every successful build scroll for thousands of lines.

## Worker Placement Is Architecture, Not Scheduling Trivia

Packer does not only talk to vCenter. The build process often needs to SSH from the Concourse task container to the temporary VM. That means the selected worker must have network reachability to the build VLAN.

This is where Concourse worker placement becomes an architectural decision:

```text
central cluster
  Concourse web
  Concourse database
  local workers for nearby sites

remote clusters
  workers close to remote vCenter and build networks
```

If central workers cannot reach a remote build network, the pipeline will fail even though vCenter can create the VM. Typical symptoms look like SSH timeouts:

```text
TCP connection to SSH ip/port failed: dial tcp 192.0.2.25:22: i/o timeout
```

Before changing Packer code, prove the route from the worker:

```bash
kubectl exec -n concourse concourse-worker-0 -- ip route get 192.0.2.25
kubectl exec -n concourse concourse-worker-0 -- nc -vz 192.0.2.25 22
```

If the worker subnet cannot reach the build subnet, the fix may be a firewall route, moving the build VM to a reachable port group, or placing a worker in the remote site. That is not a Packer problem.

## Host Networking Has A Cost

Using `hostNetwork: true` for Concourse workers can be a practical bridge when task containers need the same routes as the Kubernetes nodes. It can also hide problems and expand the worker's blast radius.

The decision should be explicit:

- Use host networking when the build workflow depends on node-level routes that pod networking does not expose.
- Document which subnets workers must reach and why.
- Keep the Concourse namespace and worker nodes tightly controlled.
- Revisit the decision when remote workers or proper pod routing are available.

Host networking is not a generic performance tuning flag. In this workflow, it was about making SSH and vCenter-adjacent traffic follow the expected network path.

## ISO Path And URL Fallback Need Clear Ownership

vSphere ISO paths are fast when the ISO exists in the expected datastore, but brittle when names drift or datastores differ by site. URL-based ISO download is slower but more portable.

A safe model is:

```text
prefer datastore ISO path when present
fallback to ISO URL when missing
cache downloads when possible
fail with a clear error when neither source works
```

When a VM drops into EFI Boot Manager, do not assume the answer is a bigger boot wait. Check whether the boot ISO was actually attached and whether the site-specific `iso_path`, datastore, and CD-ROM settings match the target vCenter.

The pipeline should make this visible in the job output:

```text
site=site-a
iso_source=datastore
iso_path=[datastore-a] ISO/ubuntu.iso
fallback_url_enabled=true
```

That turns a boot screen mystery into a configuration check.

## Production Readiness Checklist

Before calling a Concourse-backed template build service production-ready, verify these items:

- Repository access uses a scoped credential and does not print tokens.
- Packer variables separate public site config from secrets.
- Secrets resolve through Concourse variables, with a path to Vault or another credential manager.
- Site jobs match the real vCenter and network ownership model.
- Worker placement is documented, including which source subnets need access to which vCenter and build networks.
- Packer logs are retained without dumping sensitive material to the console.
- ISO source behavior is consistent across sites.
- Build failures show whether the failure happened in clone, Packer init, VM creation, SSH wait, provisioning, or template conversion.
- Concourse web access has DNS, TLS, and authentication configured separately from build execution.

The ingress side is its own checklist. See [Concourse Ingress DNS And TLS Cutover](/field-notes/concourse-ingress-dns-tls-cutover/) for the browser-facing DNS, TLS secret, and `externalUrl` work.

For bootstrap-specific diagnosis, see [Packer Bootstrap Placement Versus Runtime Execution](/field-notes/packer-bootstrap-placement-vs-runtime-execution/). That note separates Packer file placement, SSH provisioner reachability, and Terraform/cloud-init runtime execution.

## Operating Rule

Do not treat a successful template build as proof that the platform is ready.

The platform is ready when failed builds are diagnosable, secrets stay out of logs, workers run from networks that can reach their targets, and each site can be rebuilt without relying on someone's workstation as the missing route.
