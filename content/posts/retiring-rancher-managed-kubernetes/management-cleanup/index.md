+++
title = 'The Cluster Was Unregistered. The Agents Were Still Running.'
date = 2026-11-21T00:00:00-06:00
draft = false
description = 'Part 2 of Retiring Rancher-Managed Kubernetes: proving lifecycle ownership and direct access, then diagnosing a cleanup Job blocked by Pod Security Admission.'
tags = ['rancher', 'rke2', 'kubernetes', 'pod-security', 'troubleshooting', 'decommissioning']
categories = ['posts']
series = ['Retiring Rancher-Managed Kubernetes']
+++

Part 2 of [Retiring Rancher-Managed Kubernetes](/posts/retiring-rancher-managed-kubernetes/).

The cluster disappeared from Rancher management. Its downstream agents were still running.

That was not contradictory. The management record and the in-cluster cleanup were separate pieces of work. The cleanup needed a live downstream API, a functioning Job controller, and a pod that admission would allow to start. Removing registration had not completed those steps.

The useful question changed from “did Delete work?” to “which part of the removal workflow has actually completed?”

## Establish the Meaning of Delete First

Before unregistering the legacy UAT cluster, I inspected its Rancher management and provisioning resources. A provisioning `Cluster` object existed. An early interpretation treated that as evidence Rancher must own node provisioning.

The more specific output changed that interpretation. The inspected provisioning spec did not contain machine pools or a managed Kubernetes version. On one inspected dedicated etcd VM, `rancher-system-agent` was inactive while `rke2-server` was active. Together with installation history, those observations supported treating the environment as an independently installed RKE2 cluster registered with Rancher.

None of those fields is a universal ownership classifier. In particular, `localClusterAuthEndpoint` describes an access feature, not whether a cluster is imported. Relabeling that field `importedConfig` in a `jq` report did not change its meaning.

The distinction mattered because unregistering an independently installed cluster and deleting a Rancher-provisioned cluster can have different infrastructure consequences. The retirement plan had to match the actual lifecycle owner, not just the presence of a resource with “provisioning” in its API group.

## Preserve Access Outside the System Being Removed

The existing kubeconfig reached the downstream API through Rancher's proxy. That was a dependency on the management relationship I was about to remove.

For UAT, I established a direct RKE2 kubeconfig, selected the downstream API endpoint, and successfully listed all 19 nodes before unregistration. That proved an independent access path for the subsequent investigation.

Production exposed the same dependency in a less comfortable order. Its Rancher entry was removed first; direct access was then established and tested, returning 18 Ready nodes. It worked, but it sharpened the general rule: exercise the independent access path before removing the proxy that currently provides access.

A copied kubeconfig file is not that test. Verify the selected server URL, certificate validation, identity, and an actual downstream query. Keep the credential restricted; it is recovery access, not publication material.

## A Job Object Is Not a Running Cleanup

The downstream cluster contained a `cattle-cleanup` Job. Attempts to fetch its logs initially timed out. `describe job` showed why: the Job controller could not create a pod.

The relevant event, condensed from the recorded output, was:

```text
Reason: FailedCreate
pods ... is forbidden: violates PodSecurity "restricted:latest"
allowPrivilegeEscalation != false
unrestricted capabilities
runAsNonRoot != true
seccompProfile ... must be RuntimeDefault or Localhost
```

The cleanup template used `rancher/rancher-agent:v2.8.2`. This is a finding about the captured template and admission policy, not a claim about all Rancher releases.

Logs were unavailable because there was no admitted container to produce them. The Job's existence proved a cleanup request had been represented in Kubernetes; the event explained why execution had not started.

Production later showed the same class of denial. Reusing the diagnostic question was useful. Reusing the assumption that cleanup must already be working was not.

## No Namespace Label Did Not Mean No Policy

The namespace had no explicit `pod-security.kubernetes.io/` labels, yet the denial named `restricted:latest`. An empty namespace label set did not explain away enforcement. Cluster-level defaults or configured admission behavior still had to be considered; the event was direct evidence of the effective restriction on that request.

The historical workaround temporarily set the `default` namespace's enforcement label to `privileged`. Its scope was the entire namespace, including other pod creations during that window. It was not a cleanup-pod-only exemption, nor did it disable RBAC or every other admission mechanism.

For another installation, first inspect the exact failing template, effective admission configuration, and supported cleanup method. Any temporary policy exception needs a recorded original state and restoration. The operation's original enforcement label was absent; afterward the override was removed and its absence checked. If a namespace originally has an explicit value, removing the label would not restore that value.

## Verify the Intended Removals

After the admission change, the pod progressed through `ContainerCreating` and then execution. At one production checkpoint, the cleanup pod was running but Fleet and Rancher agents still existed. “Running” was progress, not completion.

Later checks showed the expected downstream namespaces and agent workloads absent while the direct API remained responsive. The cleanup Job also disappeared. Its disappearance alone would have been ambiguous; the target-resource checks supplied the more useful evidence.

The resulting state was specific:

| Layer | Observation |
| --- | --- |
| Rancher management | Selected cluster record removed |
| Downstream cleanup | Targeted agents and namespaces no longer listed |
| Admission exception | Temporary enforcement override removed; original absence checked |
| Operator access | Direct downstream API still usable |
| Infrastructure | RKE2 and the VMs still needed their own shutdown |

The management detach had a beginning, an execution path, and a completion check. Keeping the cluster alive through all three made the difference between unregistering it and leaving unexplained cleanup work behind.

## Sources and Reading Order

The complete export's user messages 20, 24, and 28 establish the UAT ownership/access observations; 60–83 contain admission and cleanup checks. Messages 202–226 cover the production sequence. See the [series evidence map](/posts/retiring-rancher-managed-kubernetes/#evidence-map) and [command index](/field-notes/rancher-retirement-investigation-command-index/) for investigation recipes.

[Kubernetes Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/) documents the namespace-level policy model and the distinction between workload-template checks and enforcement on the pods they create.

- **Previous:** [Shutting Down Kubernetes Is Not the Same as Decommissioning It](/field-notes/rancher-rke2-decommissioning-field-note/)
- **Next:** [Zero Replicas Is Not a Shutdown Plan](/posts/retiring-rancher-managed-kubernetes/reconciliation-and-storage/)
- [Series overview](/posts/retiring-rancher-managed-kubernetes/)
