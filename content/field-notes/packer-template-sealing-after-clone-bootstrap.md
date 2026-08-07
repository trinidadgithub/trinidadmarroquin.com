+++
title = 'Packer Template Sealing After Clone-Time Bootstrap'
date = 2026-08-07T00:00:00-05:00
draft = false
description = 'Field note for sealing vSphere Packer templates after clone-time bootstrap: validate the static entrypoint, keep runtime ownership in Terraform/cloud-init, derive identity at clone time, and power off cleanly for capture.'
tags = ['packer', 'vsphere', 'cloud-init', 'terraform', 'bootstrap', 'templates', 'operations']
categories = ['field-notes']
+++

A Packer template can contain a bootstrap framework without owning every piece of clone behavior.

The useful boundary is:

- Packer installs the bootstrap entrypoint and service.
- Packer validates that the entrypoint is present, executable, and syntactically valid.
- Terraform/vSphere guest customization provides clone identity and network intent.
- Terraform-rendered cloud-init prepares runtime storage and starts bootstrap at the right time.
- Bootstrap writes status, marks completion, and powers off cleanly so the VM can be captured as a known-good template or replacement image.

That separation keeps the image reusable. The template contains the mechanism, not the site's final state.

## Do Not Bake Clone Identity Into The Image

A common mistake is to let the bootstrap script hard-code a domain or DNS suffix because it worked in the first environment.

Avoid this shape:

```bash
DOMAIN="corp.example.com"
FQDN="${HOSTNAME}.${DOMAIN}"
```

The domain belongs to the clone-time layer. In vSphere, that usually means guest customization, Terraform module input, or cloud-init metadata.

The bootstrap script can derive the effective value from the guest after customization has run:

```bash
HOSTNAME="$(hostname -s)"
DOMAIN="$(hostname -d 2>/dev/null || true)"

if [[ -z "${DOMAIN}" && -f /etc/resolv.conf ]]; then
  DOMAIN="$(awk '/^search[[:space:]]/{print $2; exit}' /etc/resolv.conf 2>/dev/null)"
fi

if [[ -n "${DOMAIN}" ]]; then
  HOST_ALIASES="${HOSTNAME}.${DOMAIN} ${HOSTNAME}"
else
  HOST_ALIASES="${HOSTNAME}"
fi
```

This keeps one template usable across environments with different domains or with intentionally empty DNS search suffixes.

## Keep Runtime Storage Out Of Image Bootstrap

Packer should not prepare workload data disks that only exist after Terraform creates a clone.

For Kubernetes or Rancher-style nodes, use this ownership split:

```text
Packer template       -> bootstrap files, service unit, prerequisites
Terraform VM module   -> extra disks, guest customization, guestinfo values
cloud-init userdata   -> partition, format, mount, and bind runtime paths
bootstrap entrypoint  -> user/SSH/services and post-mount node preparation
```

If the data disk is attached by Terraform, cloud-init or a clone-time helper should mount it before bootstrap starts. The template should not assume `/dev/sdb` exists during the Packer build.

## Validate The Bootstrap Payload Before Sealing

The Packer build should fail before publishing a template if the bootstrap mechanism is incomplete.

Useful checks inside the Packer provisioner:

```bash
sudo install -d -m 0755 -o root -g root /opt/platform/bootstrap /var/lib/platform-bootstrap
sudo install -m 0755 -o root -g root run_me.sh /opt/platform/bootstrap/run_me.sh
sudo install -m 0644 -o root -g root platform-bootstrap.service /etc/systemd/system/platform-bootstrap.service
sudo ln -sf /opt/platform/bootstrap/run_me.sh /usr/local/bin/platform-bootstrap

sudo bash -n /usr/local/bin/platform-bootstrap
test -x /usr/local/bin/platform-bootstrap
test -f /etc/systemd/system/platform-bootstrap.service
sudo systemd-analyze verify /etc/systemd/system/platform-bootstrap.service
sudo /usr/local/bin/platform-bootstrap --version
sudo /usr/local/bin/platform-bootstrap --check
```

These checks prove that Packer placed the static mechanism. They do not prove the clone's cloud-init data, disks, or guest customization are correct. Validate those on a clone.

## Write Status And Completion State

A bootstrap that runs as a oneshot service should leave evidence that survives process exit:

```text
/var/log/platform-bootstrap.log
/var/lib/platform-bootstrap/status.json
/var/lib/platform-bootstrap/complete
```

That matters because `systemctl status platform-bootstrap` may show `inactive (dead)` after a successful oneshot. The status file and completion marker tell the difference between "completed" and "never ran."

Use a lock so repeated cloud-init or manual attempts do not overlap:

```bash
exec 9>/run/platform-bootstrap.lock
if ! flock -n 9; then
  echo "another bootstrap process is already running"
  exit 0
fi
```

## Power Off Cleanly After Success

For a template-capture or prebuilt replacement workflow, a successful bootstrap should leave the VM in a clean, stopped state.

Do this only after writing the completion marker:

```bash
touch /var/lib/platform-bootstrap/complete
trap - EXIT

if [[ "${POWEROFF:-1}" != "0" ]]; then
  systemctl poweroff || shutdown -P now
fi
```

The environment variable is useful for diagnostics. A pipeline, cloud-init test, or console troubleshooting session can set `POWEROFF=0` to keep the VM online after bootstrap.

Prefer power-off over reboot when the next consumer is a template conversion, snapshot, or powered-off replacement VM. Reboot proves the VM can restart, but it also changes the final state and can race with capture logic.

## Acceptance Criteria

The image/bootstrap path is ready when these are true:

- the Packer build installs the full bootstrap payload, not just one wrapper script.
- the entrypoint passes syntax, version, health, and unit verification checks.
- the template does not bake static domain, DNS search, cluster token, server URL, or runtime disk assumptions.
- cloud-init or a clone-time helper owns data-disk layout before bootstrap starts.
- bootstrap writes durable status and a completion marker.
- successful bootstrap powers off cleanly unless explicitly suppressed for debugging.
- a disposable clone proves guest customization, guestinfo, cloud-init, mounts, and bootstrap all ran in the intended order.

The operating rule is simple: seal the mechanism, not the environment. Runtime ownership belongs to the clone path.
