+++
title = 'DevOps And SRE Linux Workstation'
date = 2026-06-23T00:00:00-05:00
draft = false
description = 'Reference for setting up a Linux-based engineering workstation: OS selection, core toolchain, shell hygiene, secret management, session persistence, and bootstrap automation.'
tags = ['workstation', 'linux', 'tools', 'devops', 'sre', 'productivity']
categories = ['field-notes']
last_updated = 2026-06-23
+++

This field note documents the engineering workstation baseline used across the runbooks and field notes in this site. It is a living document — tools are added as they prove value and removed when they are retired.

## OS Selection

Two distributions cover the majority of infrastructure engineering environments:

| Distribution | Strengths | Considerations |
|---|---|---|
| **Ubuntu LTS** (24.04+) | Broad package availability, largest community, NVidia driver support, first-class Snap/Flatpak support | Canonical's Snap push can be invasive; pin to LTS to avoid churn |
| **Debian Stable** (12+) | Rock-solid stability, no corporate backing, minimal pre-installed cruft | Older packages; backports or third-party repos needed for newer tooling |

Both run the same toolchain. The choice is primarily about release cadence and package freshness vs. stability.

**Hardware minimums** for a daily-driver management workstation:

- CPU: 4+ cores (8 recommended for local container builds)
- RAM: 16 GB minimum, 32 GB recommended (multiple kubeconfigs, browser tabs, local kind/microk8s clusters)
- SSD: 256 GB minimum, 512 GB recommended (container images, multiple tool versions, git repos)
- Network: Reliable connectivity to cloud APIs, VPN, and internal infrastructure

## Core Toolchain

### Package Management

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y \
  curl wget git jq yq unzip \
  gnupg lsb-release ca-certificates \
  direnv tree htop iotop

# Enable unattended security upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### Kubernetes Tooling

```bash
# kubectl — always match the cluster version or one minor version ahead
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/ && rm kubectl

# Helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Velero CLI
curl -LO https://github.com/vmware-tanzu/velero/releases/latest/download/velero-v1.15.0-linux-amd64.tar.gz
tar xzf velero-*-linux-amd64.tar.gz && sudo mv velero-*/velero /usr/local/bin/ && rm -rf velero-*

# kustomize
curl -fsSL https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh | bash
sudo mv kustomize /usr/local/bin/

# stern — tail multiple pods and containers
curl -Lo stern.tar.gz https://github.com/stern/stern/releases/latest/download/stern_*_linux_amd64.tar.gz
tar xzf stern.tar.gz && sudo mv stern /usr/local/bin/ && rm stern.tar.gz

# Popeye — cluster health scanner
curl -Lo popeye.tar.gz https://github.com/derailed/popeye/releases/latest/download/popeye_linux_amd64.tar.gz
tar xzf popeye.tar.gz && sudo mv popeye /usr/local/bin/ && rm popeye.tar.gz
```

### Infrastructure-As-Code

```bash
# Terraform — use tfenv to pin per-project versions
git clone https://github.com/tfutils/tfenv.git ~/.tfenv
~/.tfenv/bin/tfenv install latest
echo 'export PATH="$HOME/.tfenv/bin:$PATH"' >> ~/.bashrc

# Terragrunt
curl -Lo terragrunt https://github.com/gruntwork-io/terragrunt/releases/latest/download/terragrunt_linux_amd64
sudo mv terragrunt /usr/local/bin/ && chmod +x /usr/local/bin/terragrunt

# tflint
curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash

# Checkov — policy-as-code scanner
pip3 install checkov
```

### Cloud CLIs

```bash
# AWS CLI v2
curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip

# Vault CLI
curl -fsSL https://releases.hashicorp.com/vault/1.18.0/vault_1.18.0_linux_amd64.zip -o vault.zip
unzip vault.zip && sudo mv vault /usr/local/bin/ && rm vault.zip

# govc (vSphere CLI)
curl -Lo govc.tar.gz https://github.com/vmware/govmomi/releases/latest/download/govc_$(uname -s)_$(uname -m).tar.gz
tar xzf govc.tar.gz && sudo mv govc /usr/local/bin/ && rm govc.tar.gz
```

### Containers

```bash
# Docker CE
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER

# Dive — container layer inspection
curl -Lo dive.tar.gz https://github.com/wagoodman/dive/releases/latest/download/dive_*_linux_amd64.tar.gz
tar xzf dive.tar.gz && sudo mv dive /usr/local/bin/ && rm dive.tar.gz
```

### General Tooling

```bash
# bat — cat with syntax highlighting
sudo apt install -y bat  # or: https://github.com/sharkdp/bat

# fzf — fuzzy finder
git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf && ~/.fzf/install

# ripgrep — fast recursive grep
sudo apt install -y ripgrep

# httpie — human-friendly curl alternative
pip3 install httpie

# age — simple file encryption
sudo apt install -y age
```

## Shell Hygiene

### Kubectl Aliases And Completions

```bash
cat >> ~/.bashrc << 'EOF'
source <(kubectl completion bash)
alias k='kubectl'
alias kg='kubectl get'
alias kd='kubectl describe'
alias kdel='kubectl delete'
alias kl='kubectl logs'
alias kaf='kubectl apply -f'
alias kx='kubectl ctx'    # requires kubectx
alias kn='kubectl ns'     # requires kubens

# Switch context with tab completion
complete -F __start_kubectl k
EOF

# kubectx / kubens
sudo git clone https://github.com/ahmetb/kubectx /opt/kubectx
sudo ln -s /opt/kubectx/kubectx /usr/local/bin/kubectx
sudo ln -s /opt/kubectx/kubens /usr/local/bin/kubens
```

### KUBECONFIG Management

The default `~/.kube/config` merge approach becomes unwieldy with more than a few clusters.

```bash
# Per-project kubeconfig directories
mkdir -p ~/.kube/configs

# Source the right config in each project via direnv
cat >> ~/.bashrc << 'EOF'
# KUBECONFIG merge helper — merges everything in ~/.kube/configs/
export KUBECONFIG=$(ls ~/.kube/configs/*.yaml 2>/dev/null | tr '\n' ':')
EOF
```

Create a `.envrc` per project to pin the kubeconfig:

```bash
# In each project root
echo 'export KUBECONFIG=~/.kube/configs/production.yaml' > .envrc
direnv allow
```

### Terraform Workspace Prompt

```bash
# Show terraform workspace in the prompt
cat >> ~/.bashrc << 'EOF'
parse_terraform_workspace() {
  if [ -f .terraform/environment ]; then
    echo " (tf:$(cat .terraform/environment))"
  fi
}
PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]$(parse_terraform_workspace)\$ '
EOF
```

## Session Persistence

Infrastructure work spans long-running apply operations, multi-step incident responses, and context switches across terminals.

### Tmux

```bash
sudo apt install -y tmux

# Minimal configuration
cat >> ~/.tmux.conf << 'EOF'
set -g default-terminal "screen-256color"
set -g history-limit 50000
set -g mouse on
bind | split-window -h
bind - split-window -v
bind r source-file ~/.tmux.conf \; display-message "Reloaded"
EOF
```

**Patterns:**

| Situation | Tmux Pattern |
|---|---|
| Terraform plan/apply | `tmux new -s infra-apply` — stay attached until complete |
| Incident response | `tmux new -s incident-<ticket>` with panes for logs, kubectl, runbook |
| Long tail of tailing logs | Detach (`C-b d`) and reattach later (`tmux attach -t <session>`) |
| Multi-cluster operations | One window per cluster, named by context |

## Secret Hygiene

Credentials live on the workstation temporarily and are never stored in plain text.

```bash
# Age key generation — one per workstation, backed up offline
age-keygen -o ~/.config/age/key.txt
chmod 600 ~/.config/age/key.txt

# Encrypt a secrets file
age -e -r "$(cat ~/.config/age/key.txt | age-keygen -y)" -o secrets.env.age secrets.env

# Decrypt inline
age -d -i ~/.config/age/key.txt secrets.env.age

# SOPS integration
cat >> ~/.sops.yaml << 'EOF'
creation_rules:
  - age: >-
      age1...
EOF
```

**Never do these:**

- Store cloud provider keys in `~/.bashrc` or shell history
- Commit `.env` files to git
- Use the same SSH key for GitHub and infrastructure access
- Leave `vault login` tokens in the terminal scrollback

## Bootstrap Automation

The entire workstation should be reproducible from a blank install.

```bash
# ~/bootstrap/bootstrap.sh — idempotent workstation setup
# Keep this in a private git repo

#!/usr/bin/env bash
set -euo pipefail

sudo apt update && sudo apt upgrade -y

# Install all tools (functions above)
# Clone dotfiles
# Set up SSH keys (requires out-of-band transfer)
# Install VS Code / extensions
```

A bootstrap script should be **idempotent** — running it twice produces the same result. Use `which <tool>` guards or `install -C` for binaries.

## When To Update This Document

- A new CLI becomes part of the standard incident response workflow
- A tool in the chain reaches end-of-life or is superseded
- The team standardizes on a different container runtime or orchestrator
- A security practice changes (e.g., hardware SSH keys, new encryption scheme)

## References

- [tmux: Productive Mouse-Free Development](https://pragprog.com/titles/bhtmux2/tmux-2/)
- [Direnv: Unclutter your .profile](https://direnv.net/)
- [The Twelve-Factor App: Dev/prod parity](https://12factor.net/dev-prod-parity)
- [Age: Simple, modern encryption](https://age-encryption.org/)
- [Kubectx + Kubens: Kubernetes context/namespace switching](https://github.com/ahmetb/kubectx)
