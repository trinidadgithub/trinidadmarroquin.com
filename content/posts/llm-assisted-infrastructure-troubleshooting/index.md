+++
title = 'Using LLMs During Infrastructure Troubleshooting Without Turning Off Your Brain'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Practical lessons for using LLMs during infrastructure troubleshooting while preserving operator judgment, validation, and evidence-based debugging.'
tags = ['llm', 'operations', 'troubleshooting', 'systems-thinking', 'sre']
categories = ['notes']
+++

LLMs can speed up infrastructure troubleshooting, but only if the operator stays in control.

The useful pattern is not "ask the model what is wrong and do what it says." That is risky. The better pattern is to treat the model like a second engineer who can help organize evidence, generate hypotheses, suggest verification commands, and turn the final diagnosis into reusable documentation.

That distinction matters.

During a recent Terraform and vSphere refactor, an LLM helped connect several layers of the system: Terraform modules, vSphere guest customization, Packer-built templates, cloud-init, netplan, bootstrap scripts, `govc`, iSCSI, and Kubernetes CSI. That was useful. It also suggested at least one invalid vSphere provider argument. `terraform validate` caught it.

That is the right relationship: use the model to accelerate thinking, then verify everything with the system.

## Start With Evidence

LLMs work better when the prompt includes real operational evidence instead of a vague symptom.

Useful context includes:

- exact command output.
- error messages.
- recent changes.
- relevant file snippets.
- current assumptions.
- what has already been ruled out.

For infrastructure work, a good prompt is often more like an incident handoff than a search query.

Instead of:

```text
Terraform broke my VM. What happened?
```

Use:

```text
Terraform created the VM, but vSphere guest customization failed.
Here is the exact error, the relevant main.tf block, and the toolsDeployPkg.log excerpt.
Please list likely causes ranked by evidence, and give read-only verification commands first.
```

That gives the model something to reason from.

## Ask For Diagnostic Branches

The most useful output is not a single answer. It is a short list of likely branches and how to test each one.

Example structure:

```text
Rank likely causes by evidence.
For each cause, provide:
- why it fits
- how to verify safely
- what would disprove it
- what fix should wait until verification
```

That keeps the operator from jumping straight to a fix.

In the Terraform/vSphere session, this helped separate several different failure modes:

- Terraform state/address changes during module conversion.
- vSphere guest customization failures inside the VM.
- cloud-init being disabled in the template.
- duplicate netplan files causing route conflicts.
- wrong vSphere port group backing.
- iSCSI sessions being present before CSI mapped a LUN.

Those are different problems. Treating them as one big "VM provisioning is broken" issue would have wasted time.

## Separate Safe Checks From Changes

For SRE work, prompt the model to distinguish read-only diagnostics from actions that mutate infrastructure.

Good read-only checks:

```bash
terraform state list
terraform plan -out=tfplan
terraform show -no-color tfplan > plan.txt
govc device.ls -vm /path/to/vm
govc vm.info -e /path/to/vm
ip route
cloud-init status --long
```

Potentially mutating actions:

```bash
terraform apply
terraform state mv
terraform apply -replace=...
netplan apply
iscsiadm -m node --login
```

The model can suggest both, but the operator should decide when to cross from observation to change.

## Make The Model Show Its Assumptions

One useful prompt is:

```text
What assumptions are you making, and which command would verify each one?
```

This is especially useful when a system has multiple layers. For example, when a VM could not reach its gateway, several explanations were plausible:

- wrong netmask.
- missing default route.
- wrong vSphere port group.
- firewall.
- cloud-init network conflict.

The evidence eventually showed the VM had a UAT IP address but was attached to an Internal VLAN port group. That is not something to guess. It was verified by comparing `govc device.ls` output between a working VM and a broken VM.

## Validate Provider-Specific Advice

LLMs can be wrong about provider details.

In this session, the model suggested adding unsupported vSphere network interface arguments:

```hcl
connected       = true
start_connected = true
```

Terraform rejected them:

```text
Error: Unsupported argument
```

That was a useful failure because validation caught it before apply.

The rule is simple:

```bash
terraform fmt
terraform validate
terraform plan
```

Do not trust provider syntax from memory, a blog post, or an LLM. Validate it against the provider you are actually using.

## Use The Model To Preserve The Investigation

One of the highest-value uses of an LLM is after the issue is understood.

Ask it to turn the session into reusable material:

```text
Summarize this as a field note with symptom, checks, root cause, fix, and operating model.
```

That is how a messy troubleshooting session becomes documentation.

From one Terraform/vSphere investigation, the useful outputs became separate notes:

- Terraform state moves during a module refactor.
- vSphere cloud-init guestinfo verification.
- Terraform clone customization failures.
- netplan conflicts after VMware customization.
- `govc` verification commands.
- iSCSI bootstrap readiness for Kubernetes nodes.
- first-boot ownership between Packer, Terraform, vSphere, cloud-init, and bootstrap.

Each note answers a different operational question. That is better than one giant transcript and better than several posts repeating the same lesson.

## Protect Secrets And Context

Operational prompts often include sensitive material by accident.

Before sharing content with any LLM, remove or replace:

- passwords.
- tokens.
- private keys.
- customer names if not appropriate.
- public IPs or internal hostnames if sensitive.
- real usernames when unnecessary.
- full state files.

Use representative snippets. Keep enough context to debug the issue, but not enough to leak credentials or expose infrastructure unnecessarily.

## Good Prompts For Operators

These prompts are useful during troubleshooting:

```text
List the likely causes ranked by evidence. Do not suggest fixes yet.
```

```text
Give me read-only verification commands first. Mark any command that changes state.
```

```text
What would disprove your current theory?
```

```text
Compare these two outputs and identify the operationally meaningful difference.
```

```text
Turn this diagnosis into a field note: symptom, checks, root cause, fix, and prevention.
```

```text
What advice here depends on provider-specific behavior that I should validate locally?
```

## The Operator Still Owns The System

LLMs can compress a lot of analysis time. They can also confidently suggest the wrong thing.

The operator still owns:

- judgment.
- blast radius.
- command execution.
- validation.
- rollback.
- documentation quality.

That is not a limitation. That is the right division of labor.

Use the model to speed up investigation, organize possibilities, and produce clearer notes. Do not use it to skip understanding. Infrastructure work still rewards evidence, small changes, and careful verification.

The best outcome is not that the LLM solved the problem. The best outcome is that the operator solved the problem faster and left behind better documentation for the next person.
