+++
title = 'Azure AKS Operations With Terraform'
date = 2026-06-10T00:00:00-05:00
draft = false
description = 'Field note for provisioning Azure AKS clusters with Terraform, including networking, identity, storage backends, and cross-cloud comparison patterns.'
tags = ['azure', 'aks', 'terraform', 'cloud']
categories = ['field-notes']
+++

Azure Kubernetes Service follows the same managed-control-plane pattern as EKS and GKE, but the resource model, networking defaults, and identity system are different enough that provider-specific knowledge matters during provisioning.

For a runnable lab, see the [`azure` directory in the IaC repository](https://github.com/trinidadgithub/IaC/tree/main/azure).

## Resource Group Structure

Everything in Azure lives in a resource group. The AKS cluster, VNet, and NSG are typically in the same group for a lab, but production should separate network infrastructure into a shared resource group owned by the platform team:

```hcl
resource "azurerm_resource_group" "aks_rg" {
  name     = "aks-resources"
  location = "East US"
}
```

Resource groups are the boundary for role assignments, locks, and tags. A cluster in the wrong resource group inherits the wrong policies.

## Network Model

Azure AKS uses the `azure` network plugin by default, which assigns pod IPs from the subnet directly. This differs from AWS (where the CNI manages ENIs) and GCP (where alias IPs are used):

```hcl
network_profile {
  network_plugin = "azure"
}
```

With the Azure CNI, every pod gets an IP from the VNet subnet. This means subnet size limits cluster scale more than node count does. Plan the address space for the maximum expected pod count before provisioning.

## System-Assigned Identity

AKS can use a system-assigned managed identity instead of a service principal:

```hcl
identity {
  type = "SystemAssigned"
}
```

This removes the credential rotation problem of service principals. The identity is tied to the cluster lifecycle and does not require manual secret management. For production, use a user-assigned identity with pre-configured role assignments so the identity can be created and authorized before the cluster references it.

## Network Security Groups

Azure applies NSG rules at the subnet or NIC level. The AKS lab opens HTTPS as an example:

```hcl
security_rule {
  name                       = "allow-https"
  priority                   = 1000
  direction                  = "Inbound"
  access                     = "Allow"
  protocol                   = "Tcp"
  destination_port_range     = "443"
  source_address_prefix      = "*"
  destination_address_prefix = "*"
}
```

AKS creates its own NSG rules for the node pool. Adding custom rules to the same subnet can conflict with AKS-managed rules. Use `azurerm_subnet_network_security_group_association` carefully and test rule priority ordering.

## Terraform State Backend

Azure Blob Storage is a common Terraform state backend:

```hcl
terraform {
  backend "azurerm" {
    storage_account_name = "trinidadstorageacct"
    container_name       = "terraform-state"
    key                  = "azure-storage-account/terraform.tfstate"
  }
}
```

The storage account uses LRS replication by default. For shared team access, enable blob soft delete and versioning on the state container. See also: [Terraform Azure Backend Bootstrap](/field-notes/terraform-azure-backend-bootstrap/).

## Cross-Cloud Comparison

| Concern | Azure | AWS | GCP |
|---|---|---|---|
| Resource boundary | Resource group | Account | Project |
| Network scope | Regional VNet | Regional VPC | Global VPC |
| Pod networking | Azure CNI (subnet IPs) | VPC CNI (ENI IPs) | Alias IPs |
| Cluster identity | Managed Identity | IAM role | Service Account |
| State backend | Blob Storage | S3 | GCS |

## Acceptance Criteria

- AKS cluster deploys without service principal credential management.
- Pod CIDR and subnet size support the target node and pod count.
- Custom NSG rules do not conflict with AKS-managed rules.
- Terraform state is stored in a versioned, access-controlled backend.
- Cluster endpoint is reachable from authorized networks only.
