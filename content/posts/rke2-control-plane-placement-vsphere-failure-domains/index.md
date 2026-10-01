+++
title = 'RKE2 Control Plane Placement Across Three ESXi Hosts'
date = 2026-09-30T00:00:00-05:00
draft = false
description = 'A platform engineering design article for placing dedicated RKE2 control-plane and etcd nodes across three ESXi hosts, with failure-domain analysis, vSphere HA tradeoffs, storage assumptions, capacity checks, and validation commands.'
tags = ['rke2', 'kubernetes', 'vsphere', 'vmware', 'etcd', 'terraform', 'architecture', 'high-availability']
categories = ['posts']
+++

The placement pattern is easy to draw:

```text
                 ESXi-1       ESXi-2       ESXi-3
                 ------       ------       ------
Control plane    master-1     master-2     master-3
etcd             etcd-1       etcd-2       etcd-3
```

The engineering question is harder:

```text
If I distribute three masters and three etcd members across three ESXi hosts,
what failures can the Kubernetes control plane actually survive?
```

This article treats `master-1`, `master-2`, and `master-3` as example VM names. Functionally, these are RKE2 server nodes running the Kubernetes API server, controller manager, scheduler, and related control-plane components with embedded etcd disabled. The `etcd-1`, `etcd-2`, and `etcd-3` VMs are RKE2 server nodes running the etcd role with the control-plane components disabled. Current RKE2 documentation describes both dedicated `etcd` nodes and dedicated `control-plane` nodes through server role configuration.

This is not the default RKE2 HA shape. The default HA documentation commonly describes an odd number of server nodes that run etcd, the Kubernetes API, and other control-plane services together. Splitting the roles adds design clarity and operational isolation, but it also adds dependencies to reason about.

The recurring question should be:

```text
What exactly have we made independent?
```

Distributing six VMs across three ESXi hosts proves compute placement. It does not, by itself, prove three complete failure domains.

## Target Topology

The intended placement is one member of each three-node role per ESXi host:

```text
                 ESXi-1       ESXi-2       ESXi-3
                 ------       ------       ------
Control plane    master-1     master-2     master-3
etcd             etcd-1       etcd-2       etcd-3
```

If `ESXi-1` fails, the design loses:

```text
master-1
etcd-1
```

It should still have:

```text
master-2     master-3
etcd-2       etcd-3
```

That is the value of the pattern. A single ESXi compute-host failure removes only one member of each three-node role. It does not remove two etcd members from the same quorum. It does not remove every API server. It gives the cluster a chance to keep serving if the remaining dependencies are healthy.

The etcd side is the strictest constraint. A three-member etcd cluster requires a majority to make progress:

```text
members: 3
quorum:  2
```

Losing one etcd member is survivable if the remaining two members can still communicate and if their storage remains available and consistent. Losing two members loses quorum. Kubernetes API servers can be running, but without an available datastore quorum the control plane cannot function normally.

The topology therefore accomplishes a narrow but important goal:

```text
one ESXi host failure -> one etcd member lost, not two
one ESXi host failure -> one control-plane VM lost, not two
```

Now test the design with the question: what exactly have we made independent?

So far, only initial compute placement is independent. The VMs are separated across ESXi hosts. Nothing in that diagram proves independent datastores, independent storage arrays, independent switches, independent power, independent API endpoint paths, or failure-state capacity.

## Placement Is Not A Failure Domain

A VM placement pattern is not the same thing as a failure domain.

Three VMs are not three failure domains merely because they have three names. Three ESXi hosts are not automatically three complete failure domains if they share the same storage array, the same storage fabric, the same top-of-rack switch, the same power dependency, or the same overloaded capacity pool.

At minimum, review these layers:

```text
VM name
VM host placement
ESXi compute host
physical server
vSphere cluster
resource pool
datastore
storage controller or array
storage fabric and paths
management network
Kubernetes API endpoint or load balancer
control-plane network
power feed, rack, and site
```

The same diagram can mean very different things depending on those layers.

If `master-1`, `master-2`, and `master-3` run on different ESXi hosts but all their boot disks live on the same shared datastore backed by one array, compute placement is separated. Storage failure is not.

If `etcd-1`, `etcd-2`, and `etcd-3` run on different ESXi hosts but all three depend on one storage fabric, one fabric failure can remove all three members from useful service.

If the API endpoint is a virtual IP or load balancer that depends on one VM, one appliance, one network segment, or one external system, a healthy control plane and healthy etcd quorum may still be unreachable to clients.

The design should keep asking:

```text
What exactly have we made independent?
```

For the base topology, the answer is compute-host placement. Everything else must be proven separately.

## The Failure Matrix Is The Design Tool

The failure matrix is not a summary after the architecture is finished. It is how the architecture is tested.

Each row asks what disappears, what remains, and which hidden assumptions must be true for the design to survive. The language is intentionally conditional. The correct answer is often "survives if..." rather than "survives."

| Failure | Components Lost | etcd Quorum State | Kubernetes API / Control-Plane Impact | Does vSphere HA Help? | Survival Assumption |
|---|---|---|---|---|---|
| `master-1` VM failure | one control-plane VM | quorum unaffected if all etcd members remain healthy | API should remain reachable through other control-plane nodes if endpoint routing removes or avoids `master-1` | may restart `master-1` if HA detects VM/host failure and restart conditions are met | API endpoint has healthy backends, remaining control-plane nodes are healthy, and clients do not depend on the failed VM directly |
| `etcd-1` VM failure | one etcd member | 2 of 3 remain; quorum should survive | API should continue if remaining etcd members are healthy and reachable | may restart `etcd-1` depending on failure type and storage accessibility | remaining etcd members can communicate, storage is consistent, and no second etcd member is degraded |
| one ESXi host failure | one master and one etcd member | 2 of 3 remain; quorum should survive | API should continue through surviving control-plane nodes if endpoint and network remain healthy | can attempt to restart failed VMs on surviving hosts | shared dependencies on storage, network, API endpoint, and capacity do not fail with the ESXi host |
| two ESXi host failures | two masters and two etcd members | 1 of 3 remains; quorum lost | API cannot operate normally because datastore quorum is lost | may not help unless VMs can restart quickly and safely on remaining capacity, which is unlikely with one host left | not normally a survivable design target for a 3-member etcd cluster |
| one datastore failure | any VMs whose boot or data disks reside there | survives only if no more than one etcd member depends on that datastore | API impact depends on which master VMs and etcd disks were on the datastore | may restart VMs only if their disks are accessible elsewhere | datastore placement maps one etcd member per independent storage failure domain |
| shared datastore or shared storage-array failure | potentially all six VMs, or all etcd data disks | quorum likely lost if multiple etcd members depend on it | API likely unavailable even if ESXi hosts are alive | does not help if VM disks are inaccessible | storage was not actually independent; redundancy inside one array did not equal failure-domain independence |
| vCenter failure | management plane unavailable; running VMs usually continue | quorum should remain if ESXi hosts, VMs, storage, and network remain healthy | API should remain if Kubernetes dependencies are independent of vCenter | HA/DRS operations and visibility may be impaired depending on state and timing | running VMs do not require vCenter for runtime, but operational response and cluster services may depend on it |
| API load balancer or registration endpoint failure | client path to API and node registration path may fail | etcd quorum can remain healthy | clients may lose API access even while control-plane nodes are healthy | HA helps only if the endpoint itself is protected and restarted | API endpoint is redundant, health-checks backends correctly, and is not a hidden single failure domain |
| management network failure | vCenter, SSH, automation, or monitoring paths may be lost | quorum may remain if etcd/control-plane networks are separate and healthy | API may remain available, but operators may be blind or unable to intervene | does not solve out-of-band management loss | control-plane traffic, management traffic, and operator access paths are understood separately |
| storage network or path failure | VMs or etcd disks using that path may stall or disconnect | survives only if at least two etcd members retain stable storage and network | API may degrade or fail if etcd I/O stalls | may not help if storage path remains unavailable on target hosts | multipathing, path failover, and storage fabric independence work as expected |
| resource exhaustion on one ESXi host | VMs may remain up but starved; etcd latency can rise | quorum may technically exist but become unhealthy under latency | API can become slow or unstable even without VM failure | HA usually does not move healthy-but-starved VMs unless DRS policy acts | reservations, DRS, admission control, and failure-state capacity protect control-plane VMs |

The matrix exposes the design boundary. The topology is strong for one row: one ESXi host failure. It is conditionally useful for several others. It does almost nothing by itself for shared storage failure, API endpoint failure, power failure, fabric failure, or capacity exhaustion.

That is not a weakness of the placement pattern. It is the point of doing the analysis. The pattern is useful when everyone understands exactly which independence it creates.

## Storage Separation Is Not Storage Independence

Storage deserves its own section because it is where many virtualization designs accidentally compress three apparent failure domains back into one.

There is a difference between storage separation and storage independence.

Storage separation might mean:

```text
master-1 and etcd-1 use datastore-a
master-2 and etcd-2 use datastore-b
master-3 and etcd-3 use datastore-c
```

That proves only that the VMs use different datastore objects.

It does not prove independent storage failure domains if all three datastores share:

```text
the same array
```

Independent storage means a failure in one storage domain does not remove the data path for the other two etcd members. Multiple datastores can help express that design, but they are not proof of it.

Ask again:

```text
What exactly have we made independent?
```

If the answer is "three datastore names," the design is not finished. If the answer is "three separately failing storage paths with separate underlying dependencies," the design is closer to the topology it claims.

For etcd, this matters more than for many stateless control-plane components. The etcd data directory is the durable cluster state. A VM can restart; a corrupt or unavailable etcd data disk can turn a clean compute failure into a quorum or recovery problem.

Consider these cases.

With one shared datastore or array:

```text
ESXi host failure:
  possibly survivable

shared datastore failure:
  multiple or all members affected
  placement across ESXi hosts does not help
```

With genuinely independent storage failure domains:

```text
ESXi host failure:
  one master and one etcd affected

one storage domain failure:
  one etcd member affected
  quorum can survive if the other two storage domains are healthy
```

Shared storage redundancy still has value. Redundant controllers, multipathing, battery-backed cache, replication, snapshots, and non-disruptive maintenance can all improve availability. But redundancy inside one shared storage system is not the same as independent storage failure domains. A redundant SAN can still be one failure domain for the Kubernetes control plane if all etcd disks depend on it.

## vCenter, ESXi Runtime, Kubernetes API, And etcd Are Different Planes

Avoid collapsing these systems into one availability statement.

vCenter availability is management-plane availability. It affects inventory visibility, vMotion operations, DRS management, HA management visibility, task history, automation, and operator response.

ESXi runtime availability is whether the hypervisor continues running the VMs.

Kubernetes control-plane availability is whether the API servers, controllers, scheduler, certificates, networking, and admission paths can serve useful requests.

etcd data availability is whether a majority of etcd members can communicate and commit state.

API endpoint availability is whether clients and joining nodes have a working path to the serving API and registration ports.

Losing vCenter does not inherently stop running Kubernetes VMs. If ESXi hosts, VM disks, VM networks, API endpoint routing, and etcd quorum remain healthy, Kubernetes can continue serving. But losing vCenter can still matter operationally: HA/DRS visibility changes, automation may fail, operators may lose event history, and planned placement or recovery actions may be blocked.

Likewise, healthy etcd quorum and healthy API servers do not automatically mean clients can reach the API. RKE2 HA requires a fixed registration address in front of server nodes. That endpoint may be implemented with a layer 4 load balancer, DNS, a virtual IP, or another platform-specific method. If that endpoint is a single failure domain, the control plane can be healthy behind a broken front door.

Add the endpoint to the same dependency review:

```text
What exactly have we made independent?

API servers:       maybe three
etcd quorum:       maybe three members
API endpoint:      maybe one appliance, one VIP, one DNS dependency, or one network path
```

The endpoint has to be designed, monitored, and tested as part of the control plane.

## vSphere HA And RKE2 HA Do Different Jobs

RKE2/Kubernetes HA and vSphere HA are complementary. They are not the same mechanism.

```text
RKE2/Kubernetes HA:
  surviving members continue providing the service

vSphere HA:
  attempts to restart failed VMs on surviving ESXi hosts
```

Use the `ESXi-2` failure case:

```text
Initial placement
-----------------
ESXi-1: master-1  etcd-1
ESXi-2: master-2  etcd-2
ESXi-3: master-3  etcd-3

ESXi-2 fails
------------
Lost:      master-2  etcd-2
Remaining: master-1  master-3
           etcd-1    etcd-3
```

RKE2 and etcd should survive if the remaining members and dependencies are healthy. etcd still has 2 of 3 members. API service can continue if the surviving control-plane nodes are healthy and the API endpoint routes to them.

Then vSphere HA may attempt to restart `master-2` and `etcd-2` on `ESXi-1` or `ESXi-3`. That can improve redundancy after the initial failure, but it changes the placement model:

```text
temporary post-HA placement
---------------------------
ESXi-1: master-1  etcd-1  master-2
ESXi-3: master-3  etcd-3  etcd-2
```

The original symmetry is gone. That may be acceptable. It may even be the desired behavior during an outage. But it should be a deliberate policy choice, not an accident.

The central design question is:

```text
During an outage, should vSphere violate placement to restart the VM,
or preserve placement purity and leave it powered off?
```

There is no universal answer.

If the rule is mandatory, HA may be unable to restart the VM on the surviving hosts if the required host is gone. That preserves placement purity but may leave capacity unused and the VM powered off.

If the rule is preferential, HA/DRS may place the VM on another host. That improves service restoration but temporarily concentrates failure risk and capacity pressure.

The right answer depends on what the architecture values during a failure: immediate VM availability, strict failure-domain purity, or a staged operational recovery where humans decide when to break symmetry.

## Initial, Preferred, And Mandatory Placement

Placement controls are not interchangeable.

Initial placement says where a VM starts.

Preferred placement says where a VM should run when the cluster has enough healthy capacity.

Mandatory placement says where a VM must run, even if that prevents restart during failure.

Those are different contracts.

Terraform can set initial VM placement during creation. For example, a VM resource may set `host_system_id` to place `master-1` on `esxi-1`. That is not the same as persistent DRS policy. It does not, by itself, say that `master-1` must remain on `esxi-1` after vMotion, incident response, DRS action, storage maintenance, or HA restart.

vSphere VM-host rules, VM anti-affinity rules, DRS automation level, manual pinning, and resource pools all influence placement differently.

Use this distinction during design review:

```text
Initial placement:
  Terraform creates master-1 on esxi-1.

Preferred placement:
  DRS should normally keep master-1 associated with the esxi-1 failure domain.

Mandatory placement:
  master-1 must not run anywhere except its assigned failure domain.
```

Mandatory rules can protect topology purity and also block recovery. Preferred rules can recover more aggressively and also violate the topology under pressure. Manual pinning can be clear but can also become stale operational debt. Resource pools can protect capacity priority when configured with reservations and shares, but they do not define failure domains.

The policy should be written in operational terms:

```text
normal state: preserve one control-plane and one etcd member per ESXi host
host failure: allow or deny temporary co-location according to recovery policy
post-failure: restore placement symmetry after the failed host returns
```

## Failure-State Capacity Is Part Of HA

Resource pools and reservations matter here only because failure-state capacity matters.

If each ESXi host normally runs:

```text
1 control-plane VM
1 etcd VM
other workloads
```

then after one ESXi host disappears, the surviving two hosts must have enough CPU, memory, storage I/O, and network capacity to run:

```text
their original workloads
surviving control-plane and etcd VMs
possibly HA-restarted control-plane and etcd VMs
the remaining application workload load
```

If the cluster cannot run the critical set after one host fails, then the architecture is not N+1 even if the VM placement diagram looks redundant.

Reservations can help. CPU and memory reservations for etcd and control-plane VMs can preserve scheduling entitlement during contention. This is especially relevant for etcd, where latency and I/O stalls can turn resource pressure into control-plane instability.

But reservations are not free. They consume admission-control capacity. They can reduce HA restart flexibility. Excessive reservations can prevent vSphere from powering on VMs that would otherwise run acceptably. A reservation policy must be tied to failure-state capacity, not copied from another cluster.

Review these signals:

```text
normal-state CPU and memory utilization
failure-state utilization after one host disappears
CPU ready on control-plane and etcd VMs
memory ballooning or swapping
datastore latency
storage path saturation
HA admission-control policy
DRS recommendations and constraints
resource pool reservations, limits, and shares
```

Avoid a control-plane resource pool that is only a folder with a stronger name. A resource pool can express capacity policy, but only if shares, reservations, limits, monitoring, and admission-control impact are understood.

Ask again:

```text
What exactly have we made independent?
```

If all six VMs are placed across three hosts but all three hosts are running at a level where one host failure causes CPU ready spikes, memory pressure, or datastore latency, the independence is mostly cosmetic.

## Planned ESXi Maintenance

The same reasoning applies to maintenance. Do not place `ESXi-1` into maintenance mode just because the diagram says the cluster can lose one host. Prove the current system can lose that host today.

Before maintaining `ESXi-1`, verify:

```text
master-2 and master-3 are Ready
etcd-2 and etcd-3 are healthy
etcd quorum is healthy
the API endpoint routes to healthy backends
storage paths are healthy
datastores backing surviving etcd members are healthy
surviving ESXi hosts have failure-state capacity
HA and DRS behavior is understood
placement rules will not block required evacuations
control-plane services are stable
```

Useful Kubernetes and etcd checks include:

```bash
kubectl get nodes -o wide
kubectl get --raw='/readyz?verbose'
```

From an RKE2 server with approved etcd client credentials, scope etcd checks carefully:

```bash
sudo ETCDCTL_API=3 etcdctl endpoint health --cluster -w table \
  --cacert=/var/lib/rancher/rke2/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/rke2/server/tls/etcd/client.crt \
  --key=/var/lib/rancher/rke2/server/tls/etcd/client.key

sudo ETCDCTL_API=3 etcdctl endpoint status --cluster -w table \
  --cacert=/var/lib/rancher/rke2/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/rke2/server/tls/etcd/client.crt \
  --key=/var/lib/rancher/rke2/server/tls/etcd/client.key
```

The goal is not to run impressive commands. The goal is to decide whether removing one host is still inside the design envelope.

"We can lose one host" is not a property to assert once during design. It is a condition to verify before each deliberate host removal.

## Conceptual Terraform Placement

Terraform can make the initial placement explicit. Keep the configuration data-driven so the topology is visible in one map rather than hidden across six copied resources.

This example is conceptual and sanitized. It demonstrates placement intent, not a complete module.

```hcl
locals {
  rke2_servers = {
    "master-1" = {
      role = "control-plane"
      host = "esxi-1"
    }
    "master-2" = {
      role = "control-plane"
      host = "esxi-2"
    }
    "master-3" = {
      role = "control-plane"
      host = "esxi-3"
    }
    "etcd-1" = {
      role = "etcd"
      host = "esxi-1"
    }
    "etcd-2" = {
      role = "etcd"
      host = "esxi-2"
    }
    "etcd-3" = {
      role = "etcd"
      host = "esxi-3"
    }
  }

  esxi_hosts = toset([
    "esxi-1",
    "esxi-2",
    "esxi-3",
  ])
}

data "vsphere_datacenter" "dc" {
  name = var.datacenter_name
}

data "vsphere_compute_cluster" "cluster" {
  name          = var.cluster_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_host" "esxi" {
  for_each      = local.esxi_hosts
  name          = each.key
  datacenter_id = data.vsphere_datacenter.dc.id
}

resource "vsphere_virtual_machine" "rke2_server" {
  for_each = local.rke2_servers

  name             = each.key
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  host_system_id   = data.vsphere_host.esxi[each.value.host].id
  datastore_id     = var.datastore_id_by_node[each.key]
  folder           = var.vm_folder

  num_cpus = var.vm_shape_by_role[each.value.role].cpu
  memory   = var.vm_shape_by_role[each.value.role].memory_mb

  guest_id  = var.guest_id
  scsi_type = var.scsi_type

  network_interface {
    network_id   = var.network_id
    adapter_type = var.adapter_type
  }

  disk {
    label = "boot"
    size  = var.vm_shape_by_role[each.value.role].boot_disk_gb
  }

  extra_config = {
    "guestinfo.rke2-role" = each.value.role
  }
}
```

The map makes the intended placement clear:

```text
master-1 -> esxi-1
master-2 -> esxi-2
master-3 -> esxi-3
etcd-1   -> esxi-1
etcd-2   -> esxi-2
etcd-3   -> esxi-3
```

But this is initial placement. It is not persistent placement policy.

If DRS can later move the VM, if an operator can vMotion it during maintenance, if vSphere HA can restart it elsewhere, or if Terraform later ignores `host_system_id` drift, the original host setting becomes historical evidence rather than a runtime guarantee.

Persistent placement belongs in vSphere policy: VM-host rules, VM anti-affinity, DRS settings, operational runbooks, and validation. Terraform may manage those policies if the provider and module do so intentionally, but the model should still distinguish initial placement from preferred or mandatory runtime placement.

## RKE2 Role Configuration Boundary

In current RKE2 documentation, a dedicated `etcd` server disables the control-plane components:

```yaml
disable-apiserver: true
disable-controller-manager: true
disable-scheduler: true
```

A dedicated `control-plane` server disables etcd and joins an existing server with the etcd role:

```yaml
server: https://<etcd-or-registration-endpoint>:9345
disable-etcd: true
```

That role split should be reflected in inventory, VM labels, monitoring, backup logic, maintenance gates, and node replacement runbooks. Do not let the VM name `master-1` become the only source of truth for what the node actually runs.

RKE2 also needs a fixed registration address for additional servers and agents. That address is part of the architecture. It should not be an afterthought added after the VM topology is complete.

## Read-Only Validation

Validation should produce evidence for each layer of the design.

Prove Kubernetes sees the expected server nodes:

```bash
kubectl get nodes -o wide
kubectl get nodes -L node-role.kubernetes.io/control-plane,node-role.kubernetes.io/etcd
```

Prove the API server is healthy from a client path that represents real use:

```bash
kubectl get --raw='/readyz?verbose'
kubectl cluster-info
```

If the API endpoint is a load balancer or virtual IP, test the endpoint itself, not just a local server node:

```bash
curl -k https://api.example.com:6443/readyz
```

Use the real endpoint name for the environment. Keep public notes generic.

Prove etcd health from an approved RKE2 server context:

```bash
sudo ETCDCTL_API=3 etcdctl endpoint health --cluster -w table \
  --cacert=/var/lib/rancher/rke2/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/rke2/server/tls/etcd/client.crt \
  --key=/var/lib/rancher/rke2/server/tls/etcd/client.key
```

Prove current VM placement in vSphere:

```bash
for vm in master-1 master-2 master-3 etcd-1 etcd-2 etcd-3; do
  govc vm.info -json "$vm" \
    | jq -r '.virtualMachines[] | [.name, .runtime.host.value] | @tsv'
done
```

The host value may be a managed object reference. In many environments, operators will combine `govc vm.info`, `govc object.collect`, or inventory views to resolve it to an ESXi host name. The important evidence is current runtime placement, not only Terraform intent.

Prove datastore placement:

```bash
for vm in master-1 master-2 master-3 etcd-1 etcd-2 etcd-3; do
  govc vm.info -json "$vm" \
    | jq -r '.virtualMachines[] | .name as $vm | .config.hardware.device[]? | select(.deviceInfo.label | startswith("Hard disk")) | [$vm, .deviceInfo.label, .backing.fileName] | @tsv'
done
```

That shows datastore names. It does not prove storage independence. Use storage platform evidence to map each datastore to the underlying array, controller, pool, fabric, and power dependencies.

Review resource reservations and runtime pressure through vCenter, monitoring, or `govc` views available in the environment. Preserve the distinction between configuration and evidence:

```text
Configured reservation: what vSphere was told
Observed CPU ready: whether the VM is waiting for CPU
Observed memory pressure: whether the VM is reclaiming, ballooning, or swapping
Observed datastore latency: whether etcd storage is healthy under load
```

Review HA and DRS rules through the vSphere UI, `govc`, PowerCLI, or the approved automation source of truth. The validation question is simple:

```text
If ESXi-2 fails, are master-2 and etcd-2 allowed to restart elsewhere?
If yes, where?
If no, is that intentional?
```

## What This Topology Does And Does Not Accomplish

It does accomplish this:

```text
loss of one ESXi compute host removes only one control-plane VM and one etcd VM
```

It can support this outcome:

```text
etcd quorum survives one ESXi host failure
Kubernetes API remains available through surviving control-plane nodes
```

But only if these are also true:

```text
the remaining two etcd members are healthy
the network path remains healthy
the storage backing surviving etcd members remains healthy
the surviving ESXi hosts have enough failure-state capacity
vSphere HA/DRS policy does not block the intended recovery
```

It does not accomplish these by itself:

```text
independent storage failure domains
independent network failure domains
independent power failure domains
independent API endpoint failure domains
automatic capacity after one host failure
safe restart behavior under hard affinity rules
protection from two ESXi host failures with a 3-member etcd quorum
```

The architecture is useful, but it is narrower than it looks. It is a compute placement design until the other dependencies are proven independent.

## Architectural Conclusion

Spreading six VMs across three ESXi hosts is a good starting point. It prevents one ESXi host failure from removing multiple members of the same three-member role. For etcd, that matters because a three-member cluster can lose one member and still retain quorum.

But the placement diagram is not the architecture. It is one layer of the architecture.

The real review is the repeated question:

```text
What exactly have we made independent?
```

If the answer is only "the VMs run on different ESXi hosts," then the design protects against one ESXi compute-host failure and little more.

If the answer includes independent storage failure domains, independent API endpoint paths, sufficient failure-state capacity, tested HA/DRS behavior, and clear placement policy, then the topology starts to represent meaningful control-plane resilience.

Placement creates separation. Independent dependencies create resilience.

## References

- [RKE2 High Availability](https://docs.rke2.io/install/ha)
- [RKE2 Managing Server Roles](https://docs.rke2.io/install/server_roles)
- [RKE2 Server Configuration Reference](https://docs.rke2.io/reference/server_config)
- [etcd Runtime Reconfiguration](https://etcd.io/docs/v3.5/op-guide/runtime-configuration/)
- [VMware vSphere Availability](https://docs.vmware.com/en/VMware-vSphere/8.0/vsphere-availability/)
- [VMware vSphere Resource Management](https://docs.vmware.com/en/VMware-vSphere/8.0/vsphere-resource-management/)
- [Terraform vSphere Provider: virtual_machine](https://registry.terraform.io/providers/hashicorp/vsphere/latest/docs/resources/virtual_machine)
- [vSphere Cluster Design Operating Boundaries](/field-notes/vsphere-cluster-design-operating-boundaries/)
- [vSphere DRS And Resource Pool Operational Model](/field-notes/vsphere-drs-resource-pool-operational-model/)
- [vSphere HA Reset Evidence For Kubernetes Nodes](/field-notes/vsphere-ha-reset-evidence-kubernetes-nodes/)
- [Terraform Refresh-Only Before Narrow vSphere Applies](/field-notes/terraform-refresh-only-before-narrow-vsphere-apply/)
- [RKE2 Node Reboots When Longhorn Is Already Degraded](/posts/rke2-node-reboots-longhorn-degraded-risk/)
