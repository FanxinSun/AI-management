# Google Cloud HPC CPU Onboarding & Human-Agent Co-Execution Guide

Recorded on **2026-11-27** from a live WSL2 onboarding session evaluating Google Colab CPUs vs. local desktop Zen 5 silicon vs. Google Cloud Compute Engine HPC CPUs (`H4D` / `C4D`), activating `$0`-upfront Cloud credits, and documenting the "break-down teaching" human–agent workflow across Chrome security gates and multiple browser profiles.

*(Account-specific emails, Billing IDs, Project IDs, and CLI restore scripts live in the companion private repository `AI-management-private/general/guides/gcp-cpu-private/`.)*

---

## 1. Hardware & Cloud Evaluation: Colab CPU vs. AMD 9800X3D vs. GCP H4D/C4D

1. **Consumer Google Colab CPU is much weaker than a modern desktop Zen 5 CPU:**
   - Standard Colab Free provides 2 vCPUs (~12 GB RAM); Colab Pro/Ultra High-RAM provides ~8 vCPUs (~51–53 GB RAM) on virtualized ~2.0–2.8 GHz Intel Xeon or AMD EPYC 7B12 hosts.
   - An **AMD Ryzen 7 9800X3D** (8C/16T Zen 5, up to 5.2 GHz boost, **96 MB 3D V-Cache**) is **3.5×–5× faster per core** and **3×–4× faster multi-core** than Colab's built-in CPU runtimes. Never offload CPU-only jobs to Colab CPU runtimes.
2. **True HPC CPU rentals live on Google Cloud Compute Engine (`GCP`), not consumer Colab:**
   - **H4D (Dedicated HPC, AMD EPYC "Turin" / Zen 5):** **192 dedicated physical cores** (`1 vCPU = 1 physical core`, SMT disabled), 2.7 GHz base / up to 4.1 GHz max, **720 GiB – 1,488 GiB DDR5**, **200 Gbps Cloud RDMA** across nodes (Slurm / Cluster Toolkit). On-demand `h4d-standard-192` in `us-central1`: **`~$7.8538/hr`** (`~$3.82/hr` Spot).
   - **C4D (General-Purpose / High-Perf Compute, AMD EPYC "Turin" / Zen 5):** **2 to 384 vCPUs**, up to **~3 TB DDR5**, up to 4.1 GHz boost. Same Zen 5 core microarchitecture as H4D/9800X3D, without dedicated compute-optimized SKU restrictions.
   - **H3 (`h3-standard-88`, Intel Sapphire Rapids):** **88 dedicated physical cores** (no SMT), 352 GiB DDR5, `~$4.9236/hr` on-demand in `us-central1`.
   - **Workload routing:** Keep 1–16 thread and L3-cache-sensitive tasks on the local **9800X3D** (faster per core and free); route 32–384 thread parallel tasks, $>64$ GB RAM workloads, or multi-node MPI/Slurm runs to **GCP `C4D` / `H4D`**.

---

## 2. Google AI Ultra Cloud Credits: Avoiding the $5 Prepay Trap

Per `developers.google.com/program/plans-and-pricing`, `developers.google.com/profile/help/benefits`, `ai.google.dev/gemini-api/docs/billing`, and `cloud.google.com/skus/exclusions`:

1. **Colab Compute Units vs. Google Developer Program Cloud Credits:**
   - **Colab Compute Units** (e.g., up to 2,000/month on Ultra) cover **only** consumer Colab GPUs/TPUs and preset runtimes — never Compute Engine `H4D`/`C4D`.
   - **Monthly GenAI & Cloud Developer Credits** (via Google Developer Program, bundled with Google One AI tiers):
     - Google AI Pro: **$10 USD/month**
     - Google AI Ultra (20 TB / 5x): **$40 USD/month** (e.g., `$51.32 SGD` converted at claim time)
     - Google AI Ultra (30 TB / 20x): **$100 USD/month**
     - Valid **12 months** per monthly grant; non-retroactive before creating your Developer Program profile.
2. **Do NOT click "Set up billing" inside `aistudio.google.com/billing` for Compute Engine:**
   - Since March 23, 2026, AI Studio defaults new accounts to **Prepay**, requiring a **$5 USD minimum non-refundable credit purchase** upfront — and per Google's docs, *"Prepay credits apply only to Gemini API usage costs; you can't use them to pay for other Google Cloud services."*
3. **The `$0`-Upfront Onboarding Route (Cloud Console + Builders Hub):**
   - **Step A:** Open `console.cloud.google.com/billing`, accept Terms of Service, and complete **Try Google Cloud for free** (`Start free`). Requires contact info + payment card for identity verification (`$0.00–$1.00` temporary authorization hold, `$0` charged, **No automatic charges** protection while in Free Trial), granting the **$300 USD** (`~$384.83 SGD`) 90-day **Welcome credit**.
   - **Step B:** Open `me.developers.google.com/benefits`, click **Join the program → Create Profile**, select your new billing account in the dropdown on the monthly credit card, tick **Always use this billing account**, and click **Apply**.
   - **Verified result in Cloud Billing → Credits:** The monthly credit lands immediately with usage scope **"Following services: all of Google Cloud Platform and Google Maps APIs"** (not Gemini-only!).
4. **Critical Credit Exclusions & Quota Constraints:**
   - **Spot / Preemptible VMs are EXCLUDED (`cloud.google.com/skus/exclusions`):** Using `--provisioning-model=SPOT` bypasses promotional Cloud credits and bills your card directly. Always use **On-Demand** instances when consuming credits.
   - **Select specialized VMs & `H4D` quota `0`:** `cloud.google.com/skus/exclusions` excludes *"certain memory-optimized or compute-optimized VMs"* and Free Trial caps specialized quotas (`H4D` `CPUS_PER_VM_FAMILY` starts at **`0`**). To run 192-core `H4D` or large `C4D`, manually click **Upgrade** in Cloud Billing (`$0` fee; existing credits stay intact and consume before your card) and request a quota increase (`IAM & Admin → Quotas`), preferring General-Purpose **`C4D`** when relying on promotional credits.

---

## 3. Human–Agent Co-Execution Pattern ("Break-Down Teaching" on WSL2 Chrome)

System safety policies strictly prohibit an agent from clicking browser security consent gates (`chrome://inspect/#remote-debugging` toggle, CDP **"Allow"** popups, Google OAuth consent) or filling personal payment/card forms — even when the user grants blanket permission in chat. Rather than stopping at a monolithic refusal ("I cannot do this"), breaking the workflow into atomic agent-prepared steps + single human gate clicks makes the collaboration fast and seamless:

1. **Open `chrome://` URLs in a New Tab (Not a New Window) on WSL2:**
   - **Pitfall:** Passing `chrome://inspect/#remote-debugging` as a CLI argument to `chrome.exe` causes Chromium to strip `chrome://` or launch a separate window.
   - **Pattern:** Use PowerShell (`-NoProfile -NonInteractive </dev/null`) P/Invoke (`SetForegroundWindow` / `ShowWindow`) on the active `chrome` `MainWindowHandle`, send `^t` (Ctrl+T), paste `chrome://inspect/#remote-debugging` via clipboard (`^v`) + `{ENTER}`, verify `MainWindowTitle` switches to `Inspect with Chrome Developer Tools - Google Chrome`, then stop cleanly so the user checks **Allow remote debugging for this browser instance**.
2. **Bridge WSL2 NAT Loopback Isolation via Windows-Native `node.exe` CDP:**
   - **Pitfall:** Windows Chrome binds `127.0.0.1:9222` (recorded in `%LOCALAPPDATA%\Google\Chrome\User Data\DevToolsActivePort`) on the Windows loopback adapter. In WSL2 NAT mode, Linux `127.0.0.1:9222` cannot reach Windows `127.0.0.1:9222`, causing Linux `agent-browser --cdp 9222` daemon startup to fail. Furthermore, each new WebSocket client triggers Chrome's interactive **"Allow"** dialog.
   - **Pattern:** Invoke Windows-native `node.exe` (`/mnt/c/Program Files/nodejs/node.exe`, built-in `WebSocket`) directly from WSL2, read `DevToolsActivePort`, open **one** long-lived WebSocket session (`Target.getTargets` / `Target.attachToTarget` / `Runtime.evaluate`), and batch all tab inspections or Shadow DOM actions inside that single connection so the user only clicks **Allow** once.
3. **Resolve Multi-Profile Accounts (`Local State`) Instead of Assuming `?authuser=`:**
   - **Pitfall:** Chrome separates distinct Google accounts into **Chrome Profiles** (`Default`, `Profile 1`, `Profile 2`, …). Passing `?authuser=email` in another profile's window fails when the target account lives in a different Chrome profile — and another account in `Profile 1` may even be blocked by Google Cloud's mandatory 2SV/MFA enforcement (effective 2026-03-23).
   - **Pattern:** Read `%LOCALAPPDATA%\Google\Chrome\User Data\Local State` (`profile.info_cache`) to map `email -> Profile N`, launch target URLs with `chrome.exe --profile-directory="Profile N"`, reuse that profile's `browserContextId` for any newly created CDP tabs, and wait at payment/ToS forms (`Start free`, `Create Profile`) while walking Shadow DOM (`MAT-SELECT` / `MAT-OPTION` / checkboxes) automatically afterward.

---

## 4. Local Control Installation (`~/sw`)

- **Installed SDK:** `/home/rog/sw/google-cloud-sdk` (`gcloud 594.0.1`, `alpha`, `beta`, `gsutil`, `bq`, bundled Python 3.14 — isolated from Conda, `torch_env`, and ROOT/Geant4 stacks).
- **Wrapper & Env:** `/home/rog/sw/gcp-cpu-ctl.sh` (`~/.local/bin/gcp-cpu-ctl`) and `/home/rog/sw/env-gcloud.sh`.
- **Cross-Project Routing & Skill:** Machine-wide guide at `/home/rog/GCP_CPU_LOCAL_CONTROL.md` + cross-brand skill installed to Claude Code, Codex, Antigravity/Gemini CLI, and `~/.agents/skills` via [`install-gcp-cpu-skill.sh`](install-gcp-cpu-skill.sh).
