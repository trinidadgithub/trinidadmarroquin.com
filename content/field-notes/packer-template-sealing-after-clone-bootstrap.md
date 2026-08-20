+++
title = 'Packer Template Sealing After Clone-Time Bootstrap'
date = 2026-08-07T00:00:00-05:00
draft = false
description = 'Field note for sealing vSphere Packer templates after clone-time bootstrap: validate the static entrypoint, keep runtime ownership in Terraform/cloud-init, remove identity-bearing state at capture, derive identity at clone time, and power off cleanly for templates.'
tags = ['packer', 'vsphere', 'cloud-init', 'terraform', 'bootstrap', 'templates', 'operations']
categories = ['field-notes']
+++

A Packer template can contain a bootstrap framework without owning every piece of clone behavior.

The boundary is sealing. A successful `packer build` produces a configured machine; it does not, by itself, prove that the resulting artifact is safe to clone. Sealing is the lifecycle stage where a configured build machine is deliberately converted into a reusable artifact, and ownership of state changes hands:

```text
configured machine -> sanitized machine -> sealed template -> clone -> uniquely identified machine
```

That makes the ownership boundaries explicit:

- Packer installs the bootstrap entrypoint, service, and reusable bootstrap capabilities.
- Packer validates that the entrypoint is present, executable, and syntactically valid.
- Sealing removes state that a clone must not inherit ([What Must Not Survive The Template](#what-must-not-survive-the-template)) and shuts the machine down for template capture.
- Terraform/vSphere guest customization provides clone identity and network intent.
- Terraform-rendered cloud-init prepares runtime storage and starts bootstrap at the right time.
- Bootstrap completes machine-specific configuration, writes status, marks completion, and powers off cleanly so the VM can be captured as a known-good template or replacement image.
- Only a disposable clone can validate what a clone actually inherits.

That separation keeps the image reusable. The template contains the reusable mechanism, not the site's final state.

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

## What Must Not Survive The Template

Reusable templates require deliberate decisions about identity-bearing and environment-specific state. Two categories matter: what this pipeline demonstrably removes at capture, and what a reusable Linux template should still evaluate.

### Verified Implementation

The repository documents these cleanup steps before template capture:

```bash
sudo cloud-init clean --logs --machine-id
sudo truncate -s 0 /etc/machine-id
sudo systemctl enable cloud-init-local cloud-init cloud-config cloud-final open-vm-tools
sudo shutdown -h now
```

- `/etc/machine-id` is truncated, so clones do not inherit build-machine identity.
- cloud-init instance state is cleaned with `--machine-id`, so the template does not present itself as a machine that already completed first boot.
- cloud-init services and `open-vm-tools` are re-enabled for cloned VMs.
- The image-factory cleanup gate records "no build artifacts, SSH host keys rotated."

Shutdown (rather than reboot) before capture leaves the final state stable for template conversion.

### Sealing Considerations

A reusable Linux template should also evaluate state this factory does not document as handled:

- SSH host keys — where the cleanup gate removes them, first boot must regenerate them per clone.
- DHCP leases and client identifiers.
- temporary credentials or tokens written during the build.
- installer artifacts and transient logs beyond cloud-init's.
- shell history and temporary files.
- environment-specific hostnames and network configuration, including template-era netplan files that compete with `99-netcfg-vmware.yaml`.

This is not a hardening checklist. The question is identity and environment, not security posture.

### Regeneration

Removing identity is only half of a correct lifecycle. Each removal needs a clear who and when:

- `/etc/machine-id`: systemd generates a fresh machine ID on the clone's first boot.
- SSH host keys: where removed, the clone's first-boot key generation recreates them per clone.
- hostname, primary NIC, gateway, and DNS: written at clone time by vSphere guest customization, not baked into the template.
- cloud-init instance state: rebuilt from the clone's own guestinfo userdata.
- bootstrap state: created by the clone's own bootstrap run after cloud-init mounts runtime storage.

```text
template cleanup -> clone -> first boot -> identity generation -> bootstrap
```

Identity removal without a documented regeneration stage produces clones that inherit state instead of re-deriving it.

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

### Build-Time Versus Clone-Time Validation

`packer build` validates the process that builds the image. It proves the mechanism is present, executable, and syntactically valid. It does not validate the uniqueness or correctness of machines produced from the resulting template.

Clone-time validation establishes that independent clones received appropriate clone-specific values:

- distinct machine identity and hostname per clone.
- per-clone SSH host identity when the template cleaned its keys.
- guest customization applied the expected primary network, gateway, and DNS.
- cloud-init consumed the clone's own guestinfo userdata, not cached instance state.
- bootstrap ran against the clone's own disks and wrote its own status and completion marker.

The relationship is deliberately asymmetric:

```text
Clone A != Clone B   for identity-bearing and runtime-specific state
Clone A == Clone B   for the intentionally reusable template mechanism
```

Build-time success backed by identical clones is not proof of correctness. It can also be proof of successfully inherited identity.

## The Reproducibility Paradox

A template can be perfectly reproducible and still be incorrectly reusable.

Packer reproducibility answers whether the artifact can be constructed consistently: same input, same build, same result. Sealing answers whether multiple machines can safely inherit from that artifact: unique identity, fresh state, correct runtime boundaries. Those are related but distinct properties. A pipeline that faithfully rebuilds an image carrying machine identity or runtime state is reproducible and mis-sealed at the same time.

Build-time success proves the mechanism. It never proves sealing.

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

## When Sealing Fails

An improperly sealed image fails quietly:

```text
build succeeds -> template captured -> multiple clones created
-> identity or runtime state inherited
-> machines boot and look healthy
-> hidden duplication creates operational ambiguity
```

Clones that share a machine-id, SSH host keys, or cloud-init instance state boot normally and pass health checks. The fleet then cannot tell two nodes apart for monitoring, audit, or incident response, and anything keyed on machine or host identity collides.

Successful boot is not sufficient evidence of correct cloning. The clone must re-derive its identity and runtime state.

## Acceptance Criteria

The image/bootstrap path is ready when these are true:

- the Packer build installs the full bootstrap payload, not just one wrapper script.
- the entrypoint passes syntax, version, health, and unit verification checks.
- the template does not bake static domain, DNS search, cluster token, server URL, or runtime disk assumptions.
- the sealed template carries no machine identity or cloud-init instance state.
- cloud-init or a clone-time helper owns data-disk layout before bootstrap starts.
- bootstrap writes durable status and a completion marker.
- successful bootstrap powers off cleanly unless explicitly suppressed for debugging.
- a disposable clone verifies that machine identity, hostname, and SSH host keys are unique and regenerated at first boot.
- a disposable clone proves guest customization, guestinfo, cloud-init, mounts, and bootstrap all ran in the intended order.

The operating rule is simple: seal the mechanism, not the environment. Runtime ownership belongs to the clone path.
