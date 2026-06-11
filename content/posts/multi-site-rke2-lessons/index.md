+++
title = 'Multi-Site RKE2 Operations: Lessons From The Fleet'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Operational lessons from running RKE2 clusters across multiple data centers: inventory design, node naming conventions, upgrade sequencing across sites, and the patterns that break first at scale.'
tags = ['rke2', 'kubernetes', 'rancher', 'operations', 'sre']
categories = ['notes']
+++

Running RKE2 across multiple data centers reveals problems that single-cluster operations never expose. The differences between sites — hardware generations, network latency, storage backend versions, DNS configurations, operating system versions — become the primary operational concern.

This post captures the lessons that held up across sites.

## Inventory Design Predicts Operational Pain

The inventory is the single source of truth for what runs where. If the inventory is incomplete or inconsistent, every automation step requires manual verification.

A useful inventory groups nodes by site, role, and cluster in a way that supports both ad-hoc commands and playbook targeting:

```yaml
all:
  children:
    site-a_prod_rke2:
      hosts:
        site-a-etcd-1-rke2:
        site-a-etcd-2-rke2:
        site-a-mstr-1-rke2:
        site-a-wrkr-1-rke2:
      children:
        site-a_prod_rke2_etcd:
        site-a_prod_rke2_mstr:
        site-a_prod_rke2_wrkr:
    site-b_prod_rke2:
      # same structure
```

The pattern is `<site>-<environment>_rke2` with subgroups per role. This lets you target by site (`site-a_prod_rke2`), by role across all sites (`_wrkr`), or by specific combinations (`site-a_prod_rke2:!site-a_prod_rke2_wrkr` to exclude workers).

### The Naming Convention Trap

Node hostnames should encode site, role, and sequence number. A name like `site-a-etcd-3-rke2` tells you where it is, what it does, which one in the sequence, and which distribution it belongs to.

A name like `ip-10-0-1-45` tells you nothing.

Inconsistent naming across sites is more expensive than bad naming. If one site uses `phx-1-etcd-1` and another uses `iad-1-etcd1-rke2`, automation that parses node names will have divergent logic paths for each site.

## Upgrade Sequencing

The pattern that held up:

```text
etcd members (one at a time, verify quorum after each)
→ control plane nodes (one at a time, verify API after each)
→ workers (batched by group, verify workloads after each batch)
```

### Across Sites

```text
non-production site (full upgrade)
→ production site A (canary)
→ production site B
→ remaining production sites
```

A minimum two-week gap between non-production and production upgrades allows time to observe issues. A one-week gap between production sites allows time to abort before the next site.

### Pre-Upgrade Checks

Before upgrading any node in any site:

```bash
# Node health
kubectl get nodes -o wide
kubectl describe node <node> | grep -A5 Conditions

# etcd health (from a control plane node)
etcdctl endpoint health -w table --cluster

# Workload health
kubectl get pods --all-namespaces | grep -v Running | grep -v Completed

# Storage health
kubectl get pvc --all-namespaces | grep -v Bound

# Pre-upgrade snapshot
rke2 etcd-snapshot save
```

## What Breaks At Scale

### DNS Configuration Drift

Every site in a multi-cluster fleet has a DNS configuration story. Some use netplan with static DNS, some use DHCP-injected domains, some have custom resolvers. The same Kubernetes manifest works differently depending on how the node resolver behaves.

See [DNS Search Domain Debugging](/field-notes/dns-search-domain-debugging/) for the toolkit.

### Storage Backend Version Skew

Different sites may have different vSphere versions, different storage appliance firmware, or different CSI driver versions. A storage class that works in one site may silently fail in another. Validate storage operations per site, not once globally.

### Image Registry Latency

A container image that pulls in 5 seconds in one site may take 2 minutes in another. This affects startup time, rolling update windows, and node autoscaler responsiveness. Cache images in a local registry per site or use a CDN-backed registry proxy.

### Node Image Version Spread

If each site has a slightly different node operating system version or kernel, the same workload may behave differently. The et al. pattern: standardize the node image across all sites and test updates in a non-production site first.

### Upgrade Velocity

The time to upgrade a fleet is bounded by the slowest site and the serialization constraints. Parallelizing across sites while serializing within sites is the correct model, but it requires confidence that the non-production site completed successfully.

Document the upgrade timeline expectations before starting. If the fleet takes three weeks to upgrade, the team needs to know that before the first node is drained.
