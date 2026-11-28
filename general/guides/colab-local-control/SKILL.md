---
name: colab-cli
description: Operate remote Google Colab cloud GPU/TPU runtimes (T4, L4, A100, H100 GPUs and TPUs; ~2,000 monthly Ultra Compute Units) and Google Drive (`gdrive` CLI) from WSL/terminal under the user's Colab Ultra subscription. Use whenever planning or executing neural/deep-learning/GPU workloads, choosing compute targets, encountering Colab/L4/A100/H100 in plans or specs, or scaling beyond lightweight local tests.
---

# Google Colab CLI (Colab Ultra Local Control)

Use `colab` (installed at `~/.local/bin/colab`, v0.8.0+) to control remote Google Colab GPU/TPU runtimes directly from WSL/terminal. The user holds an active **Google Colab Ultra subscription** (~2,000 monthly Compute Units) supporting **T4**, **L4**, **A100**, and **H100** cloud GPUs and TPUs (`v5e1`, `v6e1`), alongside pre-installed `gdrive` CLI (`~/.local/bin/gdrive`, v3.9.1+).

Before provisioning or running Colab jobs, read [`references/COLAB_LOCAL_CONTROL.md`](references/COLAB_LOCAL_CONTROL.md) (or `~/COLAB_LOCAL_CONTROL.md`).

## Governance & Golden Rules
1. **Cloud Compute Target Fidelity:** When a project plan, step specification, or user instruction designates remote cloud compute (Colab or GCP), **never** unilaterally substitute local workstation/laptop hardware (e.g., local RTX 5080) or install heavy local CUDA packages instead of using `colab` CLI / `gcp-cpu-ctl`, unless the user explicitly approves switching locally.
2. **Pre-Flight Discovery:** Never claim Colab is unavailable or browser-only without checking:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   colab version
   colab sessions
   ```
3. **Capacity Fallback Across Colab GPUs:** If one GPU tier (e.g., `A100`) returns `HTTP 503 Service Unavailable` or capacity exhaustion, fall back across other Colab GPU tiers (e.g., `--gpu H100` or `--gpu L4`) rather than abandoning Colab for local hardware.
4. **Compute-Unit Hygiene:** VM sessions consume Compute Units while alive. Always pair `colab new` / `colab exec` workflows with an explicit cleanup trap or `colab stop [-s NAME]` when finished (`colab run` auto-tears down unless `--keep` is passed).

## Common Workflows

### 1. Provisioning a GPU Session
```bash
export PATH="$HOME/.local/bin:$PATH"
colab new --gpu L4 -s my-run      # Options: T4, L4, G4, A100, H100
colab sessions                    # Verify session state
```

### 2. Dependency Installation & Remote Execution (`colab exec` exit-0 trap!)
- **Default timeout is 30s:** Always pass `--timeout` (e.g. `7200`) for training runs.
- **`colab exec` always returns exit code `0` even on Python tracebacks!** Verify an explicit completion sentinel (`content/DONE.json`), stderr output, and downloaded artifact hashes rather than trusting `$? == 0`.
```bash
colab install -s my-run -r requirements.txt
colab exec -s my-run -f train.py --timeout 7200
```

### 3. File Transfer (`content/` prefix REQUIRED!)
- **Small files / bundles (always prefix `content/...`!):** `colab ls` defaults to `content/` and `colab exec` runs in `/content`, **but `colab upload` / `download` / `rm` target Jupyter root `/`!** Passing a bare filename writes to `/` and causes `FileNotFoundError` in `colab exec`. Avoid single >400 MB HTTP 400 uploads.
  ```bash
  colab upload local_bundle.tar.gz content/bundle.tar.gz
  colab download content/output_preds.parquet local_preds.parquet
  ```
- **Large datasets:** Put files on Google Drive (`gdrive files upload ...`) and mount inside Colab with `colab drivemount /content/drive`.

### 4. Teardown
```bash
colab stop -s my-run
```
