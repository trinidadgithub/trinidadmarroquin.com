+++
title = 'Kubernetes Audit Logging Field Note'
date = 2026-08-10T00:00:00-05:00
draft = false
description = 'Operational field note for Kubernetes audit logging: what to capture, where it lands, retention, triage queries, and the failures that make audit logs useless in an incident.'
tags = ['kubernetes', 'security', 'audit-logging', 'observability', 'platform-engineering', 'operations', 'compliance']
categories = ['field-notes']
+++

Kubernetes audit logging is the record of what happened to the cluster API.

If it is not configured, enabled, and retained, a suspicious delete, a bad RBAC escalation, or a credential misuse becomes a debate instead of a line in a log. The API server generates the events; the platform team is responsible for making them useful.

This note covers operating audit logs as working evidence, not just configuration.

## What Gets Recorded

Audit log lines describe request-level events against the API server:

- request user and groups.
- verb and resource.
- namespace and object name.
- source IP and user agent.
- response status.
- request and response bodies when requested.
- annotations set by admission controllers.

One delete of a Secret emits one line. The investigation value comes from reading that line and the surrounding context, not from the count.

## Where It Lands

The audit log goes wherever you point the API server:

```text
--audit-log-path=/var/log/kubernetes/audit/audit.log
--audit-log-maxsize=100
--audit-log-maxbackup=10
--audit-log-maxage=30
```

In RKE2 the API server flags are set through:

```text
/etc/rancher/rke2/config.yaml:

kube-apiserver-arg:
  - "audit-log-path=/var/log/kubernetes/audit/audit.log"
  - "audit-log-maxsize=100"
  - "audit-log-maxbackup=10"
  - "audit-log-maxage=30"
  - "audit-policy-file=/etc/rancher/rke2/audit-policy.yaml"
```

For a self-managed control plane, the policy file path and the log path must both be readable by the API server.

The log staying local to the control plane node is a single point of failure. Stream it off-box for retention and investigation:

```text
filebeat / fluent-bit / vector -> centralized log store
```

Local rotation keeps the log bounded; remote shipping keeps it survivable.

## The Policy File

The policy decides which requests generate audit events. It should be the smallest set that keeps investigation possible.

A minimum useful policy:

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
omitStages:
  - "RequestReceived"
rules:
  - level: None
    users: ["system:kube-proxy", "system:apiserver"]
  - level: None
    resources:
      - group: "storage.k8s.io"
        resources: ["volumeattachments"]
  - level: RequestResponse
    verbs: ["delete", "update", "patch"]
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets", "configmaps"]
  - level: Metadata
  - level: Request
    verbs: ["create", "delete", "update", "patch"]
```

Order matters: the first matching rule applies. Put the noise-killers first, then the controls, then a reasonably tight catch-all at Metadata level.

## What To Capture At Metadata vs RequestResponse

- **Metadata**: user, verb, resource, source. Enough for most investigations.
- **Request/RequestResponse**: captures request bodies. Useful for config change review. Expensive at volume.
- **None**: suppression for high-volume read endpoints and system agents.

Capture full bodies for write verbs and metadata for everything else. Do not capture full bodies for list and get across the whole cluster.

## Verify It Is On Before You Need It

```bash
sudo ls -la /var/log/kubernetes/audit/
sudo tail -5 /var/log/kubernetes/audit/audit.log
```

Check the API server command line actually includes the flags:

```bash
sudo cat /proc/$(pgrep -f kube-apiserver | head -1)/cmdline | tr '\0' ' ' | grep -o 'audit[^ ]*'
```

Check for the `RequestReceived` stage appearing in the log. If only `ResponseComplete` shows, the omitStages configuration is shaping the output, which is deliberate, but it changes what is searchable.

## Triage Queries

Who deleted a namespace:

```bash
grep '"verb":"delete"' audit.log | grep 'resource":"namespaces"'
```

Who wrote to a Secret:

```bash
grep 'resource":"secrets"' audit.log | grep -E '"verb":"(create|update|patch|delete)"'
```

Who impersonated or used a service account:

```bash
grep -E 'system:serviceaccount|actuser' audit.log
```

Who hit the API from an unexpected source:

```bash
grep '"verb":"delete"' audit.log | grep -v 'user":"system:'
```

Capture the full line including the user and sourceIP fields before pivoting to other systems. The audit line is the anchor for the rest of the investigation.

## Correlation Fields

Give each line enough context to be traced:

- cluster or control plane node name.
- requestID, if available.
- source IP.
- role or service account.
- timestamp matching the incident window.

If the log line cannot be tied back to a user, a service account, a node, and a time, it answers "what" but not "who" or "why".

## Common Failure Modes

### Audit Logging Disabled

The cluster runs for months with no audit configuration. The first bad action produces no evidence at all.

### Local-Only Rotation Deleted The Evidence

The API server never runs with `--audit-log-path` writing to a persistent or shipped destination. After 30 days, the incident is unrecoverable from the log.

### Policy Filters The Event You Need

A tight policy at Metadata level still records verbs, but a rule with `level: None` for a broad resource group can suppress the exact writes in scope.

### Logs Available, Not Searchable

Audit output lands on a node and is never ingested. Investigators cannot query it during an incident, so it effectively does not exist.

### Reviewed Only During Audits

Nobody reads the logs until a compliance check. By then, retention has already rolled the evidence away.

## Review Checklist

- Is audit logging enabled on every control plane node?
- Does the policy file capture write verbs at RequestResponse?
- Are Secrets and ConfigMap writes retained at Metadata or better?
- Are high-noise system agents suppressed deliberately, not accidentally?
- Are logs shipped off-box for retention and search?
- Is retention aligned with the incident and compliance window?
- Can `who deleted this`, `who wrote this`, and `who wore this identity` be answered from the logs?
- Is there a documented test that the audit stream is live?

## Practical Takeaway

Audit logs are only useful when they are enabled, bounded, searchable, and retained.

Wire the policy to the real investigation questions, ship the stream off-box, and verify the path with a test action. A log you can search in the middle of an incident is worth more than a policy file you only show during an audit.

## References

- [SRE Agent Kubernetes Log Access RBAC](/field-notes/sre-agent-kubernetes-log-access-rbac/)
- [Pod Security Standards For Platform Teams](/field-notes/security/pod-security-standards-for-platform-teams/)
- [Kubernetes Maintenance Evidence Bundles](/field-notes/kubernetes-maintenance-evidence-bundles/)