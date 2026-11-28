# Colab local control guide (Colab CLI, for agents)

Run code on a Google Colab GPU VM (account has Colab Ultra) but drive/debug everything from this WSL terminal.
Verified working: Tesla T4 / L4 / A100 / H100, torch 2.11+cu130, CUDA OK, Drive mount OK.
For heavy parallel CPU / high-RAM workloads (32–384 vCPUs, up to 3 TB DDR5), use GCP Compute Engine (`C4D` / `H4D`) via `/home/rog/GCP_CPU_LOCAL_CONTROL.md`.

## Setup (already done)
- Tool: `google-colab-cli` v0.8.0, installed via `uv tool install google-colab-cli` -> `~/.local/bin/colab`
- **Always** first: `export PATH=$HOME/.local/bin:$PATH`
- Linux/macOS only. Needs Python 3.12+ (uv manages its own env; do not pip install into `torch_env`, py3.11).
- Upgraded to 0.8.0 on 2026-11-26 (requires `RUST_MIN_STACK=67108864 uv tool upgrade google-colab-cli` to avoid uv-resolver stack overflow with deep dependency trees). Note: `colab version` reports the version; silence update banner with `"enable_update_check": false` in `~/.config/colab-cli/settings.json` if needed.
- State/logs: `~/.config/colab-cli/` (token.json, sessions.json, history/, colab.log).

## Google Drive CLI (`gdrive`)
- Pre-installed at `/home/rog/.local/bin/gdrive` (v3.9.1, Rust-based).
- Direct local sync/upload/download with Google Drive alongside Colab's VM `colab drivemount /content/drive`.
- Initial authentication: run `gdrive account add` (prints OAuth URL for human browser approval).
- Useful commands:
  - `gdrive account list`
  - `gdrive files list`
  - `gdrive files upload <local_path>`
  - `gdrive files download <file_id>`

## Authentication (needs the human)
- Login token expires (`invalid_grant`). On expiry, `colab new` prints a Google OAuth URL; the USER must open it in a
  browser, approve, and paste back the authorization code. Feed it to the waiting process (e.g. manage_task send_input
  with trailing newline). Agents cannot do this step alone.
- Drive: `colab drivemount /content/drive` prints a second URL; user approves in browser, then send an empty Enter to
  the waiting process. (When piping through `tail`, output is hidden until exit; read the task log instead.)
- Never paste/log tokens or the `colab-runtime-proxy-token` URLs shared outside the session.

## Lifecycle
```bash
colab new [-s NAME] [--gpu T4|L4|G4|A100|H100] [--tpu v5e1|v6e1]   # provision (CPU if no flag)
colab sessions | colab status                                        # inspect
colab stop [-s NAME]                                                 # RELEASE VM (consumes compute units while running!)
```
With a single active session `-s` can be omitted.

## Running code
```bash
echo 'print(1)' | colab exec                 # stdin
colab exec -f script.py [--timeout 3600]     # default timeout only 30s -> raise it for real jobs
colab exec -f notebook.ipynb                 # notebooks supported per README (not tested here)
colab repl | colab console                   # interactive python / raw shell
colab install pkg1 pkg2 | -r requirements.txt   # uv-based; retry if "Connection was lost"
colab run script.py                          # one-shot: fresh VM, run, fetch outputs, auto-teardown
colab restart-kernel
colab log                                    # export history to ipynb/md/jsonl
```
VM sessions are ephemeral: packages installed with `colab install` are lost after `colab stop`; reinstall per session
(torch is preinstalled on the VM; a GPU VM had torch 2.11+cu130).

## Files
```bash
colab ls [path]                       # relative to /content
colab upload LOCAL REMOTE             # REMOTE is relative to /content (NOT '/content/x' -> 400 error)
colab download REMOTE [LOCAL]
colab rm REMOTE
```
- **Large files fail**: a single 461 MB upload returned HTTP 400; a small file worked. Workarounds: `split -b 40M` + upload
  chunks + `cat` on VM (untested end to end), or better put data on Google Drive and `colab drivemount`, then read
  `/content/drive/MyDrive/...`.

## Gotchas
- Interactive widget notebooks (ipywidgets / Plotly FigureWidget, etc.) do NOT work via `colab exec` (no front end).
  Run those locally (e.g. VS Code Jupyter) instead.
- Always `colab stop` when done; sessions bill compute units. Keep-alive daemon prevents idle shutdown otherwise.
- The VM cannot see local files: upload them (small) or use Drive (large). Results must be downloaded or written to Drive.

## Applies to any project on this machine
This guide is project-agnostic. Typical flow for any script/notebook:
1. `colab new --gpu L4` (user does OAuth if prompted) -> 2. `colab install <deps>` -> 3. upload/mount data ->
4. `colab exec -f job.py --timeout N` -> 5. `colab download` results -> 6. `colab stop`.
