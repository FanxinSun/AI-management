# Muse CLI Local WSL2 Connection Guide

This guide documents how to install, authenticate, and drive a personal **[muse.ai](https://muse.ai/)** agent from a **WSL2 (Ubuntu)** terminal using `muse-cli` — including a **100% background, zero-interruption** cookie sync method from Windows Chrome.

> **Disambiguation:**
> - `muse-cli` (PyPI) = third-party CLI for your personal **muse.ai** agent.
> - `muse` = Meta's official **Muse Code** coding agent (`dev.meta.ai`), a different tool. Always invoke `muse-cli`.

---

## 1. Installation on WSL2

Because `uv` can hit a resolver stack overflow on deep dependency trees (`thread 'uv-resolver' has overflowed its stack`), install `muse-cli` using either `RUST_MIN_STACK=67108864` or an isolated Python venv:

### Option A: `uv` with increased stack size
```bash
RUST_MIN_STACK=67108864 uv tool install --upgrade muse-cli
```

### Option B: Isolated venv (recommended on Debian/Ubuntu externally-managed Python)
```bash
python3 -m venv ~/.local/share/muse-cli-venv
~/.local/share/muse-cli-venv/bin/pip install --upgrade pip muse-cli
ln -sf ~/.local/share/muse-cli-venv/bin/muse-cli ~/.local/bin/muse-cli
```

### Install the agent skill
```bash
mkdir -p ~/.agents/skills/muse-cli
curl -fsSL https://raw.githubusercontent.com/nikships/muse-cli/main/skills/muse-cli/SKILL.md -o ~/.agents/skills/muse-cli/SKILL.md
```

Verify installation:
```bash
command -v muse-cli && muse-cli --help >/dev/null && echo cli-ok
```

---

## 2. Authentication on WSL2 (Zero-Interruption Background Sync)

### Why standard export paths are awkward on WSL2
1. **Locked/Encrypted SQLite DB:** Windows Chrome v130+ locks `User Data\Default\Network\Cookies` while open and encrypts values with App-Bound Encryption (`v20`).
2. **Remote Debugging Friction:** `muse-cli auth export --browser agent-browser` requires manually enabling `chrome://inspect/#remote-debugging`, keeping `https://muse.ai/` as the active foreground tab, and clicking an interactive Allow dialog.

### Background Windows Chrome `NetworkService` Memory Sync
While you are logged into `https://muse.ai/` in Windows Chrome (even minimized or in the background), Chrome's `NetworkService` utility process (`chrome.exe --type=utility --utility-sub-type=network.mojom.NetworkService`) holds the plaintext `Cookie` header containing `hatch_sess=` in committed private memory.

The bundled helper script [`sync_muse_cookies_wsl.sh`](sync_muse_cookies_wsl.sh) reads that cookie header silently via background PowerShell (`-NoProfile </dev/null` + Win32 `VirtualQueryEx` / `ReadProcessMemory`) with **zero window focus changes, zero UI Automation, and zero clipboard writes**, saves it to `~/.config/muse-cli/cookies.txt` (`chmod 600`), and verifies with `muse-cli status`:

```bash
~/AI-management/general/guides/muse-cli-wsl/sync_muse_cookies_wsl.sh
```

> **Note:** If you prefer manual export, open Chrome DevTools (`F12`) $\to$ **Application** $\to$ **Cookies** $\to$ `https://muse.ai`, copy `hatch_sess=...` (and companion cookies separated by `; `) into `~/.config/muse-cli/cookies.txt`, and run `chmod 600 ~/.config/muse-cli/cookies.txt`.

---

## 3. Token Lifecycle & Browser Independence

Once `~/.config/muse-cli/cookies.txt` (`0600`) is saved:
- **You do NOT need to keep the Chrome tab or Chrome open.** `muse-cli` communicates directly with the `muse.ai` gateway.
- Short-lived access/gateway tokens are cached automatically in `~/.config/muse-cli/tokens.json` (`0600`, ~15 minutes) and refreshed transparently using `cookies.txt`.
- Only re-run `sync_muse_cookies_wsl.sh` when `hatch_sess` itself eventually expires (reported as an `auth error`).

---

## 4. Everyday Commands & Agent Usage

```bash
# Interactive chat (humans only — agents must NEVER run bare `muse-cli`, `chat`, or `tui`)
muse-cli chat

# Non-interactive JSON commands (safe for agents & scripts)
muse-cli status
muse-cli threads
muse-cli history --limit 5
muse-cli history --thread <session-id> --limit 5
muse-cli send "message" --wait 120
muse-cli send "message" --thread <session-id> --wait 0
muse-cli watch --timeout 60
muse-cli tasks
muse-cli files --limit 20
muse-cli download <seq|message-id|sandbox://...> -o DIR
```

### WSL2 Pitfalls
1. **`powershell.exe` STDIN hang:** Always pass `</dev/null` when invoking `powershell.exe` from non-interactive WSL shells (already handled inside `sync_muse_cookies_wsl.sh`).
2. **Transient DNS timeouts on WSL2:** `curl_cffi` can occasionally hit `Could not resolve host: muse.ai (Timeout while contacting DNS servers)` after idle periods; simply retry the command once.
3. **Agent safety:** Running `muse-cli` with no subcommand, `muse-cli chat`, or `muse-cli tui` opens an interactive full-screen TUI that blocks the terminal. Agents should always pass an explicit subcommand (`status`, `threads`, `history`, `send`, etc.).
