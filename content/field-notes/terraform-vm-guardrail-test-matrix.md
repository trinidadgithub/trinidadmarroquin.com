+++
title = 'Terraform VM Guardrail Test Matrix'
date = 2026-06-15T00:00:00-05:00
draft = false
description = 'A reusable test matrix for validating Terraform VM guardrails across duplicate input, NetBox ownership, vCenter inventory, DNS, active IP detection, and fail-closed provider behavior.'
tags = ['terraform', 'vsphere', 'netbox', 'testing', 'validation', 'automation', 'operations']
categories = ['field-notes']
+++

Use this matrix to prove VM provisioning guardrails before trusting automation with real vSphere creates.

The point is not to make every test pass green. The point is to prove each unsafe condition fails at the correct layer.

## Baseline Commands

Generate a plan and plan JSON:

```bash
terraform init
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
```

Run preflight:

```bash
./scripts/preflight-vm-guardrails.sh --plan-json tfplan.json
```

Confirm clean post-apply state when a test intentionally creates a disposable VM:

```bash
terraform apply tfplan
terraform plan -detailed-exitcode
```

## 1. Clean New VM

Test:

```text
Plan one new VM name and one unused IP address.
```

Expected:

```text
terraform plan succeeds
preflight passes
NetBox resources are planned when enabled
terraform apply succeeds for disposable test target
follow-up plan shows no changes
```

Proof to capture:

- VM name.
- IP and prefix.
- DNS name.
- planned NetBox VM/interface/IP/primary-IP resources.
- clean `terraform plan -detailed-exitcode` after apply.

## 2. Duplicate IP Inside Terraform Config

Test:

```text
Set two planned VMs to the same ipv4_address.
```

Command:

```bash
terraform plan -out=/tmp/duplicate-ip-test.tfplan
```

Expected failure:

```text
VM IPv4 addresses must be unique within var.vms.
```

Layer responsible:

```text
Terraform variable validation
```

## 3. Duplicate VM Name Inside Terraform Config

Test:

```text
Set two planned VMs to the same name.
```

Command:

```bash
terraform plan -out=/tmp/duplicate-name-test.tfplan
```

Expected failure:

```text
VM names must be unique within var.vms.
```

Layer responsible:

```text
Terraform variable validation
```

## 4. IP Already Exists In NetBox

Test:

```text
Use an IP address that already exists in NetBox.
```

Command:

```bash
./scripts/preflight-vm-guardrails.sh --plan-json tfplan.json
```

Expected failure:

```text
NetBox already has IP '192.0.2.10' (192.0.2.10/24 status=active dns=cluster-a-worker-01.example.com).
```

Layer responsible:

```text
Preflight NetBox check
NetBox provider resource on apply
```

## 5. VM Name Already Exists In NetBox

Test:

```text
Use a VM name that already exists in NetBox.
```

Command:

```bash
./scripts/preflight-vm-guardrails.sh --plan-json tfplan.json
```

Expected failure:

```text
NetBox already has VM 'cluster-a-worker-01'.
```

Layer responsible:

```text
Preflight NetBox check
NetBox provider resource on apply
```

## 6. VM Exists In vCenter But Not NetBox

Test:

```text
Use a VM name that exists in vCenter but does not exist in NetBox.
```

Command:

```bash
./scripts/preflight-vm-guardrails.sh \
  --plan-json tfplan.json \
  --skip-netbox \
  --skip-dns \
  --skip-nmap
```

Expected failure:

```text
vCenter already has VM 'cluster-a-worker-01': /DC-Site-A/vm/K8s-Cluster/Prod/cluster-a-worker-01.
```

Also test missing `govc` configuration:

```bash
env -u GOVC_URL -u GOVC_USERNAME -u GOVC_PASSWORD \
  ./scripts/preflight-vm-guardrails.sh \
  --plan-json tfplan.json \
  --skip-netbox \
  --skip-dns \
  --skip-nmap
```

Expected failure:

```text
vCenter checks require a working govc configuration.
```

Layer responsible:

```text
Preflight vCenter check
```

## 7. IP Active On Network But Not In NetBox

Test:

```text
Use an IP that responds to nmap -sn -n but has no NetBox record.
```

Command:

```bash
./scripts/preflight-vm-guardrails.sh \
  --plan-json tfplan.json \
  --skip-netbox \
  --skip-govc \
  --skip-dns
```

Expected failure:

```text
Network scan indicates planned IP '192.0.2.10' is already active.
```

Layer responsible:

```text
Preflight nmap check
```

Note: if the plan includes already-managed active VMs, the scan may flag those too. That is expected if the script scans all planned static IPs instead of only create/update actions.

## 8. Reverse DNS Exists

Test:

```text
Use an IP with an existing PTR record.
```

Candidate checks:

```bash
dig +short -x '192.0.2.10'
getent hosts '192.0.2.10'
```

Preflight command:

```bash
./scripts/preflight-vm-guardrails.sh \
  --plan-json tfplan.json \
  --skip-netbox \
  --skip-govc \
  --skip-nmap
```

Expected failure:

```text
Reverse DNS/getent already resolves planned IP '192.0.2.10'.
```

Layer responsible:

```text
Preflight reverse DNS check
```

## 9. Forward DNS Exists For VM Name

Test:

```text
Use a VM name that already resolves in DNS.
```

Candidate check:

```bash
getent hosts 'cluster-a-worker-01'
getent hosts 'cluster-a-worker-01.example.com'
```

Preflight command:

```bash
./scripts/preflight-vm-guardrails.sh \
  --plan-json tfplan.json \
  --skip-netbox \
  --skip-govc \
  --skip-nmap
```

Expected failure:

```text
DNS already resolves planned VM name 'cluster-a-worker-01'.
```

Layer responsible:

```text
Preflight forward DNS check
```

## 10. NetBox Enabled Without Provider Credentials

Test:

```text
Set netbox_enabled = true and remove NETBOX_SERVER_URL / NETBOX_API_TOKEN.
```

Command:

```bash
unset NETBOX_SERVER_URL
unset NETBOX_API_TOKEN
terraform plan -out=/tmp/missing-netbox-creds.tfplan
```

Expected failure:

```text
Error: Missing required argument
The argument "server_url" is required

Error: Missing required argument
The argument "api_token" is required
```

Layer responsible:

```text
Terraform provider configuration
```

## 11. Preflight Without NetBox Credentials

Test:

```text
Run preflight without NetBox credentials.
```

Command:

```bash
unset NETBOX_SERVER_URL
unset NETBOX_API_TOKEN
./scripts/preflight-vm-guardrails.sh --plan-json tfplan.json --skip-govc
```

Expected warning, if degraded mode is intentional:

```text
Warnings:
  - Skipping NetBox checks because NetBox URL/token environment variables or --netbox-url/--netbox-token were not provided.
```

Expected behavior:

```text
DNS and nmap checks continue after the NetBox warning.
```

Layer responsible:

```text
Preflight degraded-mode handling
```

## 12. NetBox Cluster Missing

Test:

```text
Set netbox_enabled = true and use a non-existent netbox_cluster_name.
```

Command:

```bash
terraform plan -out=tfplan \
  -var='netbox_cluster_name=missing-cluster-test'
```

Expected failure:

```text
Error: no result
with module.vm_group.data.netbox_cluster.cluster[0]
```

Layer responsible:

```text
Terraform NetBox data lookup
```

## 13. NetBox Unreachable

Test:

```text
Point the NetBox provider at an unreachable endpoint.
```

Command:

```bash
NETBOX_SERVER_URL="https://netbox-unreachable.invalid" \
NETBOX_API_TOKEN="dummy" \
NETBOX_SKIP_VERSION_CHECK=true \
terraform plan -out=/tmp/netbox-unreachable-test.tfplan
```

Expected failure:

```text
Planning failed.
Error: Get "https://netbox-unreachable.invalid/api/..."
```

Layer responsible:

```text
Terraform NetBox provider/data lookup
```

Desired outcome:

```text
NetBox unreachable -> Terraform plan fails -> vSphere VM is not created
```

## Test Cleanup

For each destructive or collision test:

- add only one temporary collision at a time.
- run the test.
- save the exact output.
- revert the temporary config immediately.
- confirm no diff remains.

Cleanup checks:

```bash
git status --short -- path/to/test/env
git diff -- path/to/test/env
```

## Operating Rule

A VM guardrail is not proven until every unsafe path fails where you expect it to fail.

Document the test, the command, the observed output, and the cleanup state.
