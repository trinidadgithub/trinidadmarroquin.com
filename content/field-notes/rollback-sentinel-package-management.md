+++
title = 'Rollback Strategies With Sentinel Files And Package Management'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for automated rollback patterns using sentinel files for failure detection and dpkg package management for version reversal.'
tags = ['deployment', 'cicd', 'puppet', 'automation']
categories = ['field-notes']
+++

Rollback is a deployment strategy that gets rehearsed less often than it should. A rollback plan that has never been tested is not a rollback plan.

## The Sentinel File Pattern

A sentinel file marks a failure condition. When it exists, automation triggers a rollback. In a Puppet-based lab:

```puppet
exec { 'rollback-to-v1':
  command => 'dpkg --force-depends -i /opt/v1/c-app.deb',
  onlyif  => 'test -f /tmp/simulate_failure',
}
```

The sentinel file is a teaching proxy. In production, the sentinel would be a health check failure, a metrics threshold breach, or a monitoring alert.

## Conditional Execution

Puppet's `onlyif` and `unless` control when rollback resources execute:

- `onlyif` runs the command only if the condition is true.
- `unless` runs the command only if the condition is false.

```puppet
exec { 'check-not-rolled-back':
  command => 'echo already rolled back',
  unless  => 'dpkg -l c-app | grep -q v2',
}
```

The rollback should be idempotent. Running it twice should not cause a second rollback attempt.

## Package-Level Rollback

`dpkg --force-depends -i` installs a `.deb` file and replaces the current version. This is fast and works at the package level, but it has significant limitations:

- no database migration rollback.
- no cache invalidation.
- no session drain.
- no downstream dependency coordination.
- no state rollback.

Package rollback is appropriate for stateless services. Stateful services require schema versioning, data recovery plans, and coordinated service restarts.

## Dependency Chaining

```puppet
exec { 'cleanup-v2-artifacts':
  command => 'rm -rf /opt/v2',
  require => Exec['rollback-to-v1'],
}
```

The cleanup only runs after the rollback completes. This prevents orphaned artifacts from causing confusion during the next deployment.

## Production Rollback Checklist

Before relying on an automated rollback:

- [ ] Can the previous version be restored within the recovery SLO?
- [ ] Are database schema changes reversible?
- [ ] Is there a way to invalidate cached data from the failed version?
- [ ] Are downstream services aware of the rollback?
- [ ] Has the rollback been tested in a non-production environment?
- [ ] Is there a communication plan for the rollback event?

## Acceptance Criteria

- Rollback triggers on sentinel file or health check failure.
- Rollback is idempotent.
- Previous version is restored without manual intervention.
- Post-rollback cleanup removes artifacts from the failed version.
- Rollback duration is measured and documented.
