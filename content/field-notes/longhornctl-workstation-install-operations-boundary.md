+++
title = 'Longhornctl Workstation Install And Operations Boundary'
date = 2026-08-03T00:00:00-05:00
draft = false
description = 'Field note for installing longhornctl on an Ubuntu workstation and keeping its use separate from day-to-day Longhorn health checks through CRDs and the UI.'
tags = ['longhorn', 'kubernetes', 'rke2', 'rancher', 'storage', 'cli', 'operations']
categories = ['field-notes']
+++

Longhorn has a CLI, `longhornctl`, but installing it should not change the operational source of truth during maintenance. For Rancher-managed Longhorn clusters, the most useful day-to-day state still usually comes from the Longhorn UI and Kubernetes CRDs such as `volumes.longhorn.io`, `replicas.longhorn.io`, `nodes.longhorn.io`, `engines.longhorn.io`, and `settings.longhorn.io`.

The practical boundary is simple: use `longhornctl` as an operator tool, not as a reason to skip in-cluster evidence.

## Install Locally

For an Ubuntu workstation, a user-local install avoids system-wide package changes. Confirm the workstation architecture first:

```bash
uname -s
uname -m
```

For a Linux `x86_64` workstation, download the matching `linux-amd64` release asset and checksum from the upstream Longhorn CLI releases, verify the checksum, then place the binary in `~/.local/bin`:

```bash
version='v1.12.0'
base_url="https://github.com/longhorn/cli/releases/download/${version}"

curl -fL "${base_url}/longhornctl-linux-amd64" \
  -o /tmp/longhornctl-linux-amd64
curl -fL "${base_url}/longhornctl-linux-amd64.sha256" \
  -o /tmp/longhornctl-linux-amd64.sha256

cd /tmp
sha256sum -c longhornctl-linux-amd64.sha256
chmod 0755 longhornctl-linux-amd64
mv longhornctl-linux-amd64 ~/.local/bin/longhornctl
```

Verify the installed command:

```bash
which longhornctl
longhornctl version
```

If `~/.local/bin` is not already on `PATH`, add it through the workstation shell profile rather than installing the binary into a system directory by default.

## Where It Fits

`longhornctl` is useful for tasks such as install or upgrade checks, preflight checks, support bundle collection, and version-specific administrative workflows.

During a maintenance window, keep the health gates tied to cluster state:

```bash
kubectl -n longhorn-system get pods -o wide
kubectl -n longhorn-system get volumes.longhorn.io
kubectl -n longhorn-system get replicas.longhorn.io
kubectl -n longhorn-system get nodes.longhorn.io
```

Those checks show the current volume, replica, node, and engine state that matters before draining or rebooting storage-bearing nodes. `longhornctl` can complement that evidence, especially when collecting a support bundle, but it should not replace the explicit CRD checks in the runbook.

## Maintenance Rule

Install tools before the window, verify their checksums, and record their versions. Then decide which command is authoritative for each gate.

For Longhorn maintenance, the safest split is:

```text
longhornctl: workstation tool, preflight helper, support bundle helper
kubectl + Longhorn CRDs: in-cluster operational state
Longhorn UI: fast visual confirmation and guided admin workflows
```

That boundary prevents a CLI install from becoming a process change. The tool is useful; the runbook still needs to prove storage health from the cluster itself.
