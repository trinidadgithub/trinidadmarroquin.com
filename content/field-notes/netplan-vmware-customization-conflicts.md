+++
title = 'Netplan Conflicts After VMware Guest Customization'
date = 2026-06-09T00:00:00-05:00
draft = false
description = 'Field note for diagnosing duplicate netplan ownership, missing default routes, and DNS drift on vSphere Ubuntu VMs.'
tags = ['vsphere', 'netplan', 'cloud-init', 'linux', 'terraform']
categories = ['field-notes']
+++

VMware guest customization can write `/etc/netplan/99-netcfg-vmware.yaml`. If the template already has another active netplan file, the host can end up with multiple network authorities.

That can break routing, DNS, bootstrap scripts, Kubernetes node communication, and storage initialization.

## Symptoms

Common signs:

```text
Error: Conflicting default route declarations for IPv4
first declared in nic0 but also in ens192
```

or:

```text
Destination Host Unreachable
```

or DNS search drift like:

```text
resolv_conf_search = .
netplan_search = []
```

## Inspect Netplan Ownership

```bash
ls -l /etc/netplan
sudo grep -R "routes:\|gateway\|search:" /etc/netplan -n
```

If both a template file and VMware file are present, decide which one owns networking.

Example conflict:

```text
/etc/netplan/01-template-static.yaml
/etc/netplan/99-netcfg-vmware.yaml
```

## Verify Active Routing

```bash
ip -br addr
ip route
networkctl status ens192 --no-pager
```

If the default route is missing, test the expected route manually:

```bash
sudo ip route replace default via 10.0.232.1 dev ens192
ping -c 3 10.0.232.1
```

If ARP fails, compare the vSphere port group against a working VM:

```bash
govc device.ls -vm /VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-11-uat
govc device.ls -vm /VC-Austin/vm/K8-Cluster/UAT/AUS-1-wrkr-12-uat
```

## Normalize To One Netplan File

If VMware customization is the current network authority, keep only the VMware-generated file:

```bash
if [ -f /etc/netplan/99-netcfg-vmware.yaml ]; then
  for f in /etc/netplan/*.yaml /etc/netplan/*.yml; do
    [ -f "$f" ] || continue
    case "$f" in
      /etc/netplan/99-netcfg-vmware.yaml)
        echo "keeping $f"
        ;;
      *)
        echo "removing $f"
        rm -f "$f"
        ;;
    esac
  done
fi
```

Then validate and apply:

```bash
sudo netplan generate
sudo netplan apply
ip route
resolvectl status
```

## Important Shell Detail

If this is run through Ansible `shell`, remember that `/bin/sh` may execute the script. Bash-only syntax such as `[[ ... ]]` can fail:

```text
/bin/sh: 47: [[: not found
```

Use POSIX `[ ... ]` syntax or explicitly run the script with Bash.

## Operating Model

Pick one owner:

- VMware customization owns primary NIC, hostname, gateway, and DNS.
- Bootstrap owns additional storage NICs and iSCSI-specific netplan.
- Cloud-init userdata runs bootstrap and avoids competing with network ownership.

The failure pattern is usually not one bad command. It is multiple systems trying to own the same network configuration.
