+++
title = 'STIG-Oriented Linux Baseline Review'
date = 2026-08-10T00:00:00-05:00
draft = false
description = 'Operational field note for STIG-oriented Linux baseline reviews: what STIG profile actually controls, automated content, verification, deviation handling, and review evidence.'
tags = ['security', 'stig', 'compliance', 'linux', 'openscap', 'platform-engineering', 'operations']
categories = ['field-notes']
+++

A STIG-oriented Linux baseline review checks a system against the hardening requirements that the security technical implementation guide defines.

For platform teams, STIG work is usually about proving a defensible baseline exists: no root logins, sane permissions, locked-down services, audit enabled, and deviations that have an owner. This note is about running that review with automated content instead of a checklist walked by hand.

## What A STIG Baseline Actually Controls

STIG content for Red Hat and Ubuntu distributions covers roughly the same layers:

- authentication and account policy (password aging, lockout, sudo config).
- service and software inventory (enablement, packages).
- file permissions and ownership.
- kernel and sysctl hardening (network, core dumps).
- audit daemon and audit rules.
- SSH configuration.
- time sync and logging.

The profile is prescriptive. The platform question is which regulatory or contractual requirement makes a specific profile the right target.

## Map The Requirement, Not Just The Distro

A STIG requirement usually names:

- the control family (IA, AC, AU, CM, SC).
- the STIG version for the OS release.
- a profile identifier, for example the STIG profile in the distribution's security content.

Record the source requirement with the review. "We checked a profile" is not the same as "we checked the profile the contract requires."

## Run Against Real Content

Use automated content instead of a hand-built checklist:

```bash
yum install scap-security-guide openscap-scanner
oscap xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_stig \
  --results stig-results.xml \
  --report stig-report.html \
  /usr/share/xml/scap/ssg/content/ssg-rhel8-ds.xml
```

The report and results XML are your evidence. Re-run the same command after fixes with the same profile identifier so pass/fail changes are comparable.

Inspect the raw results to see which rule an OVAL check relies on before you file or dismiss a finding.

## Read The Fails Like A Triage

Group STIG failures into real drift, config choice, and content limitations:

- **Real drift**: a control no longer matches the expected state.
- **Config choice**: the platform intentionally deviates, for example a required auto-login control that conflicts with the system's purpose.
- **Content false positive**: the OVAL rule expects a path, package, or setting the deployment does not use.

Confirm each questionable fail with a single command before writing remediation. For example, a rule firing on `/etc/shadow` permissions that are actually 0000 by design needs a documented deviation, not a permission change that breaks authentication.

## Deviation Entries

Every config-choice and false-positive item gets a deviation line:

```text
Rule: xccdf_org.ssgproject.content_rule_accounts_password_pam_pwhistory
Verdict: Fail, deviation
Reason: password history enforced by realm group policy, not local PAM;
       local control intentionally disabled to avoid conflict.
Owner: platform team
Re-evaluate: next quarterly review
```

A deviation is defensible when it names the rule, states the reason, names an owner, and sets a re-evaluation date.

## Verify Fixes With The Same Content

After changing a control, re-run the scan and confirm the rule is now Pass in the same profile:

```bash
oscap xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_stig \
  --results stig-results-retest.xml \
  /usr/share/xml/scap/ssg/content/ssg-rhel8-ds.xml
```

Keep both result files. The retest result is the remediation evidence.

## Evidence Retention

For each review window keep:

- the STIG source requirement and profile identifier.
- the OS release and patch level reviewed.
- the scan date.
- the results XML and report.
- the triage notes for each fail.
- deviations with owners and re-evaluation dates.
- outstanding items and owners.

## Common Failure Modes

### No Pinned Profile

The review uses "the STIG profile" without the profile identifier. The next run uses a different profile and nobody notices what changed.

### Hand-Walked Checklist

A human clicks through a guide and the pass/fail state is never compared to automated results. Evidence is anecdotes.

### Fixing The Symptom

A rule touches a config file that package updates rewrite, so the fix passes the scan and drifts on the next package update. Reuse automation or template the baseline.

### Deviations Without Owners

The report shows fails that are "expected" but nobody recorded the rule number, the reason, or who owns the decision.

### No Retest

Fixes are assumed. The same profile is never re-run, so the pass state is unverified.

## Review Checklist

- Is the profile identifier for the OS pinned and recorded?
- Is the review tied to a specific STIG source requirement?
- Does the scan use automated SCAP content, not a hand checklist?
- Are fails triaged into real drift, config choice, and content limitation?
- Does every deviation name the rule, reason, owner, and re-evaluation date?
- Are fixes re-verified against the same profile?
- Are raw XML results and reports retained?
- Is a re-review scheduled to catch package or config drift?

## Practical Takeaway

A STIG review earns its value from pinned profiles, automated content, and owned deviations.

Run real SCAP content against the required profile, triage every fail explicitly, document deviations with owners, and re-run the profile to verify fixes. The evidence is the results XML plus the deviation log, reviewed on a schedule.

## References

- [CIS Benchmark Review Process](/field-notes/security/cis-benchmark-review-process/)
- [Ubuntu Unattended Upgrades Kubernetes Nodes](/field-notes/ubuntu-unattended-upgrades-kubernetes-nodes/)
- [DevOps SRE Linux Workstation](/field-notes/devops-sre-linux-workstation/)