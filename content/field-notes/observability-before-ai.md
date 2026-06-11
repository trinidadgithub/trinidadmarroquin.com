+++
title = 'Observability Before AI: What Every Operator Needs First'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for building observability foundations before introducing AI-assisted operations: structured metrics, actionable dashboards, coherent alert routing, and incident response patterns that make AI useful rather than noisy.'
tags = ['observability', 'monitoring', 'alerting', 'sre', 'incidents']
categories = ['field-notes']
+++

AI-assisted operations tools are entering the market rapidly. Their value depends entirely on the quality of the observability data they consume. If the data is noisy, incomplete, or unstructured, AI tools amplify the noise instead of reducing it.

This field note covers the foundations every operator should have in place before adding AI to the observability stack.

## Required Foundations

### Structured Metrics

Metrics must have consistent labels across services. The same label (`service`, `environment`, `region`) should mean the same thing in every metric. If one service uses `env` and another uses `environment`, any tool consuming both will produce unreliable correlations.

```text
# Good
http_requests_total{service="api", environment="prod", region="us-east-1"} 1024

# Bad (consumers cannot reliably aggregate)
http_requests_total{svc="api", env="prod", az="us-east-1a"} 1024
requests{service="api", region="us-east-1"} 2048
```

### Actionable Dashboards

Every dashboard should answer a specific question. Questions like "is the service healthy?" and "is the deployment progressing?" are valid. Questions like "what do all these charts mean?" are not.

A dashboard that takes more than 30 seconds to read during an incident will not be read during an incident.

Structured dashboards — SLO at the top, symptom metrics in the middle, cause metrics below — give operators a consistent mental model across services. AI tools that consume dashboard state as context benefit from this structure because the relationship between metrics is already defined.

### Coherent Alert Routing

Alert routing that mirrors the team structure makes AI-assisted triage more effective. If an AI tool receives an alert about a service, it should be able to determine which team owns it, which runbook applies, and where to route the notification.

Without structured routing, the AI tool either guesses or sends everything to a single channel, replicating the same problem the team already has.

### Consistent Incident Response

Observability AI tools learn from incident response patterns. If every incident is handled differently — different communication channels, different severity definitions, different escalation paths — the AI cannot build a useful response model.

Standardize the incident response process before expecting AI to augment it.

## What AI Can Add (After The Foundations)

Once the foundations are in place, AI-assisted operations can help with:

- **Anomaly correlation.** Identifying that a latency spike and an error rate increase in different services share a root cause (e.g., a shared database or network link).
- **Runbook suggestion.** Recommending the relevant runbook based on the alert context and historical incidents.
- **Incident timeline generation.** Building a timeline from alert history, deployment events, and change records.
- **Post-incident pattern analysis.** Identifying recurring incident types across services that share a common vulnerability.

None of these work if the underlying data is unstructured, inconsistent, or noisy.

## What AI Cannot Fix

- **Missing metrics.** If the service emits no metrics, no AI can diagnose it.
- **Undefined SLOs.** If the team has not defined acceptable reliability, no AI can tell them whether the system is healthy.
- **Broken alert routing.** If alerts go to the wrong team, AI cannot route them correctly without structured ownership data.
- **No incident response process.** AI can suggest actions, but if there is no team to execute them, the suggestions have no operational effect.

## The Order Of Operations

```text
1. Define SLOs for each service.
2. Instrument services with structured metrics.
3. Build dashboards that answer specific questions.
4. Configure alert routing that matches team ownership.
5. Establish a consistent incident response process.
6. Automate runbook steps where possible.
7. THEN evaluate AI-assisted operations tools.
```

Skipping any step before step 7 means the AI tool will be limited by the quality of the foundation it runs on.
