+++
title = 'Concourse Ingress DNS And TLS Cutover'
date = 2026-06-26T00:00:00-05:00
draft = false
description = 'Field note for moving Concourse behind Kubernetes ingress, round-robin DNS, and a signed TLS certificate without mixing up DNS, ingress, secret, and application URL ownership.'
tags = ['concourse', 'kubernetes', 'ingress', 'tls', 'dns', 'helm']
categories = ['field-notes']
+++

Concourse can be healthy inside the cluster while still failing from the operator's browser. The common gap is not the web pod. It is the handoff between DNS, ingress controller placement, certificate material, and Concourse's own external URL.

Use this checklist when moving Concourse from a temporary URL or NodePort to a real hostname such as `concourse.example.com`.

## Confirm The Ingress Target

Start by finding where ingress actually lands. Do not assume every worker should be in DNS until the ingress controller placement confirms it.

```bash
kubectl --context cluster-a-prod get daemonset -A | grep ingress

kubectl --context cluster-a-prod get pods -n kube-system \
  -l app.kubernetes.io/name=rke2-ingress-nginx -o wide

kubectl --context cluster-a-prod get ingress -n concourse
```

The important outputs are:

- the ingress class used by the Concourse ingress.
- the node names running ingress controller pods.
- the IP addresses published in ingress status.
- whether control-plane or etcd nodes are unintentionally serving ingress.

On RKE2, the default ingress controller can run as a DaemonSet on every Linux node unless restricted. That may include control-plane or etcd nodes. Decide whether that is acceptable before placing all published addresses into DNS.

## Register DNS To Ingress Nodes

For a simple internal round-robin setup, create multiple A records for the same hostname:

```text
concourse.example.com. 300 IN A 192.0.2.10
concourse.example.com. 300 IN A 192.0.2.11
concourse.example.com. 300 IN A 192.0.2.12
```

If using dynamic DNS updates, build the transaction explicitly so the intended record is replaced as one unit:

```bash
nsupdate <<EOF
server 192.0.2.53
zone example.com
update delete concourse.example.com A
update add concourse.example.com 300 A 192.0.2.10
update add concourse.example.com 300 A 192.0.2.11
update add concourse.example.com 300 A 192.0.2.12
send
EOF
```

Verify against the authoritative resolver, not only the workstation cache:

```bash
nslookup concourse.example.com 192.0.2.53
dig @192.0.2.53 concourse.example.com A +short
```

## Create The TLS Secret

Kubernetes ingress expects a TLS secret with the server certificate and private key. If the certificate was issued by an internal CA, put the server certificate first, then intermediates, then the root if your environment requires it.

```bash
cat concourse.example.com.crt intermediate-ca.crt root-ca.crt > fullchain.pem

openssl verify \
  -CAfile root-ca.crt \
  -untrusted intermediate-ca.crt \
  concourse.example.com.crt

kubectl --context cluster-a-prod -n concourse create secret tls concourse-web-tls \
  --cert=fullchain.pem \
  --key=concourse.example.com.key
```

Do not commit private keys, generated full chains, or downloaded PEM bundles unless the repository is explicitly designed to hold public certificate material. The durable configuration should reference the secret name, not contain the secret contents.

## Update Helm Values

There are two separate changes:

- ingress TLS tells Kubernetes which secret to serve for the hostname.
- Concourse `externalUrl` tells Concourse what URL to advertise and use during login flows.

Example values:

```yaml
concourse:
  web:
    externalUrl: "https://concourse.example.com"

web:
  ingress:
    enabled: true
    ingressClassName: nginx
    hosts:
      - concourse.example.com
    tls:
      - hosts:
          - concourse.example.com
        secretName: concourse-web-tls
```

Apply the values through the normal Helm path:

```bash
helm --kube-context cluster-a-prod upgrade --install concourse concourse/concourse \
  --namespace concourse \
  --values concourse-values.yaml \
  --version 20.2.4 \
  --wait \
  --timeout 10m
```

## Verify The Cutover

Check Kubernetes state first:

```bash
kubectl --context cluster-a-prod get ingress -n concourse -o yaml \
  | grep -A6 'host:\|tls:\|secretName:'

kubectl --context cluster-a-prod exec -n concourse deployment/concourse-web -- \
  env | grep CONCOURSE_EXTERNAL_URL
```

Then test each ingress node directly with `curl --resolve`. This separates DNS round-robin from backend health:

```bash
for ip in 192.0.2.10 192.0.2.11 192.0.2.12; do
  curl -sS -o /dev/null \
    --resolve concourse.example.com:443:${ip} \
    -w "${ip} http=%{http_code} connect=%{time_connect} tls=%{time_appconnect} total=%{time_total}\n" \
    https://concourse.example.com
done
```

Finally, check the Concourse API through the public hostname:

```bash
curl -sS https://concourse.example.com/api/v1/info
```

Expected signals:

- HTTPS returns `200` for the web UI.
- `/api/v1/info` returns Concourse version metadata.
- `CONCOURSE_EXTERNAL_URL` is `https://concourse.example.com`.
- each DNS target completes TCP connect and TLS handshake.

## Failure Patterns

- **DNS resolves but browser gets a timeout.** DNS may point to nodes that are not running ingress or cannot receive traffic on 443.
- **TLS works on one IP but not another.** Ingress controller placement or host firewall state differs by node.
- **Login redirects to HTTP.** Ingress TLS was added, but Concourse `externalUrl` still uses `http://`.
- **Certificate warning remains.** The secret may contain only the leaf certificate instead of the full chain, or the wrong secret name is referenced by ingress.
- **Helm notes still show HTTP.** Do not trust chart notes alone. Verify the rendered ingress and the running `CONCOURSE_EXTERNAL_URL` environment variable.

The clean cutover is four independent confirmations: DNS points to ingress nodes, ingress references the TLS secret, Concourse advertises the HTTPS URL, and every published IP completes an HTTPS request.
