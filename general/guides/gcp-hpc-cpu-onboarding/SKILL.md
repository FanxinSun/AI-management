---
name: gcp-cpu-compute
description: Control high-core remote Google Cloud Compute Engine CPUs (C4D / H4D Zen 5, 32-384 vCPUs, up to 3 TB DDR5) from WSL2 using gcloud and gcp-cpu-ctl in ~/sw. Read /home/rog/GCP_CPU_LOCAL_CONTROL.md before provisioning or pricing cloud CPU jobs.
---

# Remote High-Core CPU Route (GCP Compute Engine)

Remote high-core, high-RAM CPU compute is configured on this machine via Google Cloud SDK (`/home/rog/sw/google-cloud-sdk`) and `/home/rog/sw/gcp-cpu-ctl.sh` (symlinked as `gcp-cpu-ctl` in `~/.local/bin`).

## When to use this vs. local CPU or Colab GPU

1. **Keep on local AMD Ryzen 7 9800X3D (WSL2):** 1–16 threads, single-core IPC, or L3-cache-sensitive work (`9800X3D` @ up to 5.2 GHz + 96 MB 3D V-Cache beats every cloud CPU per core at $0 cost).
2. **Use Remote GCP CPU (`gcp-cpu-ctl` / `gcloud`):** Parallel workloads scaling to 32–384 vCPUs (`C4D` / `H4D` AMD EPYC "Turin" Zen 5), datasets needing $>64$ GB RAM (up to ~3 TB DDR5), or multi-node MPI/Slurm (`H4D` 192 dedicated physical cores + 200 Gbps Cloud RDMA). **Do NOT use Colab CPU runtimes** (2–8 slow vCPUs).
3. **Use Colab CLI (`/home/rog/COLAB_LOCAL_CONTROL.md`):** CUDA / GPU / TPU workloads (`T4` / `L4` / `A100` / `H100`).

## Before Running Commands

- Always read `/home/rog/GCP_CPU_LOCAL_CONTROL.md` first for workflows and safety rules.
- Account credentials/IDs are stored in `/home/rog/AI-management-private/general/guides/gcp-cpu-private/GCP_ACCOUNT_CREDENTIALS.md` (`restore-gcp-config.sh`).
- **Hard Guardrails:**
  - Never provision VMs (`gcp-cpu-ctl up` / `gcloud compute instances create`) or upload local files/code without explicit per-action user permission.
  - Never upload `~/sPHENIX` or any collaboration-internal/protected data.
  - Never use Spot/Preemptible VMs when relying on promotional Cloud credits (`cloud.google.com/skus/exclusions` excludes Spot/Preemptible; prefer on-demand `C4D`).
  - Always `delete` (`gcp-cpu-ctl down <name>`) rather than merely `stop` VMs so persistent disks do not keep accruing charges.
