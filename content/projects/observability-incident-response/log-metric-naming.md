+++
title = 'Log And Metric Naming Conventions'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Initial conventions for log fields, metric names, labels, cardinality, and operational searchability.'
tags = ['observability', 'logging', 'metrics']
categories = ['projects']
+++

Telemetry is only useful if operators can find and compare it during pressure.

Naming conventions reduce the translation tax between teams, dashboards, alerts, and incident notes.

## Log Fields

Useful common fields:

```text
timestamp
level
service
environment
cluster
namespace
pod
trace_id
request_id
user_safe_error_code
```

Do not put secrets or personal data in logs. Redaction should be a platform expectation, not an afterthought.

## Metric Names

Metric names should describe the measured thing and unit.

Examples:

```text
http_request_duration_seconds
http_requests_total
queue_depth
volume_attach_failures_total
```

Labels should support aggregation without exploding cardinality.

Avoid labels for unbounded values such as user IDs, raw paths, request IDs, or pod UIDs unless there is a deliberate high-cardinality system for them.

## Ownership Labels

Telemetry should carry ownership context:

- service.
- team.
- environment.
- region.
- cluster.

This makes alerts routable and dashboards filterable.

## Acceptance Criteria

- Logs can be searched by service, environment, and request correlation ID.
- Metric units are clear.
- Labels do not create uncontrolled cardinality.
- Sensitive data is not logged.
- Alert labels route to the right owner.
