+++
title = 'Bootstrap Logging, Locks, And Continue-On-Failure Behavior'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note for making first-boot bootstrap scripts easier to debug by logging each stage, preventing concurrent runs, and summarizing failures.'
tags = ['bootstrap', 'linux', 'cloud-init', 'operations']
categories = ['field-notes']
+++

First-boot bootstrap scripts should be easy to debug after the VM is already running. For operational bootstrap, fail-fast is not always the best default.

If a bootstrap framework configures hostname, SSH, disks, iSCSI, and node labels, stopping at the first failure may hide useful evidence from later checks. A better pattern is to run each stage, log the result, continue, and summarize failures at the end.

## Symptoms

- Bootstrap log stops after the first or second script.
- Later configuration steps never run.
- `cloud-init-output.log` shows only partial output.
- Re-running the bootstrap manually succeeds, but first boot did not.
- Log lines appear duplicated or interleaved.

## Use A Stage Runner

Wrap each bootstrap step so failures are recorded but do not prevent later diagnostics:

```bash
#!/usr/bin/env bash
set -uo pipefail

LOG_FILE="/var/log/futurex-bootstrap.log"
FAILED_STEPS=()

log() {
  echo "[$(date -Is)] $*" | tee -a "$LOG_FILE"
}

run_step() {
  local label="$1"
  shift

  log "========== START ${label} =========="
  if "$@" 2>&1 | tee -a "$LOG_FILE"; then
    log "========== PASS ${label} =========="
  else
    local rc=${PIPESTATUS[0]}
    log "========== FAIL ${label} rc=${rc} =========="
    FAILED_STEPS+=("${label}:rc=${rc}")
  fi
}
```

Then call each stage explicitly:

```bash
run_step "01_set_hostname" sudo "${SCRIPT_DIR}/01_set_hostname.sh" "${VARS_FILE}" "${HOSTNAME_VALUE}"
run_step "02_base_and_ssh" sudo "${SCRIPT_DIR}/02_base_and_ssh.sh" "${VARS_FILE}"
run_step "05_iscsi" sudo "${SCRIPT_DIR}/05_iscsi.sh" "${VARS_FILE}"
run_step "03_data_disk_lvm" sudo "${SCRIPT_DIR}/03_data_disk_lvm.sh" "${VARS_FILE}"
run_step "04_setup_rancher_disk_label" sudo "${SCRIPT_DIR}/04_setup_rancher_dik_lable.sh" "${VARS_FILE}"
```

## Add A Summary

End every run with a summary:

```bash
log "========== BOOTSTRAP SUMMARY =========="
if (( ${#FAILED_STEPS[@]} > 0 )); then
  log "Completed with failed steps:"
  for failed in "${FAILED_STEPS[@]}"; do
    log "FAILED: ${failed}"
  done
else
  log "Completed successfully."
fi

exit 0
```

Exit `0` when the goal is evidence collection and the host should stay reachable. Use a non-zero exit only when another system must treat the bootstrap as failed.

## Prevent Concurrent Runs

If cloud-init, a systemd unit, or a manual command can trigger the same script, add a lock:

```bash
LOCK_FILE="/run/futurex-bootstrap.lock"
exec 9>"${LOCK_FILE}"

if ! flock -n 9; then
  echo "[$(date -Is)] Another futurex-bootstrap process is already running; exiting." | tee -a "$LOG_FILE"
  exit 0
fi
```

Duplicate log entries often mean the script was run twice or that an outer `tee` is also writing the same output.

## Avoid Double Logging

If the bootstrap script writes its own log, keep cloud-init simple:

```yaml
#cloud-config
runcmd:
  - [ bash, -lc, '/usr/local/bin/futurex-bootstrap' ]
```

Avoid wrapping it like this unless you intentionally want a second wrapper log:

```yaml
runcmd:
  - [ bash, -lc, '/usr/local/bin/futurex-bootstrap 2>&1 | tee -a /var/log/futurex-bootstrap.log' ]
```

## Operating Rule

Bootstrap should produce enough evidence for the next operator:

- what ran.
- what passed.
- what failed.
- what command returned the failure.
- whether a second bootstrap process tried to run.

The goal is not to hide failures. The goal is to preserve enough context to fix them without guessing.
