+++
title = 'Concourse Infrastructure Workflows'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial Concourse workflow patterns for infrastructure repositories, platform changes, promotion, and failure visibility.'
tags = ['cicd', 'concourse', 'infrastructure']
categories = ['projects']
+++

Concourse works well for infrastructure when the pipeline graph tells the truth about the change flow.

Jobs should be small enough to understand and resources should capture the actual inputs.

## Pipeline Shape

Common jobs:

- lint.
- validate.
- plan.
- plan review or approval.
- apply non-production.
- apply production.
- post-apply verification.

Use serial groups for stateful targets so two applies do not compete for the same backend or environment.

## Task Design

Tasks should:

- run from versioned scripts.
- print the exact target environment.
- fail loudly on missing variables.
- keep secrets out of logs.
- publish plan or verification artifacts.

## Resource Patterns

Useful resources:

- Git repository.
- versioned image for task runtime.
- artifact store for plans.
- notification or issue tracker integration.
- environment promotion marker.

## Failure Output

A failed job should show:

- command executed.
- environment target.
- safe error output.
- link to plan or logs.
- owner or next action.

## Acceptance Criteria

- Pipeline graph matches promotion flow.
- Stateful applies are serialized.
- Plans are retained.
- Secrets are not printed.
- Operators can rerun safely after fixing inputs.
