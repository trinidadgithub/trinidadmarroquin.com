+++
title = 'Docker Stale Binaries In Usr Local Bin'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for diagnosing Docker failures caused by stale runc and containerd-shim-runc-v2 binaries in /usr/local/bin shadowing package-managed versions.'
tags = ['docker', 'containerd', 'runc', 'troubleshooting', 'linux']
categories = ['field-notes']
+++

Docker can break silently when stale binaries in `/usr/local/bin` shadow the package-managed versions after an upgrade. The daemon starts, `docker ps` works, but containers fail to run with no obvious error in the Docker CLI.

## The Pattern

```text
docker ps            # works, lists containers
docker run hello-world  # hangs or fails silently
```

The daemon itself is healthy. The break is in the runtime path. After a Docker or containerd upgrade, the new daemon expects a compatible runc and shim, but an old copy in `/usr/local/bin` gets resolved first because it appears earlier in `$PATH` than the packaged binary.

## Detection

Check which runc is actually in use:

```bash
which runc
runc --version
```

If it points to `/usr/local/bin/runc` and the version predates the installed Docker or containerd, that is the problem. Compare against the packaged version:

```bash
dpkg -l runc  # or rpm -q runc
```

## Fix

Move the stale binaries out of the path, then restart the daemons:

```bash
sudo mkdir -p /usr/local/bin/disabled
sudo mv /usr/local/bin/runc /usr/local/bin/disabled/
sudo mv /usr/local/bin/containerd-shim-runc-v2 /usr/local/bin/disabled/
sudo systemctl restart containerd docker
```

Verify:

```bash
docker run --rm hello-world
```

After the fix, `which runc` should resolve to `/usr/bin/runc` (or wherever the package manager installed it).

## Why It Happens

Docker Engine and containerd are often installed via the official convenience script or a manual tarball that drops files into `/usr/local/bin`. When the system package manager later installs an updated version (or when Docker is reinstalled from the official apt repository), the `$PATH` shadowing persists because `/usr/local/bin` takes precedence over `/usr/bin`.

The same can happen with any binary that both a package and a manual installation place in the path. The fix is not specific to runc.

## Prevention

Avoid mixing installation methods. Pick one:

- **apt / yum / dnf** for system-managed installations.
- **official convenience script** only when the package manager does not offer the required version, and audit `/usr/local/bin` afterward.

If `/usr/local/bin` has binaries from a prior installation, clean them out before upgrading the package-managed installation:

```bash
sudo rm /usr/local/bin/runc /usr/local/bin/containerd-shim-runc-v2
sudo systemctl restart containerd docker
```

## Acceptance Criteria

- `docker run --rm hello-world` completes.
- `which runc` does not return `/usr/local/bin/runc`.
- Existing containers can start and stop normally.
- `docker ps` shows the same containers before and after the fix.
