+++
title = 'IoT Device Container With Terraform And Certificate Mounts'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for running an AWS IoT device in a Docker container managed by Terraform, focusing on X.509 certificate injection via volume mounts.'
tags = ['iot', 'docker', 'terraform', 'security']
categories = ['field-notes']
+++

IoT device containers need TLS certificates to authenticate with AWS IoT Core. The certificate path is the critical configuration — if the container cannot find its credentials, it does not connect.

For a runnable lab, see the [`terraform-docker-iot` directory in the IaC repository](https://github.com/trinidadgithub/IaC/tree/main/terraform-docker-iot).

## Certificate Injection Pattern

Mount certificates from the host using Terraform volume mounts. Do not bake certs into the image:

```hcl
resource "docker_container" "iot_device" {
  image = docker_image.iot_device_image.name
  volumes {
    host_path      = abspath("${path.module}/certs/root-CA.crt")
    container_path = "/certs/root-CA.crt"
  }
  volumes {
    host_path      = abspath("${path.module}/certs/iot-thing.cert.pem")
    container_path = "/certs/iot-thing.cert.pem"
  }
  volumes {
    host_path      = abspath("${path.module}/certs/iot-thing.private.key")
    container_path = "/certs/iot-thing.private.key"
  }
}
```

`abspath(path.module)` resolves the relative cert path to an absolute path relative to the Terraform module directory. This avoids path ambiguity when Terraform runs from different working directories.

## Why Volume Mounts Instead Of Baking Certs

Baking certificates into the image means:

- every environment needs a separate image.
- cert rotation requires a full image rebuild and redeploy.
- anyone with image pull access has the certs.

Volume mounts keep certs outside the image lifecycle. The same image runs in dev, staging, and production with different mounted certificates.

## MQTT Over TLS

AWS IoT Core uses port 8883 for MQTT over TLS:

```hcl
ports {
  internal = 8883
  external = 8883
}
```

The device connects using `mqtts://` protocol with the mounted CA and device certificates. If the connection fails, check the certificate file paths inside the container first.

## Container Resilience

IoT devices should restart automatically when the connection drops:

```hcl
restart = "always"
```

The application inside the container should implement exponential backoff for reconnection. Docker's restart policy handles the container, but the application still needs to handle transient MQTT disconnections gracefully.

## Common Failure Modes

- certificate file paths inside the container do not match the application configuration.
- the CA certificate is missing or expired.
- the device certificate is not registered and activated in AWS IoT Core.
- the MQTT client uses the wrong port (8883 vs 8884 for HTTPS).
- private key permissions inside the container prevent the application from reading the file.
- `abspath` resolves to a different directory than expected when Terraform runs from a pipeline.

## Acceptance Criteria

- Container starts without certificate-related errors.
- MQTT connection to AWS IoT Core succeeds.
- Certificate rotation requires only a file replacement and container restart.
- Same image runs across environments with different mounted certs.
- Application logs show successful connection and message flow.
