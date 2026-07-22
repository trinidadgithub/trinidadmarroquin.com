+++
title = 'Downstream Observability Teardown Triage'
date = 2026-07-22T00:00:00-05:00
draft = false
description = 'A Kubernetes triage pattern for separating customer workload health from observability stack teardown, stuck finalizers, alert delivery failures, and externally managed resources.'
tags = ['kubernetes', 'observability', 'rancher', 'gitops', 'operations']
categories = ['field-notes']
+++

An observability namespace can look like a platform outage even when customer workloads are healthy.

In one downstream-cluster investigation, the noisy symptoms were all in monitoring and alerting: logging resources disappearing, an agent operator stuck during deletion, alert delivery failures, external secret authentication errors, and exporter noise. The first useful move was to split the question in two:

```text
Is the cluster currently unhealthy?
Is the observability stack being removed, broken, or reconciled by another owner?
```

Those are different incidents.

## Prove Cluster Health First

Start with the generic health view before chasing monitoring components:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o wide
kubectl get pv,pvc -A
kubectl get events -A --sort-by=.lastTimestamp
```

Then check the customer or platform namespaces that matter for service availability:

```bash
kubectl get deploy,statefulset,daemonset,pod -A -o wide
kubectl get ingress,svc -A
```

If nodes are `Ready`, critical pods are `Running`, and PVCs are bound, say that clearly. Do not let an observability failure become an assumed application outage.

## Check The Ownership Plane

Before repairing deleted observability resources, find out who owns them.

Check common local ownership surfaces:

```bash
kubectl get applications.argoproj.io -A
kubectl get helmreleases -A
kubectl get helmcharts.helm.cattle.io -A
helm list -A
kubectl get bundles.fleet.cattle.io -A
```

If Argo CD or Flux CRDs are absent locally, that does not prove there is no GitOps owner. A downstream cluster may only expose an agent locally while the upstream system owns the desired state elsewhere. In that case, local Helm state can tell you what is not managing the resource, but it may not identify the real owner.

## Read Deletion Evidence

A namespace with a few leftovers may be in teardown, not partial failure.

Useful checks:

```bash
kubectl get all,cm,secret,pvc,sa,role,rolebinding -n logging
kubectl get deploy -n telemetry -o yaml
kubectl get events -n logging --sort-by=.lastTimestamp
kubectl get events -n telemetry --sort-by=.lastTimestamp
```

Look for:

- many `Killing` events in a short window.
- deleted Deployments or DaemonSets with finalizers.
- only PVCs, TLS secrets, or root CA ConfigMaps left behind.
- an operator stuck at `0/1` while its Deployment has a deletion timestamp.
- no corresponding Helm release in the local cluster.

That pattern points toward active removal or external pruning. The right next step is usually ownership confirmation, not manual recreation.

## Separate Storage Topology From App Health

Monitoring stacks often use persistent storage. Attach errors may be real, but still scoped to observability.

Check whether the storage driver is available on the nodes where the monitoring pods are trying to run:

```bash
kubectl get nodes -L topology.kubernetes.io/zone -o wide
kubectl get pods -n storage-system -o wide
kubectl describe pod -n logging loki-example-0
kubectl describe pvc -n logging data-loki-example-0
```

The important question is whether the volume is trying to attach to a node that can actually run that CSI path. If only worker nodes advertise the needed CSI topology but monitoring pods are scheduled onto monitor-only nodes, the symptom is storage placement, not necessarily a broken cluster.

## Alert Delivery Is Its Own Failure

Alertmanager failures should be triaged separately from workload health.

Check whether alerts are firing, whether Alertmanager is healthy, and whether notification delivery is failing:

```bash
kubectl -n monitoring get pods -o wide
kubectl -n monitoring logs deploy/alertmanager --since=2h
kubectl -n monitoring get secret,configmap
```

Common findings:

- webhook returns `403` or another authorization failure.
- the alert route exists, but the receiver credential is expired or revoked.
- Alertmanager is correctly detecting issues but cannot notify the external system.

That is an alert delivery incident. Treat it that way instead of assuming all firing alerts imply customer impact.

## External Secret Errors Need Consumers

External secret controller errors can be urgent, but first check whether anything depends on the failing store:

```bash
kubectl get clustersecretstore,secretstore -A
kubectl get externalsecret -A
kubectl -n external-secrets logs deploy/external-secrets --since=2h
```

If a store cannot authenticate but no `ExternalSecret` objects consume it, that is still a configuration problem, but it may not explain current workload impact. If consumers exist and secrets are stale or missing, escalate it as an application dependency issue.

## Exporter Noise Is Not Always Platform Failure

Exporter errors can flood logs and alerts after database or application version drift.

Check the relationship between exporter version, target version, and the failing query:

```bash
kubectl -n monitoring logs deploy/postgres-exporter --since=2h
kubectl -n monitoring get cm,secret | grep exporter
```

If an exporter repeatedly emits query-shape errors, the immediate operational value is to reduce false noise and fix the exporter/query compatibility. Do not let exporter noise mask higher-priority platform symptoms.

## The Triage Pattern

Use this order:

1. Prove node, pod, PVC, and critical workload health.
2. Identify whether observability resources are locally managed or externally reconciled.
3. Read deletion timestamps, finalizers, and events before recreating anything.
4. Separate storage placement failures from application failures.
5. Treat alert delivery failures as notification-path incidents.
6. Check external secret consumers before declaring customer impact.
7. Classify exporter errors as signal quality problems unless they block workloads.

The conclusion should be explicit:

```text
customer workload impact: yes/no/unknown
observability stack health: healthy/deleting/broken/externally owned
alert delivery: healthy/failing/unknown
secret dependency impact: yes/no/unknown
next owner: platform/app/observability/security/GitOps
```

That separation keeps the response factual. Observability can be broken at the same time the cluster is serving traffic. It can also be the only system that would have told you about a real outage. Triage both facts without merging them into one vague incident.
