---
name: colab-cli
description: Operate Google Colab cloud runtimes (T4, L4, A100, H100 GPUs and TPUs) from WSL/terminal using the installed `colab` CLI and Google Drive `gdrive` CLI under the user's Colab Ultra subscription. Use whenever asked to train, run, manage, or automate deep learning or GPU workloads on Google Colab from the terminal.
---

# Google Colab CLI (Colab Ultra Local Control)

Use `colab` (installed at `~/.local/bin/colab`) to control remote Google Colab GPU/TPU runtimes from this WSL terminal. The user holds an active **Google Colab Ultra subscription** with compute units for **L4**, **A100**, and **H100** cloud GPUs.

Before provisioning or running Colab jobs, consult [`/home/rog/COLAB_LOCAL_CONTROL.md`](file:///home/rog/COLAB_LOCAL_CONTROL.md) (or [`general/guides/colab-local-control/COLAB_LOCAL_CONTROL.md`](file:///home/rog/AI-management/general/guides/colab-local-control/COLAB_LOCAL_CONTROL.md)).

## Golden Rules
1. **Never unilaterally substitute local hardware for cloud tasks.** When a project plan, step specification, or user instruction calls for Colab or remote GPU training, never attempt to train locally on laptop hardware or install heavy CUDA packages locally unless explicitly ordered by the user.
2. **Path Setup:** Always ensure `export PATH=$HOME/.local/bin:$PATH` is set.
3. **VM Lifecycle:** Always issue `colab stop` once a job completes to prevent burning compute units on idle runtimes.

## Common Workflows

### 1. Provisioning a GPU Session
```bash
export PATH=$HOME/.local/bin:$PATH
colab new --gpu L4 -s my-run      # Options: T4, L4, A100, H100
colab sessions                    # Verify session is READY
```

### 2. Dependency Installation
```bash
colab install -s my-run -r requirements.txt
# or individual packages:
colab install -s my-run torch torchvision torchaudio
```

### 3. File Transfer
- **Small files / archives (< 50MB):**
  ```bash
  colab upload local_bundle.tar.gz bundle.tar.gz
  colab download output_preds.parquet local_preds.parquet
  ```
- **Large datasets (> 50MB):** Use Google Drive mount:
  ```bash
  colab drivemount /content/drive
  ```
  Or use the pre-installed `gdrive` CLI (`~/.local/bin/gdrive`).

### 4. Running Scripts Non-Interactively
```bash
# Note: Default timeout is only 30s. Always pass --timeout for training jobs!
colab exec -s my-run -f train.py --timeout 7200
```

### 5. Cleanup
```bash
colab stop -s my-run
```
