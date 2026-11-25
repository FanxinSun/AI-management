# WSL2 Native Win32/GDI+ Clipboard Bridge (`wl-paste`)

Fast native `wl-paste` drop-in for WSL2 that reads Windows clipboard screenshots, copied files, and text directly via Win32/GDI+ in ~80–115 ms.

## Why This Exists

1. On WSL2 with WSLg (`WAYLAND_DISPLAY=wayland-0`), pressing `Ctrl+V` in Windows Terminal with a screenshot on the Windows clipboard sends an empty bracketed paste (`\e[200~\e[201~`).
2. `agy` (`third_party/jetski/cli/model/clipboard_linux.go`) detects `WAYLAND_DISPLAY`, calls `wl-paste --list-types` and `wl-paste --type image/png`, and enforces a **2.0 s timeout** in `ReadClipboardMedia`. Without `wl-paste`, `agy` logs:
   ```text
   Implicit clipboard media probe: result=false err=no supported clipboard tool found (install wl-clipboard to paste images on Wayland)
   ```
3. Cold-starting `powershell.exe` takes ~2.39 s per call (exceeding `agy`'s 2.0 s budget across two calls), and stock WSLg Wayland clipboard bridging does not reliably expose Windows `PNG` or `CF_BITMAP`/`CF_DIB` screenshots.
4. `wl-paste.exe` is compiled natively with MSVC (`/O2 /MT`, `_O_BINARY` stdout, zero .NET startup overhead), completing `--list-types` in ~80 ms and `--type image/png` in ~114 ms. It also accelerates Claude Code's Wayland image paste from ~4.8 s to ~0.2 s.

## Supported Clipboard Formats

- **Raw `PNG` / `image/png`** (from `Win+Shift+S`, browsers, modern apps): trimmed cleanly at the PNG `IEND` chunk.
- **`CF_BITMAP` / `CF_DIB` / `CF_DIBV5`** (from `PrintScreen`, Paint, legacy apps): encoded to PNG in-memory via GDI+.
- **`CF_HDROP`** (files copied in Windows Explorer): mapped to `text/uri-list` (`file:///mnt/<drive>/...` and `//wsl.localhost/<distro>/...` UNC paths).
- **`image/jpeg` (`JFIF`), `image/gif`, `image/webp`**, and **UTF-8 `CF_UNICODETEXT`** (`CRLF` normalized to `LF`).

## Install & Self-Healing

```bash
~/AI-management/fix/wsl-clipboard/install-wsl-clipboard.sh
```

- Installs the self-healing wrapper to `~/.local/bin/wl-paste`.
- Copies `wl-paste.cpp` and `install-wsl-clipboard.sh` into `~/.local/share/wsl-clipboard/`.
- Compiles `C:\Users\<WinUser>\AppData\Local\wsl-clipboard\wl-paste.exe` using Visual Studio `vcvars64.bat` + `cl.exe`.
- If `wl-paste.exe` is ever deleted on the Windows side, `~/.local/bin/wl-paste` automatically rebuilds it on demand before executing.
- Safe on non-WSL hosts (exits `0` with a skip message when `/mnt/c/WINDOWS/System32/cmd.exe` is absent).

## Verify

```bash
which wl-paste
wl-paste --version
time wl-paste --list-types
```

## As first recorded in the WSL agent-control guide (moved here 2026-11-25)

- **Symptom.** Pressing `Ctrl+V` in `agy` with a screenshot on the Windows clipboard does nothing, while `claude` and `codex` paste it normally. `cli.log` records:
  ```text
  Implicit clipboard media probe: result=false err=no supported clipboard tool found (install wl-clipboard to paste images on Wayland)
  ```
- **Cause.** Windows Terminal sends an empty bracketed paste (`\e[200~\e[201~`) on `Ctrl+V` when the clipboard holds an image. `agy` sees WSLg's `WAYLAND_DISPLAY=wayland-0`, probes `wl-paste --list-types` and `wl-paste --type image/png`, and enforces a hard **2.0 s timeout** in `ReadClipboardMedia`. Cold-starting `powershell.exe` takes ~2.39 s per call (exceeding 2.0 s across two calls), and stock WSLg Wayland clipboard bridging does not reliably expose Windows `PNG` or `CF_BITMAP`/`CF_DIB` screenshots.
- **Fix.** [`wsl-clipboard/install-wsl-clipboard.sh`](install-wsl-clipboard.sh) compiles a native Win32/GDI+ clipboard bridge (`wl-paste.exe`, ~80 ms `--list-types`, ~114 ms `--type image/png`) and installs a self-healing wrapper at `~/.local/bin/wl-paste`. It supports lossless raw `PNG`, `CF_BITMAP`/`CF_DIB` via GDI+, `CF_HDROP` (`text/uri-list` `file:///mnt/...`), `JFIF`/`GIF`/`WebP`, and UTF-8 `CF_UNICODETEXT`.
