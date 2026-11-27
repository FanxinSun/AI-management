# Poe.com CLI Local WSL2 Connection Guide

This guide documents how to drive **[Poe.com](https://poe.com/)** bots and models from a **WSL2 (Ubuntu)** terminal using `poe-cli` — with points-billed execution on `sunfxcatl@gmail.com` (@fanxinsun) and **100% background, zero-interruption** cookie and API token synchronization from Windows Chrome.

---

## 1. Installation on WSL2

The CLI is located at `/home/rog/sw/poe-cli/poe_cli.py` and globally available in `$PATH`:
```bash
ln -sf /home/rog/sw/poe-cli/poe_cli.py ~/.local/bin/poe-cli
chmod +x ~/.local/bin/poe-cli
```

Verify installation:
```bash
command -v poe-cli && poe-cli --help
```

---

## 2. Authentication & Zero-Interruption Background Sync

Poe supports two complementary authentication layers:
1. **Official OpenAI-Compatible API (`https://api.poe.com/v1`):** Uses an authorized API key (`sk-poe-...`) tied to your points balance.
2. **Browser Session (`p-b` cookie):** Used to check live subscription points, view active API keys, and query web services.

### Background Sync from Windows Chrome
While you are logged into `https://poe.com/` in Windows Chrome (even minimized or in the background):
```bash
~/AI-management/general/guides/poe-cli-wsl/sync_poe_cookies_wsl.sh
```
This script reads the session cookie header silently via background PowerShell (`-NoProfile </dev/null` + Win32 memory scan) with **zero window focus changes, zero UI automation, and zero clipboard writes**, saves it to `~/.config/poe-cli/cookies.txt` (`chmod 600`), and verifies live points and keys against `https://poe.com/api/keys`.

---

## 3. Everyday Commands

```bash
# Check connection, live points balance, and API key
poe-cli status

# Output status as raw JSON (ideal for scripts and agent tools)
poe-cli status --json

# List available models and pricing per 1M tokens
poe-cli models --limit 20
poe-cli models --search claude
poe-cli models --cheapest --limit 10

# Chat with the default cheapest model (assistant — free / standard points)
poe-cli chat "Explain quantum entanglement in 10 words."

# Stream response in real time
poe-cli chat "Write a short haiku about compilers." --stream

# Query specific models (e.g., Claude-Fable-5.1, claude-haiku-4.5, gemini-3.8-flash)
poe-cli chat "Check status" --model claude-haiku-4.5 --usage
```

---

## 4. Environment Variables

- `POE_API_KEY`: Overrides the default API key configured in `~/.config/poe-cli/config.json`.
- `POE_API_BASE`: Overrides the default API gateway (default: `https://api.poe.com/v1`).
