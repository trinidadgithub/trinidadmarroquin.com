+++
title = 'RKE2 etcd Startup Failures From Expired Peer Certificates'
date = 2026-08-28T00:00:00-05:00
draft = false
description = 'Field note for diagnosing RKE2 servers stuck during startup when etcd peer TLS certificates expire and prevent quorum, without jumping to destructive etcd recovery.'
tags = ['kubernetes', 'rke2', 'etcd', 'certificates', 'operations', 'incident-response']
categories = ['field-notes']
+++

An RKE2 server stuck in `activating` can look like an API server problem. In one useful failure pattern, the API server is only downstream noise. The real issue is etcd peer TLS.

The important clue is the startup sequence:

```text
RKE2 starts
containerd starts
kubelet starts static pods
etcd starts or attempts to start
RKE2 cannot read local etcd status
API server readiness fails
```

Do not begin with `cluster-reset`, snapshot restore, or deleting `/var/lib/rancher/rke2/server/db`. First prove what etcd is doing.

## First Read The Startup Path

Start with the service status and untruncated journal output:

```bash
sudo systemctl status rke2-server --no-pager
sudo journalctl -u rke2-server \
  --since "2026-08-24 12:53:45" \
  --no-pager -o cat
```

Repeated messages like these point toward etcd being unavailable to RKE2:

```text
Failed to check local etcd status for learner management
Failed to get apiserver address from etcd: context deadline exceeded
Waiting for control-plane node to register apiserver addresses in etcd
Polling for API server readiness: GET /readyz failed
```

The `/readyz` failure matters, but it may not be the first fault.

## Check Static Pod State

RKE2 control-plane components run as static pods through containerd. Check them directly:

```bash
sudo /var/lib/rancher/rke2/bin/crictl \
  --runtime-endpoint unix:///run/k3s/containerd/containerd.sock \
  ps -a
```

Look for:

- `etcd`.
- `kube-apiserver`.
- `kube-controller-manager`.
- `kube-scheduler`.

If the etcd container exists, inspect its logs before restarting anything:

```bash
sudo /var/lib/rancher/rke2/bin/crictl \
  --runtime-endpoint unix:///run/k3s/containerd/containerd.sock \
  logs <ETCD_CONTAINER_ID> 2>&1
```

Also check listeners:

```bash
sudo ss -lntp | egrep ':(2379|2380|6443|9345)\b'
```

Normally:

- `2379` is etcd client traffic.
- `2380` is etcd peer traffic.
- `6443` is kube-apiserver.
- `9345` is the RKE2 supervisor.

`connection refused` on `127.0.0.1:2379` can be normal while etcd is still starting. A later TLS or authentication timeout is a different class of problem.

## Find The Peer Certificate Error

The decisive etcd log line looks like this:

```text
tls: failed to verify certificate: x509: certificate has expired or is not yet valid
```

In the incident pattern, one member had refreshed local certificates after restart, while another peer was still presenting an expired etcd peer certificate. The healthy-looking member rejected peer traffic, Raft elections churned, quorum never formed, and RKE2 could not complete startup.

The chain is:

```text
peer presents expired etcd certificate
-> local etcd rejects TLS connection
-> members cannot establish Raft communication
-> leader election fails or churns
-> RKE2 cannot read datastore state
-> kube-apiserver cannot become ready
```

## Check Certificates On Every Server

On each RKE2 server or etcd member, run:

```bash
hostname
uptime
sudo rke2 certificate check --output table
```

If `--output table` is not supported by that RKE2 version, use:

```bash
sudo rke2 certificate check
```

Pay attention to expired leaf certificates such as:

- `peer-server-client.crt` for `etcd-peer`.
- `server-client.crt` for `etcd-server`.
- `client.crt` for `etcd-client`.
- kube-apiserver, scheduler, controller, supervisor, and admin client certificates.

Expired leaf certificates are different from expired CAs. If the CA certificates are still valid, do not jump to CA rotation.

## Recovery Sequence

If the CAs are valid and the issue is expired leaf certificates, prefer the normal RKE2 renewal path: controlled restart of the affected server.

Recover one etcd member at a time:

```text
1. Leave any member with newly renewed certificates running.
2. Restart one expired RKE2 server only.
3. Confirm certificates renewed to OK.
4. Watch etcd peer TLS errors stop.
5. Confirm quorum and leader election.
6. Confirm kube-apiserver readiness.
7. Move to the next affected member only if needed.
```

On the affected member:

```bash
sudo rke2 certificate check --output table | egrep 'EXPIRED|peer-server-client|server-client|client.crt'
sudo systemctl restart rke2-server
sudo journalctl -fu rke2-server
```

Then re-check:

```bash
sudo rke2 certificate check --output table | egrep 'EXPIRED|peer-server-client|server-client|client.crt'
```

The expected result is renewed leaf certificates and `OK` status.

## What Not To Do First

Avoid these until evidence proves they are required:

- `rke2 server --cluster-reset`.
- snapshot restore.
- deleting `/var/lib/rancher/rke2/server/db`.
- removing etcd members.
- manually copying certificates.
- manually generating certificates.
- `rke2 certificate rotate-ca` when CAs are still valid.

Those actions solve different problems and can make a recoverable certificate incident into a data or quorum incident.

## Prevention

Add certificate review to normal cluster maintenance:

```bash
sudo rke2 certificate check --output table
```

Track:

- leaf certificates nearing expiration.
- last restart or maintenance date for each control-plane node.
- whether planned restarts are happening before certificate boundaries.
- alerts or tickets before expiration, not after restart failure.

The operating rule: when RKE2 startup blocks on etcd, prove whether etcd has a local database, peer network, disk, clock, or certificate problem before using destructive recovery tools.
