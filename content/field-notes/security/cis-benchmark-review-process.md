+++
title = 'CIS Benchmark Review Process'
date = 2026-08-10T00:00:00-05:00
draft = false
description = 'Operational field note for running CIS benchmark reviews on Kubernetes and Linux nodes: scoping, scanners, false positives, remediation priorities, and review evidence.'
tags = ['security', 'cis-benchmark', 'compliance', 'linux', 'kubernetes', 'platform-engineering', 'operations']
categories = ['field-notes']
+++

A CIS benchmark review produces a long list of checks. The failure is not having fails; the failure is treating every check with equal weight.

CIS profiles are dense and some controls conflict with how a platform is actually operated. This note is about reviewing CIS results in a way that produces evidence, priorities, and defensible decisions instead of a scary PDF.

## Scope First

Before running any scanner, define the scope:

- which control planes and which worker nodes.
- which benchmark version the review targets.
- which profile (L1, L2, or a curated subset).
- the remediation owner per area.
- the evidence window for the review.

A review without a version pinned is a moving target. Record the CIS benchmark version with every result set.

## Tooling

Common options for Kubernetes and node reviews:

- kube-bench: CIS Kubernetes benchmark checks against live clusters.
- lynis: general Linux hardening review, less CIS-specific.
- oscap / OpenSCAP: pulls real CIS/STIG content, richer profiles.
- vendor scanners: platform vendor audit tools map to their own guidance.

Run the scan from a system that can reach the API server and nodes with the right scope:

```bash
kube-bench run --targets master,node --version 1.x
```

Capture raw output before summarizing. The summarized pass/fail list is not the evidence; the raw findings with check numbers are.

## Read Results As Signals, Not Verdicts

Group findings into three buckets:

- **Real drift**: the check exposes behavior that should change.
- **Config choice**: the benchmark conflicts with the platform operating model.
- **Scanner artifact**: the tool cannot see the real config and reports a false or unavailable result.

Treat these differently. Only real drift drives remediation tickets.

## Common False Phantoms

Known categories to verify before filing:

- **Files below expected permissions** when the benchmark assumes a different install path. Confirm the actual path and owner.
- **API server flags reported as missing** because the scanner reads process args the way it expects, and the actual run uses a different mechanism.
- **TLS or cipher checks on components that already terminate or proxy elsewhere.**
- **Checks that assume a package manager or config layout this distro does not use.**
- **SELinux/AppArmor checks on a system where the profile is enforced but the scanner parses only a specific config file.**

For each questionable fail, run one command to confirm the actual state before writing remediation.

## Remediation Priorities

Order the real-drift findings by exposure, not by check count:

1. **Authentication and authorization gaps**: anonymous access, RBAC defaults, root logins.
2. **Rotation and certificate weaknesses**: expiring or self-signed material, weak cryptographic settings.
3. **Network exposure**: control plane or node services listening beyond intended scope.
4. **File and permission drift on core configs and service units.**
5. **Audit and logging gaps**: no audit stream, rotation, or retention.

Fix the controls that make an incident easier first. Permissions on an optional helper config are lower priority than unauthenticated API access.

## Documented Deviations

Every config-choice finding gets a deviation entry:

```text
Check: 2.x.x, kube-apiserver audit set
Result: Fail, flagged as deviation
Reason: audit policy intentionally filters health probes;
       write verbs captured at RequestResponse per operating policy.
Owner: platform team
Review: next quarterly review
```

Deviations need a reason, an owner, and a review date. A deviation documented during the review is compliance work; a deviation discovered during an audit is exposure.

## Verify Remediation With Evidence

When a finding is fixed, prove it with a command:

```bash
kube-bench run --targets master,node --check <check-number>
```

Record the pass output. Keep a per-window evidence file with:

- benchmark version.
- scan date.
- scanner and flags.
- raw output location.
- real-drift findings fixed.
- deviations with owners.
- outstanding items and owners.

## Review Signs That Safety Is Working

A review process is working when:

- results are reproducible against a pinned version.
- real drift is distinguishable from config choice.
- deviations are fewer over time, not more.
- platform changes are re-reviewed within the window.
- the review produces tickets an operator actually runs.

## Common Failure Modes

### Score-Chasing

Teams fix the easiest checks to raise a pass percentage while ignoring authentication and audit coverage. A higher score hides bigger risk.

### Version Drift

Results are compared across benchmark versions, so checks disappear, appear, or change meaning mid-review.

### Scanner Output As Truth

A scanner says a flag is missing, but the flag is set through the platform config mechanism. No one verifies the actual runtime state.

### No Owner For The Fails

Findings are emailed to a distribution list and no one is accountable for triage, deviation, or remediation.

### One-Time Review

The review runs before a target date and never again. Six months of config drift makes the next review red again.

## Review Checklist

- Is the benchmark version pinned and recorded?
- Is scope defined for control planes, workers, and version?
- Are findings triaged into real drift, config choice, and artifact?
- Does each real-drift item have an owner and target?
- Are deviations documented with reason, owner, and review date?
- Is raw scanner output retained as evidence?
- Are remediation results verified with a re-run, not assumed?
- Is a re-review scheduled within the operating window?

## Practical Takeaway

A CIS review is a triage exercise, not a test score.

Pin the version, scope the review, split real drift from config choice and scanner artifacts, and document deviations with owners. The output that matters is a short list of defensible, owned control changes plus evidence the review happened on schedule.

## References

- [STIG-Oriented Linux Baseline Review](/field-notes/security/stig-oriented-linux-baseline-review/)
- [Kubernetes Audit Logging Field Note](/field-notes/security/kubernetes-audit-logging-field-note/)
- [Ubuntu Unattended Upgrades Kubernetes Nodes](/field-notes/ubuntu-unattended-upgrades-kubernetes-nodes/)