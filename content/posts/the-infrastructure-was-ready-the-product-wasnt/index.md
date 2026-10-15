+++
title = 'The Infrastructure Was Ready. The Product Wasn’t.'
date = 2026-10-14T00:00:00-05:00
draft = false
description = 'When does Kubernetes help a team deliver software, and when does maintaining the platform consume the time it was meant to save?'
tags = ['kubernetes', 'platform-engineering', 'devops', 'software-delivery', 'sre']
categories = ['posts']
+++

On June 21, 2023, [Pete Cheslock wrote](https://x.com/petecheslock/status/1671536499748118532):

> Kubernetes has single handed set our industry back a decade.
>
> Companies are going to die because they spend more time “managing Kubernetes” than building a product.

That is too sweeping to accept as a diagnosis. It is also too familiar to dismiss. An engineering team can get very good at keeping a cluster running and still struggle to ship the thing the cluster was built to run.

Maybe the complaint is legitimate, but the suspect is incomplete. Kubernetes can consume an organization's attention. So can almost any infrastructure investment that arrives before the need it is supposed to meet. It is worth asking how the work got there before assigning all of the blame to the orchestrator.

## We Had Plenty To Operate Before Pods

I have worked through enough generations of infrastructure to be suspicious of any story that begins with “before Kubernetes, deployment was simple.” Apache HTTP Server, GlassFish and Tomcat, Oracle databases, enterprise middleware, RPM packaging on CentOS, certificates, and VMs all came with operating instructions. An application release could require coordinating server configuration, middleware connections, certificate expiration, package versions, and somebody who remembered which machine had been changed by hand.

Those were real dependencies, not evidence that the people maintaining them were doing it wrong. A VM could isolate a workload without making two environments identical. An RPM could make installation repeatable without proving the application was ready to receive traffic. A runbook could make a deployment predictable until it met the one host that had drifted.

Kubernetes emerged in response to real problems in running containerized applications. Its [own overview](https://kubernetes.io/docs/concepts/overview/) describes service discovery, scheduling, automated rollouts, self-healing, and declarative configuration. The Deployment controller, for example, [works toward a declared state](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) rather than requiring an operator to replace each instance by hand.

Some complexity is removed: the team need not write its own process-restart loop for every service. Some is standardized: a common API describes workloads that once had separate deployment conventions. Some is newly introduced or made visible: control-plane availability, network and storage integrations, admission policies, version compatibility, and the ownership of everything around the cluster. Putting a database behind a Service does not remove the database's backup obligation. Reconciliation is useful; it is not a substitute for deciding what a good application release means.

## The Architecture Review

Consider a team choosing the runtime for a new product. Kubernetes offers rollouts, service discovery, scaling, health checks, and a consistent deployment model. The engineers proposing it do not want to build another set of bespoke scripts only to replace them as the product grows.

The architecture review has a different job: identify which capabilities the first release needs, which future requirements are credible, and who will own the cluster through upgrades and incidents. Traffic and service count are still uncertain. Avoiding a costly migration later matters; so does maintaining a platform before the product needs all of it. A database change will still need its own release plan.

“We can build this” describes a capability. “We need this” describes a constraint the product has actually encountered, or one it is credibly about to encounter. Complexity must earn its place. A future requirement can justify an early investment, but it needs a plausible timeline and an owner, not just a diagram with room to grow.

## The Cost Is Mostly On The Calendar

The invoice for a cluster is the easy number to see. The harder number is engineering time spent designing access, maintaining upgrades, handling security changes, renewing certificates, connecting storage, responding to incidents, and teaching each new application team how to use the platform. Managed Kubernetes transfers some of the control-plane and node work to a provider, depending on the service. It does not write the application's readiness probe, decide its release policy, or make its data recoverable. Kubernetes itself [does not build source code or prescribe CI/CD](https://kubernetes.io/docs/concepts/overview/).

That time may be an investment. If one platform team turns repetitive work across many application teams into a reliable self-service path, the cost can be paid back repeatedly. [DORA's platform-engineering discussion](https://dora.dev/capabilities/platform-engineering/) treats an internal platform as a product for developers, not merely a collection of infrastructure components. Its 2024 research associates internal developer platforms with better productivity and organizational performance *and* cautions that throughput and change stability can suffer. Those findings concern platforms broadly, not Kubernetes specifically; they do not establish what caused an individual team's results.

For an early product team with one deployable service, building and operating its own cluster can put the same engineers on two roadmaps: learn what customers need, and make a general-purpose runtime production-ready. A growing organization may already be paying for a different mess—duplicated deploy scripts, inconsistent access controls, unreliable VM replacements. There, standardizing on Kubernetes can reduce a cost that exists today. At larger scale, a shared platform can spread the work of patching and maintaining a deployment contract across many consumers, provided someone is funded to maintain that contract.

Consider a small team doing this well: it standardizes deployments on Kubernetes, then spends its next release window getting persistent storage and an upgrade path ready to operate. Both jobs matter if the platform is going to carry production traffic. The same engineers are also needed to settle the product's first integration contract. No one has wasted a day; the two pieces of work are competing for the same days. This is an illustrative tradeoff, not an incident report.

These are different economics. The comparison is not “Kubernetes versus zero complexity.” It is the cost of the current constraints against the cost of owning a new operating model, including the migration. A managed application service, a container service, or a small number of VMs with an automated pipeline may be sufficient for a narrower workload. Those options still need security, monitoring, backups where appropriate, and people who answer when things break. The honest question is which set of obligations the team can meet without borrowing time from the work it exists to deliver.

[Google SRE calls repetitive, manual, automatable operational work “toil.”](https://sre.google/sre-book/eliminating-toil/) A platform is an investment when it takes that work out of the critical path for more than one team. It becomes a liability when its own recurring operational work consumes more capacity than the work it removes. An especially expensive version of that liability has a polished dashboard and no application ready to use it.

## When Kubernetes Earns Its Place

The architecture review should not become a blanket veto. Suppose several teams deploy services regularly, each with different release scripts and discovery conventions. They need to place workloads across nodes, recover from machine loss, isolate tenants, and change versions without inventing that machinery independently. A declarative workload API, shared scheduling and discovery, and repeatable rollout behavior can be worth the operating cost. Kubernetes is a serious answer to those constraints.

It is an even better answer when a platform team can provide a usable path from application repository to running service: clear ownership, sensible defaults, a way to debug failures, and a rehearsed rollback. The application teams should consume a capability, not become part-time cluster administrators. A “paved road” that requires every team to understand the storage controller, ingress internals, and upgrade choreography has not yet shifted much cognitive load. It may still be the right road, but someone should count its tolls.

The counterargument to Cheslock is substantial: removing Kubernetes does not remove distributed systems, on-call, security, or deployments. For some organizations it would restore a fragmented set of scripts and handoffs that costs more than the cluster. Equally, using Kubernetes does not imply a microservices rewrite. A single well-understood application can run there. The question is whether that deployment buys something useful compared with a simpler place to run it.

## The Dashboard Cannot Answer For The Product

How would the team know whether its choice helped?

They could count clusters, successful Terraform runs, healthy Pods, and completed pipeline executions. Those numbers answer operational questions. They do not say how long a product change sat waiting for a usable test environment, whether releases became easier to reverse, or whether the team spent more time making product decisions.

Suppose the platform team makes deployment execution faster and more reliable. That is a real improvement in operational efficiency. But a release can still wait on uncertain requirements, an approval queue, or an integration owned by another team. Organizational effectiveness asks whether the intended change reaches users; improving one step does not shorten a wait somewhere else. Nor does that make the platform work pointless. It tells the team to look at the whole path before deciding what to improve next.

[DORA's delivery measures](https://dora.dev/guides/dora-metrics-four-keys/) include change lead time, deployment frequency, failed-deployment recovery time, change fail rate, and deployment rework rate. They are useful at the application or service level, interpreted together and in context. They are not a customer-value meter: a team can deploy efficiently and still build the wrong feature. Add a look at reliability, on-call interrupts, time lost to platform requests, and whether the intended product release actually reached users. Compare the same work before and after a platform change when possible. Do not turn a measurement meant to guide improvement into a quota to game.

The earlier [piece on ignored feedback loops](/posts/devops-dirty-dozen/ignoring-feedback-loops/) on this site makes the uncomfortable point: collecting a signal is not the same as changing a decision. Here, the missing loop is from platform investment back to product delivery. If engineers report that a release still takes days of handoffs, a green cluster is not a rebuttal. It is another piece of evidence about a different part of the system.

## Six Weeks Later

In this illustrative scenario, the cluster is ready. The pipeline has passed its tests. The platform team's runbook is in good shape.

The product release is six weeks late. Some of that time went to platform integration they chose to do early. Some went to product requirements that were still unresolved. The cluster could not have answered those questions for them.

The deployment dashboard is green.

The infrastructure was ready. The product wasn't.

## Sources

- [Pete Cheslock's original post, June 21, 2023](https://x.com/petecheslock/status/1671536499748118532)
- [Kubernetes documentation: overview and historical context](https://kubernetes.io/docs/concepts/overview/) and [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [DORA: platform engineering](https://dora.dev/capabilities/platform-engineering/) and [2024 State of DevOps research](https://dora.dev/research/2024/dora-report/)
- [DORA: software delivery performance metrics](https://dora.dev/guides/dora-metrics-four-keys/)
- [Google SRE: Eliminating Toil](https://sre.google/sre-book/eliminating-toil/)
