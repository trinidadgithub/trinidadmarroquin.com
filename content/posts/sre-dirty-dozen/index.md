+++
title = 'The SRE Dirty Dozen: Common Anti-Patterns In Site Reliability Engineering'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Twelve common anti-patterns in SRE practice: alert fatigue disguised as paging, dashboards without decisions, SLI collection without SLO targets, incident reviews without action items, and other traps that SRE teams fall into.'
tags = ['sre', 'anti-patterns', 'incidents', 'observability', 'platform']
categories = ['notes']
+++

The DevOps Dirty Dozen covered anti-patterns in DevOps culture. SRE has its own set of traps — practices that look like reliability work but do not improve reliability.

## 1. Alert Frequency As A Paging Criterion

"If it pages, it matters" sounds correct. The reality is that teams habituate to frequent pages within weeks. An alert that fires every night at 3 AM for a non-critical condition trains operators to silence notifications, miss the genuine page, and burn out.

The correct criterion is not frequency. It is whether the condition requires a human to act within minutes. Everything else is a ticket, a dashboard tile, or a log entry.

## 2. Dashboards Without Decisions

A dashboard with 50 charts and no annotation of what the operator should look for is a screensaver. Every dashboard should answer a question. If the question is not defined before the charts are added, the dashboard will accumulate visual noise until it is useless.

The pattern: title each dashboard as a question ("Is the API healthy?") and add only the metrics that answer it. Auxiliary data goes in a drill-down link.

## 3. SLI Collection Without SLO Targets

Collecting latency and error rate is not SRE. SLI data without SLO targets tells operators what is happening but not whether it is acceptable. The SLO is the decision rule that converts a metric into an operational judgment.

Without SLO targets, every latency spike is a potential incident and no one can agree on whether the system is healthy.

## 4. Error Budgets Nobody Uses

Defining an error budget and then ignoring it when making release decisions is a paperwork exercise. The error budget only matters if it changes behavior.

When the budget is exhausted, the team stops shipping features and dedicates capacity to reliability work. If that never happens, the error budget is decoration.

## 5. Incident Reviews Without Action Items

An incident review that produces a narrative but no action items is a book club. The output of a review is a set of validated actions that reduce the probability or impact of a similar incident.

The pattern: each action item must have an owner, a deadline, and a verification step. If it cannot be verified, it is not an action item.

## 6. Toil Automation That Creates More Toil

Automating a manual task by building a script that requires constant maintenance, manual input files, and debugging mid-run is not a reduction in toil. It is replacing one form of toil with another.

The test: if the automation needs an operator to intervene more than once per month, the task is not automated. It is partially delegated to a fragile script.

## 7. Pager Duty Without OODA Loops

Paging an operator without giving them the information to make a decision is ineffective. The alert should include the symptom, the affected component, a link to the relevant dashboard, and the runbook.

An alert that says "CPU is high on server X" sends the operator into a discovery loop that should have been completed before the alert fired.

## 8. Platform Teams Building What Operators Did Not Ask For

A platform team that builds abstractions without consulting the operators who will use them produces tools that do not match the operational model. The result is shadow infrastructure and workarounds.

The most reliable platform features are the ones operators contributed to the design of.

## 9. Monitoring The Symptoms, Not The Causes

Monitoring node CPU and memory is table stakes. Monitoring the causes of node CPU and memory spikes — deployment patterns, traffic shifts, certificate expiry — is where the operational leverage is.

Cause-level alerts are actionable. Symptom-level alerts are informational.

## 10. Perfect System Design Over Practical Incident Response

Teams that spend months designing the perfect system architecture while neglecting incident response practice will fail faster during an incident than a team with imperfect architecture and well-rehearsed response procedures.

Recovery speed is an architectural property, but it is also a practiced skill.

## 11. Reliability As The SRE Team's Problem

If only the SRE team cares about reliability, the SRE team will be the bottleneck for every change and the scapegoat for every incident. Reliability must be a shared concern embedded in how development, QA, and operations teams evaluate their work.

The SRE team's job is to enable and verify reliability practices, not to be the sole owner of them.

## 12. Treating The Runbook As The Solution

A runbook is documentation of a known failure mode. It is not the solution to the failure mode. If the same runbook is executed more than a few times, the condition should be automated.

The pattern: every time a runbook is used, evaluate whether the steps can be automated. If they cannot be automated, evaluate whether the system can be changed to eliminate the failure mode.
