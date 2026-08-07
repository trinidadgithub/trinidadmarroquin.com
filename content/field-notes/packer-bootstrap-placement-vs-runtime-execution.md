+++
title = 'Packer Bootstrap Placement Versus Runtime Execution'
date = 2026-07-16T00:00:00-05:00
draft = false
description = 'Field note for diagnosing Packer bootstrap anomalies: whether static bootstrap files were placed in the template, whether SSH provisioners ran, and whether Terraform/cloud-init started runtime behavior after clone.'
tags = ['packer', 'vsphere', 'cloud-init', 'terraform', 'bootstrap', 'concourse', 'operations']
categories = ['field-notes']
+++

A Packer template build can fail in three different places that look similar from the outside:

- Packer never reaches SSH, so file and shell provisioners never run.
- Packer places bootstrap files into the template, but does not execute runtime bootstrap.
- Terraform/cloud-init clones the VM but does not start the bootstrap entrypoint correctly.

Do not diagnose all three as “bootstrap did not work.” Ask which layer failed.

## Placement Is Packer's Job

For a reusable vSphere template, Packer should place static resources only. For the follow-on sealing pattern after the bootstrap payload is placed and validated, see [Packer Template Sealing After Clone-Time Bootstrap](/field-notes/packer-template-sealing-after-clone-bootstrap/).

```text
/usr/local/bin/platform-bootstrap
/etc/systemd/system/platform-bootstrap.service
/var/lib/platform-bootstrap/
/var/log/platform-bootstrap.log
```

The Packer build should verify the static entrypoint before sealing the image:

```bash
bash -n /usr/local/bin/platform-bootstrap
/usr/local/bin/platform-bootstrap --version
/usr/local/bin/platform-bootstrap --check
systemd-analyze verify /etc/systemd/system/platform-bootstrap.service
```

It should not bake site-specific values into the template:

```text
no cluster token
no server URL
no static IP or gateway
no DNS suffix
no SSH private keys
no environment secrets
```

Terraform and cloud-init can provide runtime values later.

## If `/opt` Or `/usr/local/bin` Is Empty

If the final template is missing the bootstrap files entirely, check whether Packer ever reached the provisioner stage.

Typical log shape when it did not:

```text
Using SSH communicator to connect: 192.0.2.25
Waiting for SSH to become available...
TCP connection to SSH ip/port failed: dial tcp 192.0.2.25:22: i/o timeout
```

In that state, none of the later provisioners ran. The problem is not cloud-init or the bootstrap script. It is reachability from the Packer runner to the temporary build VM.

For Concourse-backed builds, test from the selected worker, not from your workstation:

```bash
kubectl exec -n concourse concourse-worker-0 -- ip route get 192.0.2.25
kubectl exec -n concourse concourse-worker-0 -- nc -vz 192.0.2.25 22
```

If your workstation can reach the VM but the worker cannot, a local Packer build may succeed while the pipeline build never reaches SSH. Fix routing/firewall/worker placement before changing bootstrap code.

## Prove The Pipeline Commit

A pipeline that clones the repo fresh should print the cloned commit SHA. Otherwise, a successful build log cannot prove whether it used the commit that added the bootstrap stage.

Add a safe signal near the clone step:

```bash
git clone --depth 1 "$REPO_URL" repo
git -C repo rev-parse --short HEAD
```

Do not print clone URLs containing tokens. If the token is embedded in the URL, suppress command tracing around the clone.

## Runtime Execution Is Terraform And Cloud-Init's Job

After cloning from the template, verify the static resources first:

```bash
ls -l /usr/local/bin/platform-bootstrap
systemctl cat platform-bootstrap
```

Then verify cloud-init and bootstrap runtime state:

```bash
cloud-init status --long
sudo systemctl status platform-bootstrap --no-pager
sudo journalctl -u platform-bootstrap --no-pager -n 100
sudo cat /var/lib/platform-bootstrap/status.json
sudo test -f /var/lib/platform-bootstrap/complete && echo complete
```

For a `Type=oneshot` unit, `inactive (dead)` can be normal after success. Use the status file and completion marker to tell success from “never ran.”

## Acceptance Criteria

The template/bootstrap path is healthy when these are true:

- Packer logs show SSH connected before file/shell provisioners.
- the final template contains the static bootstrap entrypoint and unit.
- the build validates script syntax, unit syntax, `--version`, and `--check`.
- the pipeline log records the safe Git commit SHA used for the build.
- cloned VMs receive runtime values through Terraform/cloud-init, not Packer.
- cloud-init starts bootstrap only after required mounts and configuration are present.

The key distinction is placement versus execution. Packer places the mechanism. Terraform and cloud-init decide how that mechanism runs for each clone.
