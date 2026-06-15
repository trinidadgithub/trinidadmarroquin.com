+++
title = 'Terraform vSphere VM Preflight Guardrails'
date = 2026-06-15T00:00:00-05:00
draft = false
description = 'Field note for checking Terraform-planned vSphere VM names and IPs against NetBox, vCenter, DNS, reverse DNS, and live network responses before apply.'
tags = ['terraform', 'vsphere', 'netbox', 'govc', 'dns', 'automation', 'operations']
categories = ['field-notes']
+++

Terraform can validate its own input, but it cannot automatically prove that the outside world is clear.

Before applying a vSphere VM plan, run preflight checks against the systems that already know about names and addresses.

## Generate Plan JSON

Use the plan as the preflight input:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
```

Then run the guardrail script:

```bash
./scripts/preflight-vm-guardrails.sh --plan-json tfplan.json
```

## Inputs To Extract

From the plan JSON, extract each planned VM's:

- Terraform address.
- VM name.
- IPv4 address.
- prefix length.
- DNS name, if generated.
- NetBox enabled/disabled state.

Do not scrape HCL directly when a plan JSON is available. The plan reflects variables, locals, defaults, and module expansion after Terraform evaluation.

## NetBox Checks

Check whether NetBox already has the planned VM name:

```text
GET /api/virtualization/virtual-machines/?name=<planned-name>
```

Check whether NetBox already has the planned IP:

```text
GET /api/ipam/ip-addresses/?address=<planned-ip>
```

Fail on exact matches:

```text
Failures:
  - NetBox already has VM 'cluster-a-worker-01'.
  - NetBox already has IP '192.0.2.10' (192.0.2.10/24 status=active dns=cluster-a-worker-01.example.com).
```

If NetBox credentials are missing, decide intentionally:

- fail if NetBox checks are mandatory for the environment.
- warn and continue only if the script explicitly supports degraded mode.

Example warning for degraded mode:

```text
Warnings:
  - Skipping NetBox checks because NetBox URL/token environment variables or --netbox-url/--netbox-token were not provided.
```

## vCenter Checks

Use `govc` to check whether the VM name already exists in vCenter:

```bash
govc find / -type m -name 'cluster-a-worker-01'
```

Failure example:

```text
Failures:
  - vCenter already has VM 'cluster-a-worker-01': /DC-Site-A/vm/K8s-Cluster/Prod/cluster-a-worker-01.
```

Do not silently skip this check when `govc` is broken.

If vCenter checks are enabled, verify `govc` first:

```bash
govc about >/dev/null
```

Failure example:

```text
Failures:
  - vCenter checks require a working govc configuration. Export GOVC_URL, GOVC_USERNAME, GOVC_PASSWORD, and GOVC_INSECURE as needed, or rerun with --skip-govc.
```

## Forward DNS Checks

Check whether the planned VM name already resolves:

```bash
getent hosts 'cluster-a-worker-01'
getent hosts 'cluster-a-worker-01.example.com'
```

Failure example:

```text
Failures:
  - DNS already resolves planned VM name 'cluster-a-worker-01'.
```

Forward DNS catches stale names that may not exist in NetBox or vCenter anymore.

## Reverse DNS Checks

Check whether the planned IP has a PTR record:

```bash
dig +short -x '192.0.2.10'
```

Fallback if `dig` is unavailable:

```bash
getent hosts '192.0.2.10'
```

Failure example:

```text
Failures:
  - Reverse DNS/getent already resolves planned IP '192.0.2.10'.
```

Reverse DNS is useful because PTR records often outlive the systems they describe.

## Network Liveness Checks

Check whether the planned IP responds on the network:

```bash
nmap -sn -n '192.0.2.10'
```

Failure example:

```text
Failures:
  - Network scan indicates planned IP '192.0.2.10' is already active.
```

This catches the important case where an address is active but missing from NetBox.

## Skip Flags

Skip flags are useful for isolated tests and controlled degraded mode:

```bash
./scripts/preflight-vm-guardrails.sh \
  --plan-json tfplan.json \
  --skip-netbox \
  --skip-govc \
  --skip-dns \
  --skip-nmap
```

But skip flags should be visible in the summary:

```text
Preflight VM guardrail summary
Planned VMs checked: 2
NetBox checks: skipped
vCenter checks: enabled
DNS checks: enabled
nmap checks: enabled
```

## Safe Summary Format

Make the output explicit enough to paste into a change record:

```text
Preflight VM guardrail summary
Planned VMs checked: 2
NetBox checks: enabled
vCenter checks: enabled
DNS checks: enabled
nmap checks: enabled
Warnings: 0
Failures: 0
```

On failure, include the exact proof:

```text
Failures:
  - vCenter already has VM 'cluster-a-worker-01': /DC-Site-A/vm/K8s-Cluster/Prod/cluster-a-worker-01.
  - DNS already resolves planned VM name 'cluster-a-worker-01'.
  - Network scan indicates planned IP '192.0.2.10' is already active.
```

## Operating Rule

Terraform plan answers “what will Terraform try to do?”

Preflight answers “is the outside world clear enough for Terraform to do it safely?”

Run both before creating vSphere VMs from automation.
