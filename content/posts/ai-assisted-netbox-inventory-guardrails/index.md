+++
title = 'When AI-Assisted Infrastructure Updates Need Guardrails'
date = 2026-06-12T00:00:00-05:00
draft = false
description = 'A practical reflection on using AI assistance for NetBox inventory work, where tool access helped but evidence, validation, and import discipline mattered more than confident answers.'
tags = ['netbox', 'automation', 'sre', 'infrastructure', 'ai', 'operations']
categories = ['notes']
+++

AI assistance is useful in infrastructure work when it accelerates the boring parts: parsing inventory, building CSVs, checking references, and producing repeatable commands.

It becomes dangerous when it gets confident without evidence.

In one NetBox/IPAM update, the task sounded simple: take Kubernetes node inventory, create the matching NetBox records, associate management IPs, and set each device's primary IPv4 address. The work was not conceptually hard. The risk was in the details: object relationships, import order, duplicate names, existing tags, site mappings, and whether the tool was writing to the intended NetBox instance.

The first AI-assisted path was frustrating because the agent began to infer too much. It mixed real checks with assumptions about NetBox behavior. It had access to tools, but tool access did not automatically make the work safe.

The better path started when the workflow became evidence-driven again.

## The Work To Be Done

The desired model was straightforward:

```text
Kubernetes node inventory
  -> NetBox devices
  -> management interfaces
  -> IP address assignments
  -> primary IPv4 on each device
```

For each node, the useful data was:

- hostname.
- management IP and prefix length.
- site.
- device role.
- cluster tag.
- node function such as control plane, worker, etcd, monitor, or storage.
- whether an IP was assigned to a device or reserved as a VIP.

That maps cleanly to NetBox, but not as one flat operation. Devices, interfaces, IP addresses, and primary IP fields are related objects. If those relationships are created in the wrong order, the import becomes noisy or incomplete.

## Where The Agent Went Wrong

The bot did some useful things. It identified needed fields, proposed dry-run behavior, and recognized that deletes and bulk changes needed confirmation.

But it also showed classic AI-agent failure modes:

- assuming NetBox would auto-create tags safely.
- assuming a CSV field would behave the same across NetBox versions.
- treating a tool's claimed write access as proof that the write path was correct.
- trying to generate large downloadable files through a broken tool path.
- continuing to retry malformed tool calls instead of changing strategy.
- mixing “this should work” with “this was verified.”

The uncomfortable part was not that the model was wrong once. It was that the model could be wrong confidently while still sounding operationally fluent.

That is the exact situation where an operator needs to slow the workflow down.

## The Better Pattern

The safer workflow used generated artifacts and validation instead of direct trust in the assistant.

The import was split into three CSVs:

```text
devices.csv
interfaces.csv
ip-addresses.csv
```

The order mattered:

```text
1. Devices
2. Interfaces
3. IP addresses
```

Devices need to exist before interfaces can reference them. Interfaces need to exist before IP addresses can attach to them. Reserved VIPs can exist without device/interface assignment, but that should be intentional and visible in the data.

After the import, primary IPv4 assignment was handled separately. That separated “create the object graph” from “set the device display relationship.”

That distinction matters. It makes verification easier and avoids turning one failed field into a failed bulk import.

## Validation Before Import

Before importing, the generated CSVs were checked for relationship consistency:

- every interface referenced a known device.
- every assigned IP referenced a known device and interface.
- VIP rows were intentionally unassigned and marked reserved.
- device names were unique.
- interface tuples were unique.
- IP addresses were unique.
- DNS names were unique where that mattered operationally.
- all addresses belonged to the expected prefix.
- required NetBox objects existed first: site, role, manufacturer, device type, and tags.

The duplicate-name check was especially important. A repeated node-name pattern across two environments can look harmless in a text file but become a hard NetBox conflict. The validation step surfaced that before import.

That is exactly where AI is useful: not to “just do it,” but to help build mechanical checks around human decisions.

## Primary IPs As A Separate Pass

NetBox can associate an IP address to an interface and still not have that IP set as the device's primary IPv4 address.

That is not a failure. It is a separate relationship.

The safer post-import approach was:

```text
device name, primary IPv4 address
```

Then for each row:

- query NetBox for exactly one matching device.
- query NetBox for exactly one matching IP address.
- skip the row if either lookup is ambiguous or missing.
- patch the device only after a dry run succeeds.

This is a good example of operational automation being intentionally boring. The script does not need to be clever. It needs to refuse unsafe ambiguity.

## The Most Important Guardrail

The strongest guardrail was not code. It was language.

The useful instruction to the agent was effectively:

```text
Do not speculate. Do not guess. Show what you verified. Stop when the evidence is missing.
```

That changed the shape of the work. Instead of asking the agent to own the outcome, the operator used it to produce artifacts that could be inspected:

- CSV files.
- validation summaries.
- duplicate reports.
- import instructions.
- dry-run output.
- API patch scripts.

Those artifacts are reviewable. A fluent chat answer is not enough.

## Lessons For AI-Assisted SRE Work

The practical lessons are simple:

- Tool access is not trust.
- A successful API call is not proof that the correct system was updated.
- Bulk writes need a plan and a verification path.
- Generated files are safer than huge inline responses.
- Dry runs should be explicit and boring.
- Ambiguous matches should skip, not guess.
- Starting a new session can be the right move when context gets polluted.

AI can reduce toil in inventory and IPAM work. It can parse, normalize, generate, and validate faster than a person doing it by hand.

But the operator still owns the source of truth.

The win is not “the bot updated NetBox.” The win is “the bot helped produce a repeatable, validated workflow that a human could reason about before anything changed.”

That is the difference between automation and gambling.
