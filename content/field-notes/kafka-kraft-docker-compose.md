+++
title = 'Kafka KRaft Mode In Docker Compose'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for running Kafka in KRaft mode (no Zookeeper) with Docker Compose for local development and testing.'
tags = ['kafka', 'docker', 'local-dev']
categories = ['field-notes']
+++

Kafka without Zookeeper runs in KRaft mode using the Raft protocol for metadata consensus. This is the default in Kafka 4.x and available since Kafka 3.x. For local labs, KRaft mode removes the complexity of managing a separate Zookeeper container.

For a runnable reference, see the [`docker/kafka/docker-compose.yml` file in the IaC repository](https://github.com/trinidadgithub/IaC/blob/main/docker/kafka/docker-compose.yml).

## Minimal KRaft Configuration

A single-broker KRaft setup needs a few key environment variables that differ from Zookeeper-based Kafka:

```yaml
services:
  kafka:
    image: confluentinc/cp-kafka:latest
    environment:
      KAFKA_KRAFT_MODE: "true"
      KAFKA_PROCESS_ROLES: "controller,broker"
      KAFKA_NODE_ID: "1"
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@localhost:9093"
      KAFKA_LISTENERS: "PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093"
      KAFKA_ADVERTISED_LISTENERS: "PLAINTEXT://localhost:9092"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: "1"
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: "0"
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
```

## Key Variables

- `KAFKA_KRAFT_MODE=true` — enables the Raft-based metadata mode.
- `KAFKA_PROCESS_ROLES=controller,broker` — a single node acts as both controller and broker. Production splits these roles across separate nodes.
- `KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093` — defines the controller ensemble. In a single-node lab, one voter is sufficient.
- `CLUSTER_ID` — a unique identifier generated once. If it changes, the broker treats the metadata as a new cluster.

## Single-Node Tuning

Lab-specific settings that should not reach production:

- `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1` — single replica is fine for testing.
- `KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS=0` — no rebalance delay speeds up consumer group testing.

## Network

A static IP on a custom bridge network avoids hostname resolution issues:

```yaml
networks:
  kafka-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.19.0.0/16

services:
  kafka:
    networks:
      kafka-net:
        ipv4_address: 172.19.0.2
```

Static IPs are fine for a lab. Production should use DNS-based service discovery.

## When To Use KRaft

KRaft mode is appropriate for:

- local development and testing.
- CI pipelines that need a real Kafka broker.
- learning Kafka without the Zookeeper overhead.

Not appropriate for:

- production clusters that need a proven controller quorum implementation. Zookeeper-based Kafka is still the production standard for most teams until KRaft has broader production adoption.

## Acceptance Criteria

- Kafka broker starts without Zookeeper dependency.
- Topics can be created and messages produced and consumed.
- Repeated restarts do not corrupt metadata.
- Consumer group rebalancing works with single-broker constraints.
- Clean shutdown leaves the data directory consistent.
