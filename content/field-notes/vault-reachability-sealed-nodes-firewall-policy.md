+++
title = 'Vault Reachability Was Two Incidents, Not One'
date = 2026-09-30T00:00:00-05:00
draft = false
description = 'Field note for separating HashiCorp Vault sealed-node recovery from firewall policy failures when clients report that Vault is unreachable.'
tags = ['vault', 'hashicorp', 'networking', 'firewall', 'operations', 'troubleshooting']
categories = ['field-notes']
+++

"Vault is unreachable" was true, but it was not specific enough.

The useful part of this incident was separating two failure domains that overlapped in time: Vault nodes that needed unseal after an infrastructure event, and client traffic that was still being reset after Vault was healthy internally.

## Incident Shape

The incident context had two independent changes close together:

```text
1. A rack power event affected the ESXi hosts running Vault VMs.
2. Firewall policy was tightened by removing a broad allow rule.
```

After the VMs came back, Vault behaved like Vault should after restart when it uses Shamir sealing: nodes needed to be unsealed before they were usable.

The client symptom did not end there. Even after the cluster was unsealed, access from the VPN/client network to the Vault API was still failing on `tcp/8200`.

## Start At The Local Vault State

The first useful split was local health versus remote reachability.

From a Vault node, local health showed a sealed node:

```bash
curl -sk https://127.0.0.1:8200/v1/sys/health
```

```json
{"initialized":true,"sealed":true,"standby":true,"performance_standby":false,"replication_performance_mode":"unknown","replication_dr_mode":"unknown","version":"1.15.6"}
```

That is not a network problem. The service was listening, but the Vault core was sealed.

The immediate action was the normal unseal path on each sealed node:

```bash
export VAULT_ADDR=https://127.0.0.1:8200
vault operator unseal -tls-skip-verify
```

After unseal, `vault status` showed the node back in HA service:

```text
Seal Type           shamir
Initialized         true
Sealed              false
Storage Type        raft
Cluster Name        vault-cluster-example
HA Enabled          true
HA Mode             standby
Active Node Address https://vault.internal.example.com
```

The important boundary: unsealing a node fixes the Vault core state. It does not prove clients can reach the API through every network path.

## Verify The Cluster Internally

Once the nodes were unsealed, the cluster needed an internal health check before blaming the network.

```bash
vault operator raft list-peers -tls-skip-verify
vault status -tls-skip-verify
```

The cluster had three voting peers:

```text
Node     Address           State     Voter
vault-1  10.0.150.230:8201 leader    true
vault-2  10.0.150.231:8201 follower  true
vault-3  10.0.150.232:8201 follower  true
```

The local seal and HA state was clean:

```text
vault-1 / 10.0.150.230  leader    unsealed
vault-2 / 10.0.150.231  follower  unsealed
vault-3 / 10.0.150.232  follower  unsealed
```

At that point, "Vault is down" was no longer the best description. Vault was healthy internally. The remaining issue was the client path to the API.

## DNS Was Not A Load Balancer

The service name resolved directly to the Vault nodes:

```bash
getent hosts vault.internal.example.com
```

```text
10.0.150.230 vault.internal.example.com
10.0.150.232 vault.internal.example.com
10.0.150.231 vault.internal.example.com
```

That matters because a failure through the name could land on any node. Testing only the DNS name would leave ambiguity. The investigation tested the name and every node IP directly:

```bash
for endpoint in \
  https://vault.internal.example.com:8200 \
  https://10.0.150.230:8200 \
  https://10.0.150.231:8200 \
  https://10.0.150.232:8200
do
  tmp="/tmp/vault-health-$RANDOM.json"
  printf '\n%s\n' "$endpoint"
  curl -sk --connect-timeout 8 --max-time 15 \
    -o "$tmp" \
    -w 'http_code=%{http_code} remote_ip=%{remote_ip} time_total=%{time_total} err=%{errormsg}\n' \
    "$endpoint/v1/sys/health"
  if [ -s "$tmp" ]; then jq -c . "$tmp" 2>/dev/null || true; fi
  rm -f "$tmp"
done
```

Before the network policy was fixed, every direct API path from the workstation failed the same way:

```text
https://vault.internal.example.com:8200
http_code=000 remote_ip=10.0.150.230 err=Recv failure: Connection reset by peer

https://10.0.150.230:8200
http_code=000 remote_ip=10.0.150.230 err=Recv failure: Connection reset by peer

https://10.0.150.231:8200
http_code=000 remote_ip=10.0.150.231 err=Recv failure: Connection reset by peer

https://10.0.150.232:8200
http_code=000 remote_ip=10.0.150.232 err=Recv failure: Connection reset by peer
```

Plain HTTP on the same port reset too, so this was not just an HTTP-versus-HTTPS mismatch.

## Packet Flow Beat Guessing

The firewall symptom became clearer when the TCP and TLS path were described separately:

```text
TCP handshake completed from the VPN client to 10.0.150.230:8200.
The client sent a TLS ClientHello.
The server-side capture did not receive the TLS ClientHello.
The connection was reset in transit.
```

That evidence points between the client and the Vault node. It is different from:

```text
Vault is sealed
Vault listener is down
Vault is serving plain HTTP
DNS points to the wrong node
Raft has no leader
```

Those were separate hypotheses, and the local checks had already reduced them.

## Post-Change Validation

After the firewall policy was updated to allow VPN/client access to the Vault nodes on `tcp/8200`, the same health check returned valid Vault responses:

```text
vault.internal.example.com:8200 -> HTTP 429 healthy standby
10.0.150.230:8200              -> HTTP 200 active leader
10.0.150.231:8200              -> HTTP 429 healthy standby
10.0.150.232:8200              -> HTTP 429 healthy standby
```

For Vault `/v1/sys/health`, that status mix is expected in HA:

```text
200  active leader, initialized, unsealed
429  standby, initialized, unsealed
503  sealed or otherwise unavailable for service
```

The final state was not just "curl works." It was stronger:

```text
all three nodes reachable on tcp/8200
all three nodes initialized and unsealed
one active leader
two healthy standbys
all nodes in the same Raft cluster
```

## What The Evidence Supported

Observed evidence:

```text
Vault nodes were initialized but some were sealed after VM recovery.
Unseal restored local Vault health on the nodes.
Raft showed one leader and two voting followers.
DNS returned all three Vault nodes directly.
Remote client access to each node on tcp/8200 still reset after unseal.
TCP completed but TLS did not arrive at the server-side capture.
Firewall policy had recently removed the broad allow rule.
Allowing VPN/client access to the Vault nodes on tcp/8200 restored API health checks.
```

Interpretation during the investigation:

```text
The incident had a Vault state problem first and a network policy problem second.
After unseal, continued client failures were not explained by Vault sealing.
The reset belonged to the path between the VPN/client subnet and the Vault API listeners.
```

Conclusion supported by the evidence:

```text
Do not collapse sealed Vault nodes and blocked client reachability into one outage cause.
Fix and verify the Vault core state locally, then test every client path explicitly.
```

## Operating Rule

When Vault is reported unreachable after infrastructure recovery, split the checks in this order:

```text
1. Is the Vault process listening locally?
2. Is the node initialized and unsealed?
3. Does Raft have a leader and voting peers?
4. Does the service name resolve to nodes, a VIP, or both?
5. Can the client reach every node on tcp/8200?
6. Does a server-side capture see the client's TLS ClientHello?
7. Did firewall policy change between the last known-good state and now?
```

That order prevents a correct unseal operation from being mistaken for full incident resolution.
