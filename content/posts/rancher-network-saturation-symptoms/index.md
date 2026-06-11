+++
title = 'When Network Saturation Looks Like Rancher Trouble'
date = 2026-06-11T00:00:00-05:00
draft = false
description = 'An incident-style walkthrough of a Rancher traffic anomaly where control-plane symptoms pointed at remotedialer instability, but the likely trigger was backup-window network saturation.'
tags = ['rancher', 'kubernetes', 'networking', 'rke2', 'troubleshooting', 'sre']
categories = ['notes']
+++

A large network graph is good at creating anxiety. It is not always good at explaining cause.

In one investigation, a Rancher API load balancer appeared to receive hundreds of gigabytes of traffic in a 24-hour window. One RKE2 control-plane node appeared as a major sender. The first instinct was reasonable: something in Rancher, Kubernetes, monitoring, or the cluster agents might be misbehaving.

That was the right place to start. It was not the right place to stop.

By the end of the investigation, the stronger explanation was not that Rancher generated the original event. The better explanation was that a backup workload started during the same late-night window, saturated the network path, and made Rancher control-plane traffic look broken. Rancher was not the root cause. Rancher was the canary.

## The Initial Signal

The flow summary had two uncomfortable facts:

- a Rancher API load balancer VIP was the largest destination by bytes.
- an RKE2 control-plane node appeared to send a large amount of traffic.
- the session count was high enough to suggest control-plane chatter, not a simple one-time file copy.
- the destination was an internal Rancher endpoint, not an unknown public host.

The Rancher endpoint mattered. Large byte counts to a Rancher API load balancer can come from several normal-but-expensive sources:

- downstream cluster agents.
- Fleet agents.
- Kubernetes API watches.
- Argo CD or GitOps controllers.
- Prometheus scraping.
- ingress and remotedialer websocket traffic.
- reconnect churn after a degraded network path.

That does not make the traffic harmless. It only means the investigation should begin with protocol, port, timestamp, and component ownership before assuming exfiltration or malware.

## First Hypothesis: Rancher Management Traffic

The Rancher VIP resolved to the internal API load balancer. That made the first working theory straightforward:

```text
downstream RKE2 cluster
  -> cattle-cluster-agent
  -> Rancher API load balancer
  -> Rancher server / ingress
```

The control-plane node was not a random worker. It hosted core RKE2 components and one of the Rancher cluster-agent replicas. That made the node a plausible source for control-plane sessions.

The first check was pod placement:

```bash
kubectl get pods -A -o wide | grep <node-ip>
kubectl get pods -A -o wide | egrep 'cattle|fleet|rancher|system-agent'
```

The interesting pods were the `cattle-cluster-agent` replicas. They are expected to maintain long-lived connections back to Rancher. If those connections fail repeatedly, the bytes and sessions can grow quickly without any application workload moving data.

## The Logs Looked Like Rancher Was Broken

Cluster-agent logs showed the kind of messages that get an operator's attention:

```text
Failed to dial steve aggregation server
Remotedialer proxy error
websocket: close 1006 (abnormal closure)
context deadline exceeded
i/o timeout
```

The Rancher server side later showed matching symptoms:

```text
tunnel disconnect
ReverseProxy read error during body copy
unable to decode event from watch stream
Failed to watch Namespace
Failed to watch Secret
TLS handshake timeout
```

Those messages are useful evidence, but they are not a root cause by themselves. They tell us the Rancher remotedialer and watch streams were disrupted. They do not tell us why.

At this point there were several reasonable suspects:

- load balancer websocket timeout.
- HAProxy reload or backend health flap.
- firewall idle timeout.
- Rancher pod resource pressure.
- ingress-nginx timeout or reload behavior.
- packet loss or congestion between subnets.
- backup or replication traffic sharing the same path.

## Proving What Was Not Happening

The important move was to check the node and network before blaming Rancher.

On the suspected RKE2 node, live interface counters were quiet:

```bash
IFACE=$(ip route get <rancher-vip> | awk '{print $5; exit}')
ip -s link show "$IFACE"
sar -n DEV 1 10
sar -n TCP,ETCP 1 10
nstat -az | egrep -i 'Retrans|Timeout|Listen|Reset|TCPAbort|TCPLoss'
journalctl -k --since "24 hours ago" | egrep -i 'link|nic|tx|rx|drop|timeout|reset|watchdog|NETDEV'
```

That ruled out several tempting explanations:

- no live NIC saturation on the node.
- no interface error pattern.
- no obvious packet-drop storm.
- no current TCP retransmission storm.
- no kernel log evidence of link instability.

The node was not melting down.

## The Etcd Detour

A current socket snapshot showed many connections to another RKE2 node. That node turned out to be an etcd member. That was worth checking because etcd events can produce control-plane noise:

- snapshots.
- compaction.
- defragmentation.
- leader election.
- raft catch-up after a member falls behind.

The time-windowed logs did show an etcd snapshot around midnight, but it was small and local:

```text
snapshot taken from localhost
snapshot size roughly tens of MB
snapshot completed quickly
```

That ruled out the etcd snapshot as an explanation for hundreds of gigabytes of traffic.

This was an important false lead to eliminate. Without checking size, endpoint, and timing, it would have been easy to say "etcd snapshot at midnight" and stop too early.

## The Timeline Broke The Rancher Theory

The strongest correction came from timestamps.

Some Rancher disconnects happened during the live investigation, around mid-morning local time. The large traffic event was reported around the late-night backup window.

That mismatch changed the story:

```text
Rancher remotedialer symptoms existed.
The symptoms were real.
But the captured symptoms did not line up cleanly with the original traffic spike.
```

This is where incident work often goes wrong. A system can have a real problem that is not the cause of the event being investigated. The logs can be true and still be the wrong explanation.

## The Better Root Cause Candidate

After talking with another engineer, the timeline lined up with a scheduled backup job. That explanation fit better than Rancher as the primary generator:

```text
backup job starts late at night
  -> network path becomes congested
  -> Rancher websocket and watch traffic experiences delay or drops
  -> cluster agents log timeouts and websocket closures
  -> Rancher LB and ingress show elevated sessions and churn
  -> flow collector highlights Rancher endpoints as noisy
```

In that model, Rancher was not the thing saturating the network. Rancher was the sensitive control-plane workload that complained when the network was saturated by something else.

That fits distributed systems well. Control-plane traffic often breaks noisily before the network looks fully down.

## Why This Investigation Was Still Valuable

The exercise built a useful mental model for future incidents.

When Rancher-managed RKE2 clusters experience network contention, the symptoms may appear as:

- `Remotedialer proxy error`.
- `websocket close 1006`.
- `Failed to dial steve aggregation server`.
- `context deadline exceeded`.
- `tunnel disconnect`.
- watch stream decode failures.
- intermittent API or ingress errors.
- large Rancher LB byte counts with many sessions.

Those symptoms should trigger a wider checklist:

- Is a backup, replication, or migration running?
- Did the traffic start at a scheduled batch window?
- Are Rancher errors aligned with the spike or just nearby?
- Are HAProxy/ingress disconnects cause or symptom?
- Are etcd events large enough to matter?
- Are interface counters showing live saturation, or only historical noise?
- Does the flow collector show ports and conversations, or only top talkers?

## The Operating Lesson

The thing screaming is not always the thing broken.

Rancher was visible because it sits on the management path. Cluster agents, remotedialer sessions, API watches, ingress, and controllers all make the management plane sensitive to latency and packet loss.

The investigation worked because each hypothesis had to survive evidence:

- Rancher agent churn was plausible.
- HAProxy and ingress were plausible.
- etcd was plausible.
- node saturation was plausible.
- backup-window congestion fit the timeline better than all of them.

That is the practical value of the incident: not a perfect first guess, but a disciplined narrowing process.

Next time a Rancher API load balancer appears as a top talker, I would still check Rancher. I would also check the backup schedule before assuming Rancher caused the spike.
