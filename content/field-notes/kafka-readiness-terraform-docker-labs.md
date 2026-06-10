+++
title = 'Kafka Readiness Checks In Terraform Docker Labs'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for local Kafka labs where Terraform creates Docker infrastructure, waits for broker readiness, and then creates topics or starts stream processors.'
tags = ['kafka', 'terraform', 'docker', 'validation', 'automation']
categories = ['field-notes']
+++

Kafka labs are good at exposing the difference between a container being started and a broker being usable.

Terraform can create the Docker network, broker container, application image, and topics, but it needs an explicit readiness boundary. Without that boundary, the next resource may try to create topics or start a processor before Kafka is listening.

## Readiness Boundary

For a local lab, a simple port check is often enough to avoid racing the broker startup:

```bash
while ! nc -zv localhost 9092; do
  sleep 5
done
```

That check only proves that something is listening. It does not prove that the broker metadata path, topic APIs, or consumer group behavior are healthy.

Use it as a first gate, not the final validation.

## Better Verification

After the port is reachable, verify Kafka itself:

```bash
kafka-topics.sh --bootstrap-server localhost:9092 --list
```

Then verify the topics expected by the lab:

```bash
kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic test-input-topic-1
```

If a stream processor is part of the lab, check its logs separately:

```bash
docker logs stream_processor
```

Do not treat a successful Terraform apply as proof that messages are flowing.

## Terraform Lab Pattern

A practical local pattern is:

```text
network -> broker container -> readiness check -> topics -> app container -> message-flow test
```

The readiness check should be visible in the graph through dependencies. Topic creation should not run until the broker passes the first gate.

For labs, `null_resource` and `local-exec` can be acceptable glue. In production, prefer platform-native health checks, managed service readiness, and deployment controllers that understand lifecycle state.

## Common Failure Modes

- advertised listeners point clients at the wrong host or port.
- topics are created before the broker is ready.
- the stream processor subscribes to a topic name that differs from the created topic.
- local persisted data carries state from a previous failed run.
- single-broker defaults hide replication and availability assumptions.

The fastest debug path is to separate broker readiness, topic existence, and application processing. They are related, but they fail differently.

## Promotion Notes

Before moving a Kafka lab pattern toward production, revisit:

- listener and network design.
- topic ownership and creation process.
- retention and cleanup policy.
- consumer group behavior.
- broker persistence and recovery.
- monitoring for lag, ISR, controller health, and failed produce or consume paths.

A lab can teach sequencing. Production Kafka requires durability, capacity, security, and operational ownership.

## Acceptance Criteria

- Broker container is running.
- Kafka port readiness gate passes.
- Topic list and topic describe commands work.
- Producer and consumer configuration use the same bootstrap path.
- Stream processor logs show consumption or a clear connection failure.
- Cleanup removes local state when repeatability matters.
