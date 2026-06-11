+++
title = 'Kafka Streams Pipeline With Terraform'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Project notes for building a local Kafka Streams data pipeline managed entirely by Terraform, including broker provisioning, topic creation, and stream processor deployment.'
tags = ['kafka', 'terraform', 'data-pipeline', 'python', 'docker']
categories = ['projects']
+++

A local Kafka Streams pipeline managed by Terraform is useful for understanding the full data path before production dependencies are involved. Terraform handles the broker, topics, stream processor image, and container lifecycle — all through the Docker provider.

For a complete working example, see the [`kafka-streams-pipeline` directory in the IaC repository](https://github.com/trinidadgithub/IaC/tree/main/kafka-streams-pipeline). The `errors.txt` file in the repository contains the exact build failure and resolution for the `librdkafka` C extension, which is the most common issue when containerizing Python Kafka applications.

## Architecture

Terraform provisions the full pipeline:

```text
Kafka broker (KRaft mode) -> topic creation -> stream processor image -> processor container
```

All resources are managed by Terraform and cleaned up with `terraform destroy`.

## Broker Provisioning

The broker uses KRaft mode (no Zookeeper) with a custom image that adds `nc` for health checks. The base image is `confluentinc/cp-kafka` with `yum install -y nc` in a Red Hat-compatible Dockerfile.

The key configuration:

```hcl
KAFKA_KRAFT_MODE       = "true"
KAFKA_PROCESS_ROLES    = "controller,broker"
KAFKA_NODE_ID          = "1"
KAFKA_CONTROLLER_QUORUM_VOTERS = "1@localhost:9093"
```

## Readiness Checks

Terraform uses a `null_resource` with `local-exec` to wait for Kafka to be ready before creating topics:

```hcl
resource "null_resource" "wait_for_kafka" {
  provisioner "local-exec" {
    command = <<-EOC
      until nc -zv localhost 9092; do
        sleep 5
      done
    EOC
    interpreter = ["/bin/bash", "-c"]
  }
}
```

This is a port-level check. It proves something is listening, not that the broker metadata is initialized. See also: [Kafka Readiness Checks In Terraform Docker Labs](/field-notes/kafka-readiness-terraform-docker-labs/).

## Topic Creation

Topics are created with kafka-topics.sh inside the broker container, triggered by another `null_resource`:

```hcl
resource "null_resource" "create_topics" {
  depends_on = [null_resource.wait_for_kafka]

  provisioner "local-exec" {
    command = <<-EOC
      docker exec kafka bash -c "
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
          --create --topic input-topic \
          --config cleanup.policy=delete \
          --config compression.type=gzip \
          --config delete.retention.ms=86400000 \
          --config min.cleanable.dirty.ratio=0.01 \
          --if-not-exists
      "
    EOC
  }
}
```

Topic configuration matters even in a lab. Setting `cleanup.policy=delete` and `compression.type=gzip` mirrors production defaults. `delete.retention.ms=86400000` keeps data for 24 hours before cleanup, which is enough for local testing.

## Stream Processor

The Python stream processor uses the `confluent_kafka` library inside a Docker container. The Dockerfile installs `librdkafka-dev` which requires the C extension build tools. If the build fails, check:

- `gcc` and `python3-dev` are installed in the build image.
- `librdkafka-dev` version matches the `confluent_kafka` Python package version.
- The base image includes `yum groupinstall "Development Tools"` for Red Hat-based images.

## Data Flow

```text
producer -> input-topic -> stream_processor -> output-topic -> consumer
```

The stream processor reads from `input-topic`, applies transformation logic, and writes to `output-topic`. The processor logs show consumption, transformation, and production latency.

## Acceptance Criteria

- Kafka broker starts in KRaft mode without Zookeeper.
- Readiness check passes before topic creation runs.
- Topics are created with the correct configuration.
- Stream processor image builds without C extension errors.
- Processor reads from input topic and writes to output topic.
- `terraform destroy` removes all containers, images, and local state.
