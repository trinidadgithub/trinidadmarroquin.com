+++
title = 'Network Saturation Evidence Checklist'
date = 2026-06-11T00:00:00-05:00
draft = false
description = 'Field note for separating real node saturation, healthy-but-noisy control-plane traffic, and external backup or replication traffic during Kubernetes network incidents.'
tags = ['networking', 'linux', 'kubernetes', 'observability', 'troubleshooting']
categories = ['field-notes']
+++

When a flow collector reports a huge byte count, resist the urge to start with the loudest application log. Start by proving whether the node, interface, and time window support the story.

This checklist is useful when Kubernetes or Rancher appears to be involved in a network spike.

## Identify The Conversation

Ask for the flow detail, not only the top-talker summary:

```text
source IP
destination IP
source port
destination port
protocol
bytes
sessions
start time
end time
```

Important ports in Rancher/RKE2 environments include:

```text
443    Rancher, ingress, Kubernetes services
6443   Kubernetes API
9345   RKE2 supervisor
10250  kubelet
2379   etcd client
2380   etcd peer
5473   Calico Typha
9090   Prometheus
3100   Loki
```

Without ports and timestamps, top talkers are only clues.

## Map IPs To Ownership

For Kubernetes nodes:

```bash
kubectl get nodes -o wide | grep <ip>
kubectl get pods -A -o wide | grep <ip>
```

For DNS-owned endpoints:

```bash
getent hosts <ip-or-name>
nslookup <name>
dig -x <ip>
```

Classify each endpoint:

- control-plane node.
- etcd node.
- worker node.
- Rancher load balancer.
- ingress node.
- backup host.
- monitoring system.
- NAT or proxy.

## Check Live Interface Health

Find the interface used for the path:

```bash
IFACE=$(ip route get <destination-ip> | awk '{print $5; exit}')
echo "$IFACE"
```

Check counters:

```bash
ip -s link show "$IFACE"
sudo ethtool "$IFACE"
sudo ethtool -S "$IFACE" | egrep -i 'drop|err|timeout|reset|miss|coll|crc|fifo|buf|fail'
```

Look for:

- RX or TX errors.
- drops.
- CRC errors.
- carrier changes.
- TX timeouts.
- ring or buffer failures.

No interface errors does not prove the network was never congested. It only rules out one class of local NIC problem.

## Measure Current Throughput

If `sysstat` is available:

```bash
sar -n DEV 1 10
sar -n TCP,ETCP 1 10
```

Look for:

- high `%ifutil`.
- high `retrans/s`.
- high `estres/s`.
- high `orsts/s`.
- high `isegerr/s`.

For cumulative TCP counters:

```bash
nstat -az | egrep -i 'Retrans|Timeout|Listen|Reset|TCPAbort|TCPLoss'
```

Cumulative counters need context. A large number since boot does not prove a current storm.

## Inspect Current Sockets

Count established peers:

```bash
sudo ss -tan state established | \
  awk 'NR>1 {print $5}' | \
  sed 's/::ffff://g' | \
  cut -d: -f1 | \
  sort | uniq -c | sort -nr | head -30
```

Focus on a suspected endpoint:

```bash
sudo ss -tanp | grep <ip>
sudo ss -tan state time-wait | grep <ip> | wc -l
```

A current socket snapshot is not historical proof. Use it to form the next question, not to close the case.

## Check Kernel Logs

```bash
journalctl -k --since '24 hours ago' | \
  egrep -i 'eth|ens|link|nic|tx|rx|drop|timeout|reset|watchdog|NETDEV|soft lockup'
```

This helps rule out link flaps, driver issues, and kernel-visible network failures.

## Validate Etcd Before Blaming Etcd

If an etcd node appears noisy, check the actual event window:

```bash
sudo journalctl -u rke2-server \
  --since '<event-start-local>' \
  --until '<event-end-local>' | \
  egrep -i 'error|warn|timeout|reset|disconnect|etcd|snapshot|defrag|compact|leader|slow|trace'
```

Check snapshots:

```bash
sudo ls -ltrh /var/lib/rancher/rke2/server/db/snapshots
```

A small local snapshot is not enough to explain hundreds of gigabytes of traffic.

## Check Scheduled Work

If the spike happened at a predictable time, check scheduled work early:

```bash
kubectl get cronjobs -A
kubectl get jobs -A | egrep -i 'backup|snapshot|sync|replication|export'
```

On backup hosts:

```bash
journalctl --since '<event-start-local>' --until '<event-end-local>'
```

Network saturation from backup or replication jobs can make Rancher, Kubernetes API watches, Prometheus, and GitOps controllers look guilty because they are latency-sensitive.

## Operating Rule

Separate three questions:

- What emitted the symptom?
- What generated the bytes?
- What changed during the exact time window?

Those are often three different systems.
