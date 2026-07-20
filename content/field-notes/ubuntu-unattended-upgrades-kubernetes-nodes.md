+++
title = 'Disabling Ubuntu Unattended Upgrades On Kubernetes Nodes'
date = 2026-07-20T00:00:00-05:00
draft = false
description = 'Field note for auditing, disabling, masking, purging, and verifying Ubuntu unattended upgrades and apt timers on Kubernetes nodes without relying on unsafe process killing.'
tags = ['ubuntu', 'ansible', 'kubernetes', 'updates', 'maintenance', 'operations']
categories = ['field-notes']
+++

Ubuntu nodes can have the `unattended-upgrades` package installed without actively running upgrades. The package state alone is not enough. Check the config, service, timers, logs, and package history before deciding whether a node is safe.

For production Kubernetes nodes, the desired state is usually:

```text
unattended-upgrades package absent or inert
unattended-upgrades.service inactive and disabled
apt-daily.timer disabled or masked
apt-daily-upgrade.timer disabled or masked
/etc/apt/apt.conf.d/20auto-upgrades set to 0
patching handled through controlled maintenance windows
```

## Audit First

Use multiple signals. An empty unattended-upgrades log is useful, but it does not prove the feature is disabled.

```bash
dpkg -l unattended-upgrades
cat /etc/apt/apt.conf.d/20auto-upgrades 2>/dev/null || true
systemctl is-enabled unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer
systemctl is-active unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer
systemctl list-timers | grep apt || true
sudo journalctl -u unattended-upgrades --since "7 days ago" --no-pager
sudo ls -lh /var/log/unattended-upgrades/ 2>/dev/null || true
```

Interpret the state carefully:

| Signal | Meaning |
|---|---|
| package installed | The capability exists, but may be inactive |
| `20auto-upgrades` has `Unattended-Upgrade "1"` | Automatic upgrades are enabled |
| `apt-daily-upgrade.timer` enabled | The system may trigger unattended upgrade activity |
| empty unattended-upgrades log | It may not have run recently, but verify timers and config |
| journal entries during an incident window | Correlate with package, service, storage, and kubelet events |

## Disable Cleanly

Prefer stopping and disabling systemd units before removing packages. Do not start with `kill -9` unless a process is stuck and you have already tried a clean stop.

```bash
sudo systemctl stop unattended-upgrades.service apt-daily.service apt-daily-upgrade.service 2>/dev/null || true
sudo systemctl disable unattended-upgrades.service apt-daily.service apt-daily-upgrade.service 2>/dev/null || true

sudo systemctl stop apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
sudo systemctl disable apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
sudo systemctl mask apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
```

Then make the config inert:

```bash
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Download-Upgradeable-Packages "0";
APT::Periodic::AutocleanInterval "0";
APT::Periodic::Unattended-Upgrade "0";
EOF
```

If the operating model is to remove the package entirely:

```bash
sudo apt-get remove --purge -y unattended-upgrades
sudo rm -f /etc/apt/apt.conf.d/50unattended-upgrades
```

## Inject The Intent In Packer

The durable place to express this policy is the node image, not only the remediation playbook. If Packer builds the Ubuntu template used for Kubernetes nodes, add a provisioner that makes the template's intent explicit: automatic apt activity is off before any clone ever joins a cluster.

Place this after the base package installation stage and before final template cleanup. That lets the build install required packages first, then freeze the update policy into the image baseline.

```hcl
build {
  sources = ["source.vsphere-iso.ubuntu"]

  provisioner "shell" {
    inline = [
      "while [ ! -f /var/lib/cloud/instance/boot-finished ]; do echo 'Waiting for cloud-init...'; sleep 2; done",
      "sudo apt-get update",
      "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y open-vm-tools openssh-server lvm2 xfsprogs",
    ]
  }

  provisioner "shell" {
    inline = [
      "set -eu",
      "echo 'Disabling unattended apt activity for Kubernetes node template...'",
      "sudo systemctl stop unattended-upgrades.service apt-daily.service apt-daily-upgrade.service 2>/dev/null || true",
      "sudo systemctl disable unattended-upgrades.service apt-daily.service apt-daily-upgrade.service 2>/dev/null || true",
      "sudo systemctl stop apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true",
      "sudo systemctl disable apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true",
      "sudo systemctl mask apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true",
      "sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'\nAPT::Periodic::Update-Package-Lists \"0\";\nAPT::Periodic::Download-Upgradeable-Packages \"0\";\nAPT::Periodic::AutocleanInterval \"0\";\nAPT::Periodic::Unattended-Upgrade \"0\";\nEOF",
      "sudo apt-get remove --purge -y unattended-upgrades || true",
      "sudo rm -f /etc/apt/apt.conf.d/50unattended-upgrades",
      "systemctl is-enabled apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true",
      "test ! -e /etc/apt/apt.conf.d/50unattended-upgrades"
    ]
  }

  provisioner "shell" {
    inline = [
      "sudo apt-get autoremove -y",
      "sudo apt-get clean",
      "sudo rm -rf /var/lib/apt/lists/*"
    ]
  }
}
```

If the organization prefers keeping the package installed but inert, omit the `apt-get remove --purge` line and keep the config plus masked timers. The important part is that the image declares the operational boundary: Kubernetes node patching is owned by maintenance automation, not by background apt timers.

For a more modular Packer layout, keep the policy in a dedicated script and call it from the template:

```hcl
provisioner "file" {
  source      = "scripts/disable-unattended-upgrades.sh"
  destination = "/tmp/disable-unattended-upgrades.sh"
}

provisioner "shell" {
  inline = [
    "sudo install -m 0755 -o root -g root /tmp/disable-unattended-upgrades.sh /usr/local/sbin/disable-unattended-upgrades",
    "sudo /usr/local/sbin/disable-unattended-upgrades",
    "sudo rm -f /usr/local/sbin/disable-unattended-upgrades"
  ]
}
```

That keeps the Packer HCL readable while still making the image build fail if the policy script fails. Do not leave this as a wiki-only instruction. If the template is the source of truth for node operating-system behavior, the unattended-upgrades state belongs in the template build.

## Ansible Pattern

In Ansible, avoid capturing newline-separated PIDs and passing them directly to `kill`. A task like this is unsafe when `pgrep` returns more than one process:

```yaml
shell: "kill -9 {{ apt_get_pid.stdout }}"
```

Use services first, then verify, then process cleanup only as a last resort.

```yaml
vars:
  apt_timers:
    - apt-daily.timer
    - apt-daily-upgrade.timer
  apt_services:
    - apt-daily.service
    - apt-daily-upgrade.service
    - unattended-upgrades.service

tasks:
  - name: Stop and mask automatic apt timers
    ansible.builtin.systemd:
      name: "{{ item }}"
      state: stopped
      enabled: false
      masked: true
      no_block: true
    loop: "{{ apt_timers }}"
    ignore_errors: true
    tags: [unattended, disable, timers]

  - name: Stop and disable unattended upgrade services
    ansible.builtin.systemd:
      name: "{{ item }}"
      state: stopped
      enabled: false
      no_block: true
    loop: "{{ apt_services }}"
    ignore_errors: true
    tags: [unattended, disable, services]

  - name: Disable apt periodic configuration
    ansible.builtin.copy:
      dest: /etc/apt/apt.conf.d/20auto-upgrades
      owner: root
      group: root
      mode: "0644"
      content: |
        APT::Periodic::Update-Package-Lists "0";
        APT::Periodic::Download-Upgradeable-Packages "0";
        APT::Periodic::AutocleanInterval "0";
        APT::Periodic::Unattended-Upgrade "0";
    tags: [unattended, disable, config]
```

If process cleanup is still needed, separate discovery from action and handle an empty result safely:

```yaml
  - name: Find lingering apt or unattended-upgrade processes
    ansible.builtin.shell: |
      pgrep -f '(apt-get.*update|/usr/bin/apt|apt.systemd.daily|unattended-upgrade|/usr/bin/dpkg)' || true
    register: apt_lingering
    changed_when: false
    failed_when: false
    tags: [unattended, cleanup]

  - name: Force kill lingering apt processes only as a last resort
    ansible.builtin.command: "kill -9 {{ item }}"
    loop: "{{ apt_lingering.stdout_lines | map('trim') | select('match', '^\\d+$') | list }}"
    when: apt_lingering.stdout | length > 0
    ignore_errors: true
    tags: [unattended, cleanup]
```

That pattern works when zero, one, or many PIDs are returned. It also avoids failing when the discovery task is run and finds nothing.

## Purge With Lock Awareness

If the package must be purged, wait briefly for apt and dpkg locks before invoking the `apt` module:

```yaml
  - name: Wait for apt and dpkg locks to clear
    ansible.builtin.shell: |
      for i in $(seq 1 30); do
        if fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock /var/cache/apt/archives/lock >/dev/null 2>&1; then
          sleep 2
        else
          exit 0
        fi
      done
      exit 0
    changed_when: false
    failed_when: false
    tags: [unattended, purge]

  - name: Purge unattended-upgrades
    ansible.builtin.apt:
      name: unattended-upgrades
      state: absent
      purge: true
      autoremove: true
      force_apt_get: true
    register: purge_unattended
    retries: 5
    delay: 10
    until: purge_unattended is succeeded
    tags: [unattended, purge]
```

## Verify The Desired State

Verification should not depend on previous tasks having run in the same play. That matters when using `--tags verify`.

```bash
systemctl is-enabled apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service || true
systemctl is-active apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service || true
cat /etc/apt/apt.conf.d/20auto-upgrades 2>/dev/null || true
dpkg -l unattended-upgrades 2>/dev/null || true
```

Expected output for a disabled-but-installed model:

```text
APT::Periodic::Unattended-Upgrade "0";
apt-daily.timer masked
apt-daily-upgrade.timer masked
unattended-upgrades.service inactive or disabled
```

Expected output for a purged model:

```text
package not installed
timers disabled or masked
no unattended-upgrades journal activity after the change
```

Related article: [Ubuntu Unattended Upgrades Are Kubernetes Node Changes](/posts/ubuntu-unattended-upgrades-kubernetes-node-risk/).
