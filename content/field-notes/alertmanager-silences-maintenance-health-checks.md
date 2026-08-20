+++
title = 'Alertmanager Silences Need Independent Maintenance Health Checks'
date = 2026-08-18T00:00:00-05:00
draft = false
description = 'A field note on using Alertmanager silences during Kubernetes maintenance without losing the operational signal needed for post-maintenance validation.'
tags = ['kubernetes', 'prometheus', 'alertmanager', 'observability', 'maintenance', 'operations']
categories = ['field-notes']
+++

Alertmanager silences are useful during planned infrastructure work. They are also easy to misunderstand.

A silence should suppress notification noise. It should not become the health check.

During a Kubernetes node power-cycle window, the maintenance plan needed temporary silences for node, kubelet, etcd, and pod-scheduling alerts. That was reasonable: every node reboot would otherwise create expected alert noise. The risk was not the silence itself. The risk was treating the quiet notification path as proof that the cluster was healthy.

Prometheus and Kubernetes still had the signal. The operator still had to ask for it directly.

## What The Silence Covered

The maintenance silence was scoped to infrastructure alerts expected during node work:

```text
KubeNode*
Kubelet*
KubePod*
KubeDeployment*
KubeStatefulSet*
KubeDaemonSet*
KubeSystemPod*
KubeAPI*
KubeControllerManager*
KubeScheduler*
KubeProxy*
KubeJob*
KubePersistentVolume*
KubePdb*
etcd*
TargetDown
ClusterNode*
NodeSystemdService*
```

That scope kept routine maintenance noise out of the paging path while leaving unrelated business and watchdog alerts alone.

The important detail is that several pod-level alerts were intentionally inside the silence. A pod failing to become ready during the window might be expected churn, or it might be a real failure discovered by maintenance. Alertmanager would not make that distinction for the operator while the silence was active.

## The Failure Mode

Post-maintenance checks found pods that did not return cleanly after node work:

```text
namespace-a   app-observer-0       1/2   CrashLoopBackOff
namespace-a   app-observer-redis-0 0/1   ContainerCreating
namespace-a   dashboard-abc123     0/1   ContainerCreating
```

The failure split into two different classes:

- one stateful dependency was stuck because the expected storage device was not present on the target node after reboot.
- one dashboard pod was stuck because a referenced `Secret` and `ConfigMap` were missing, which matched a pre-existing configuration failure.

Both were visible from Kubernetes. Both could feed pod-not-ready or container-waiting alerts. During the maintenance silence, neither should be assumed to page the operator.

That is the operational trap: the paging path is quiet by design, but the cluster is not necessarily clean.

## Keep The Alert Data Plane Queryable

Before creating the silence, capture the current alert baseline from Alertmanager:

```bash
curl -s http://127.0.0.1:9093/api/v2/alerts \
  | jq -r '.[].labels.alertname' \
  | sort -u
```

If `jq` is not available, use a short Python reader:

```bash
curl -s http://127.0.0.1:9093/api/v2/alerts \
  | python3 -c 'import json,sys; print("\n".join(sorted({a["labels"].get("alertname","") for a in json.load(sys.stdin)})))'
```

Then record the silence itself:

```bash
curl -s http://127.0.0.1:9093/api/v2/silences \
  | python3 -c 'import json,sys; [print(s["id"], s["status"]["state"], s["startsAt"], s["endsAt"], s["comment"]) for s in json.load(sys.stdin)]'
```

This creates two useful facts:

- which alerts were already firing before maintenance started.
- which alert families the operator intentionally muted.

Without that baseline, post-maintenance alert review starts with guesswork.

## Health Checks Must Bypass Notification Silence

A maintenance health check should query systems of record directly. Do not rely on whether the pager is quiet.

Useful checks after each node or batch:

```bash
kubectl get nodes -o wide
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o wide
kubectl get events -A --sort-by=.lastTimestamp
kubectl get pvc -A
kubectl get pv
kubectl get volumeattachments
```

If Prometheus is reachable, query the same signals that alert rules use. For kube-state-metrics-style installations, examples include:

```promql
kube_pod_status_phase{phase=~"Pending|Unknown|Failed"}
```

```promql
kube_pod_container_status_waiting_reason{reason=~"CrashLoopBackOff|ContainerCreating|ImagePullBackOff|ErrImagePull"}
```

```promql
kube_node_status_condition{condition="Ready",status!="true"}
```

From a workstation, the CLI flow usually starts with a temporary port-forward to Prometheus:

```bash
kubectl -n monitoring port-forward svc/prometheus-operated 9090:9090
```

Then query Prometheus with `curl --data-urlencode` so PromQL characters are escaped correctly:

```bash
curl -G -s http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=kube_pod_status_phase{phase=~"Pending|Unknown|Failed"}' \
  | python3 -m json.tool
```

For container waiting reasons:

```bash
curl -G -s http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=kube_pod_container_status_waiting_reason{reason=~"CrashLoopBackOff|ContainerCreating|ImagePullBackOff|ErrImagePull"}' \
  | python3 -m json.tool
```

For a compact node readiness view:

```bash
curl -G -s http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=kube_node_status_condition{condition="Ready",status!="true"}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(r["metric"].get("node","<unknown>"), r["metric"].get("status",""), r["value"][1]) for r in d["data"]["result"]]'
```

To ask Prometheus what is firing regardless of Alertmanager notification state, query `ALERTS` directly:

```bash
curl -G -s http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=ALERTS{alertstate="firing"}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(r["metric"].get("alertname","<unknown>"), r["metric"].get("namespace",""), r["metric"].get("pod","")) for r in d["data"]["result"]]'
```

The exact metric names vary by stack. The principle does not: the maintenance script or runbook should ask Prometheus and Kubernetes directly whether the cluster is clean.

## Re-Enable Alerts Deliberately

Do not wait for a silence to expire if the work ends early. Expire or delete the maintenance silence after final checks, then verify that only the intended silence changed.

Example sequence:

```bash
curl -s http://127.0.0.1:9093/api/v2/silences \
  | python3 -c 'import json,sys; [print(s["id"], s["status"]["state"], s["comment"]) for s in json.load(sys.stdin)]'

curl -s -X DELETE http://127.0.0.1:9093/api/v2/silence/<silence-id>

curl -s http://127.0.0.1:9093/api/v2/silences \
  | python3 -c 'import json,sys; [print(s["id"], s["status"]["state"], s["comment"]) for s in json.load(sys.stdin) if s["id"] == "<silence-id>"]'
```

Some Alertmanager versions do not support updating silences with `PUT`. Deleting the silence is a valid way to end it early, as long as the operator verifies the final state.

## Evidence To Keep

For maintenance windows that use silences, keep these artifacts with the normal node evidence bundle:

- the pre-maintenance active alert list.
- the silence ID, matcher, start time, end time, creator, and comment.
- the exact health checks run while the silence was active.
- the non-running pod list before and after maintenance.
- any `describe pod` events for stuck workloads.
- storage attachment evidence for stateful pods.
- proof that the maintenance silence was expired or deleted.

This makes the review much cleaner. The team can distinguish expected reboot noise from new failures, pre-existing failures, and issues deferred to follow-up.

## Practical Takeaway

Silencing Alertmanager is not the same as silencing Prometheus, Kubernetes, or the storage layer.

Use silences to control notification noise during planned work. Keep the data plane visible. Query it directly during the maintenance window. Re-enable alerts deliberately when the work is done.

The pager being quiet is not a health check. It is only evidence that notification routing is quiet.

## References

- [Prometheus Alertmanager Silences](https://prometheus.io/docs/alerting/latest/alertmanager/#silences)
- [Kubernetes Maintenance Evidence Bundles Need A Redaction Plan](/field-notes/kubernetes-maintenance-evidence-bundles/)
- [Kubernetes ContainerCreating: Split Storage Failures From Missing Manifests](/field-notes/kubernetes-containercreating-storage-vs-manifest-triage/)
- [SLO Burn-Rate Alerting With Prometheus](/field-notes/slo-burn-rate-alerting-prometheus/)
