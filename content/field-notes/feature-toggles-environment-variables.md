+++
title = 'Feature Toggles With Environment Variables'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for using environment variables as feature toggles, including cross-language patterns and the limits of the approach.'
tags = ['deployment', 'cicd', 'docker', 'python']
categories = ['field-notes']
+++

Environment variable toggles are the simplest form of feature flag. No SDK, no external service, no runtime dependency. The application reads an env var at startup and enables or disables behavior accordingly.

## The Pattern

Python:

```python
import os

feature_enabled = os.getenv("FEATURE_ENABLED", "false").lower() == "true"

if feature_enabled:
    # new behavior
else:
    # old behavior
```

C:

```c
#include <stdlib.h>
#include <string.h>

const char* val = getenv("FEATURE_ENABLED");
int feature_enabled = (val != NULL && strcmp(val, "true") == 0);
```

Both implementations check a single environment variable. The toggle is consistent across languages.

## Cross-Language Gotchas

C's `strcmp` is case-sensitive. `FEATURE_ENABLED=True` evaluates to false. Python's `.lower()` normalizes the input. Standardize on lowercase `true`/`false` values across all services to avoid surprises.

## No Runtime Reload

An env-var toggle requires a process restart to take effect. The container must be redeployed with the new variable value.

This is the biggest limitation of the pattern. True feature flag platforms offer runtime reconfiguration, gradual rollout, targeting, and kill switches without redeployment. Env-var toggles are static.

When env-var toggles are appropriate:

- CI/CD gating (enable a step only in certain pipelines).
- deployment-specific behavior (debug logging, alternative endpoints).
- off-switch for a risky feature that can wait for a redeploy.
- lab and development environments where external dependencies add friction.

When they are not:

- incident response (you cannot redeploy during an outage).
- gradual rollouts (you need targeting or percentage-based flags).
- tenant-specific behavior (each customer needs different flags).

## Docker Compose Integration

```yaml
services:
  app:
    environment:
      FEATURE_ENABLED: "true"
```

Change the value, rebuild, and redeploy. The toggle is visible in the compose file alongside other configuration.

## The Progression

```text
env var toggle -> config server -> dedicated feature flag platform
```

Start with env vars when the team is small and the deployment cadence is slow. Move to a dedicated platform when you need runtime control, gradual rollout, or audit trails.

## Acceptance Criteria

- Toggle behavior works identically in all language implementations.
- Default state (no env var set) is safe.
- Toggle is documented alongside the feature it controls.
- Toggle is removed when the feature is fully adopted.
- Toggle state is visible in logs or metrics during debugging.
