+++
title = 'Containerized DNS Drift Detector Boundaries'
date = 2026-07-10T00:00:00-05:00
draft = false
description = 'Field note for packaging an audit-only DNS drift detector as a container while keeping inventories, SSH material, reports, and remediation outside the image.'
tags = ['dns', 'ansible', 'docker', 'kubernetes', 'rke2', 'audit', 'operations']
categories = ['field-notes']
+++

Containerizing a DNS drift detector is useful when the operator environment is inconsistent. The image can carry the shell runner, Ansible configuration, Python dependencies, and command defaults while the runtime provides the inventory, credentials, and report destination.

The important boundary is this: the image should run audits, not own remediation or secrets.

## Image Contents

Keep the image small and boring:

```Dockerfile
FROM python:3.12-slim

ENV ANSIBLE_CONFIG=/app/ansible.cfg \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      openssh-client \
      sshpass \
      bsdextrautils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ansible.cfg ./
COPY bin/dns-drift-detector.sh /usr/local/bin/dns-drift-detector
RUN chmod +x /usr/local/bin/dns-drift-detector

ENTRYPOINT ["dns-drift-detector"]
```

This gives the runner a predictable Bash and Ansible environment without baking in site inventory or operator credentials.

## Runtime Contract

Mount inputs and outputs explicitly:

```bash
docker run --rm \
  -v "$PWD/inventory/site-a-rke2.yaml:/inventory/inventory.yaml:ro" \
  -v "$PWD/reports:/reports" \
  -v "$HOME/.ssh:/ssh:ro" \
  -e SSH_USER=operator \
  -e ANSIBLE_EXTRA_ARGS='--private-key /ssh/id_rsa' \
  dns-drift-detector:local \
  --inventory /inventory/inventory.yaml \
  --group site_a_rke2
```

The container receives only what it needs for the run:

- inventory as read-only input.
- SSH material as read-only input.
- reports as writable output.
- target group as an explicit argument.

Do not copy generated CSVs into the image, and do not commit them unless they are sanitized fixtures.

## Audit-Only Mode

DNS search-domain remediation usually needs elevated host changes: netplan edits, systemd-resolved drop-ins, service restarts, and final audits. That workflow should remain separate from scheduled drift detection.

The detector should answer a narrower question:

```text
Which targeted nodes differ from the expected resolver baseline right now?
```

That keeps routine runs safe enough for CI, cron, or operator smoke tests. Remediation can consume the report later, but the audit image should not mutate hosts by default.

## Secrets Boundary

There are two common local credential paths:

```bash
# SSH key path
-v "$HOME/.ssh:/ssh:ro" \
-e ANSIBLE_EXTRA_ARGS='--private-key /ssh/id_rsa'

# Password path
-e SSH_USER=operator \
-e SSH_PASSWORD='...' \
-e BECOME_PASSWORD='...'
```

Keep both outside the image. The image should not contain `.env`, private keys, inventory secrets, Vault tokens, or cluster-specific group vars.

Use `.dockerignore` defensively:

```text
.env
reports/*
__pycache__/
*.pyc
.pytest_cache/
```

If the repo keeps `reports/.gitkeep`, ignore generated report contents while preserving the directory.

## Compose For Smoke Tests

A local Compose file is useful, but it should remain a smoke-test wrapper around the same runtime contract:

```yaml
services:
  dns-drift-detector:
    build:
      context: .
    image: dns-drift-detector:local
    env_file:
      - path: .env
        required: false
    volumes:
      - ./inventory.example.yaml:/inventory/inventory.yaml:ro
      - ./reports:/reports
      - ~/.ssh:/ssh:ro
    environment:
      ANSIBLE_EXTRA_ARGS: "--private-key /ssh/id_rsa"
    command:
      - --inventory
      - /inventory/inventory.yaml
      - --group
      - example_cluster_rke2
```

The example inventory should be harmless. Real inventories should be mounted at runtime.

## Validate Before Publishing

Validate the shell entrypoint, image build, help output, and Compose rendering:

```bash
bash -n bin/dns-drift-detector.sh
docker build -t dns-drift-detector:local .
docker run --rm dns-drift-detector:local --help
docker compose config
```

Then run one inventory in list-only mode before a full audit:

```bash
docker run --rm \
  -v "$PWD/inventory/site-a-rke2.yaml:/inventory/inventory.yaml:ro" \
  dns-drift-detector:local \
  --inventory /inventory/inventory.yaml \
  --group site_a_rke2 \
  --list-hosts
```

## Operating Rule

Containerized audit tools should package execution consistency, not operational authority.

Keep inventories, credentials, reports, and remediation outside the image so the detector can be rebuilt and shared without carrying site-specific risk.

Related: [DNS Drift Detector Calico Overlay False Positives](/field-notes/dns-drift-detector-calico-overlay-filter/) covers parser behavior after the containerized runner has produced reports.
