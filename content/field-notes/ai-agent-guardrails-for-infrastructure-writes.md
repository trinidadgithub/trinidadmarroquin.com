+++
title = 'AI Agent Guardrails For Infrastructure Writes'
date = 2026-06-12T00:00:00-05:00
draft = false
description = 'Field note for using AI agents safely during infrastructure updates, especially when the agent has tool access but may speculate or lose context.'
tags = ['ai', 'automation', 'sre', 'operations', 'infrastructure']
categories = ['field-notes']
+++

AI agents can help with infrastructure work, but tool access does not make an answer trustworthy.

Use guardrails when an agent is helping with NetBox, IPAM, Jira, Kubernetes, Terraform, or any other system where a wrong write creates cleanup work.

## Red Flags

Slow down when the agent:

- says it can write but cannot prove the target endpoint.
- assumes import behavior without testing one row.
- retries the same broken tool call repeatedly.
- switches from evidence to confident explanation.
- mixes generated examples with real environment values.
- proposes a bulk change without a dry run.
- cannot distinguish source data from desired state.
- ignores duplicate names or ambiguous matches.

## Required Behavior

For infrastructure writes, require:

- plan before execution.
- exact target system and endpoint.
- dry-run output.
- object counts before and after.
- duplicate detection.
- explicit confirmation before write.
- post-write verification.
- clear rollback or cleanup path.

Good instruction:

```text
Do not speculate. Do not guess. Show what was verified. If evidence is missing, stop and ask.
```

## Prefer Artifacts Over Chat

For bulk changes, ask for artifacts:

- CSV files.
- scripts.
- validation reports.
- duplicate reports.
- import instructions.
- dry-run logs.

Artifacts can be reviewed, versioned, and rerun. A long chat response is harder to audit.

## When To Start A New Session

Start fresh when:

- the agent keeps carrying forward a bad assumption.
- tool calls are malformed repeatedly.
- the session mixes too many unrelated tasks.
- the agent loses track of what was actually verified.
- you need a clean second opinion on generated files.

A new session is not a failure. It is a context reset.

## Operating Rule

Use AI to reduce toil, not to bypass operational discipline.

The human operator owns the source of truth, the write target, and the final verification.
