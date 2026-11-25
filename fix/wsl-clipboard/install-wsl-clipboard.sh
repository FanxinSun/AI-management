#!/usr/bin/env bash
# Idempotent, self-healing installer for the WSL2 native Win32/GDI+ wl-paste bridge.
# Installs ~/.local/bin/wl-paste, ~/.local/share/wsl-clipboard/{wl-paste.cpp,install-wsl-clipboard.sh},
# and compiles C:\Users\<WinUser>\AppData\Local\wsl-clipboard\wl-paste.exe when needed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QUIET=0
DRY_RUN=0
FORCE=0

usage() {
    cat <<'EOF'
Usage: install-wsl-clipboard.sh [--quiet] [--dry-run] [--force]

Installs the native Win32/GDI+ wl-paste clipboard bridge on WSL2 so agy, claude,
and codex can paste Windows screenshots (Ctrl+V) and copied files in ~80-115ms.
On non-WSL hosts, prints a skip message and exits 0.
EOF
}

while (($#)); do
    case "$1" in
        --quiet) QUIET=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --force) FORCE=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 1 ;;
    esac
done

log() {
    if (( ! QUIET )); then
        printf '%s\n' "$*"
    fi
}

CMD_EXE="/mnt/c/WINDOWS/System32/cmd.exe"
if [[ ! -x "$CMD_EXE" ]]; then
    log "skipping wsl-clipboard (not WSL)"
    exit 0
fi

WIN_USER="$( (cd /mnt/c && "$CMD_EXE" /d /c "echo %USERNAME%" </dev/null 2>/dev/null) | tr -d '\r\n' || true)"
if [[ -z "$WIN_USER" || "$WIN_USER" == "%USERNAME%" ]]; then
    WIN_USER="ROG"
fi

SRC_CPP="$SCRIPT_DIR/wl-paste.cpp"
SRC_WRAPPER="$SCRIPT_DIR/wl-paste"
SRC_INSTALLER="$SCRIPT_DIR/install-wsl-clipboard.sh"

SHARE_DIR="$HOME/.local/share/wsl-clipboard"
BIN_DIR="$HOME/.local/bin"
WIN_OUT_DIR_WSL="/mnt/c/Users/${WIN_USER}/AppData/Local/wsl-clipboard"
WIN_OUT_DIR_WIN="C:\\Users\\${WIN_USER}\\AppData\\Local\\wsl-clipboard"
WIN_EXE_WSL="${WIN_OUT_DIR_WSL}/wl-paste.exe"

[[ -f "$SRC_CPP" ]] || { echo "missing $SRC_CPP" >&2; exit 1; }

find_vcvars() {
    local pattern
    for pattern in \
        "/mnt/c/Program Files/Microsoft Visual Studio"/*/*/VC/Auxiliary/Build/vcvars64.bat \
        "/mnt/c/Program Files (x86)/Microsoft Visual Studio"/*/*/VC/Auxiliary/Build/vcvars64.bat; do
        if [[ -f "$pattern" ]]; then
            printf '%s\n' "$pattern"
            return 0
        fi
    done
    return 1
}

if (( DRY_RUN )); then
    log "[dry-run] Windows user: $WIN_USER"
    log "[dry-run] install $SHARE_DIR/{wl-paste.cpp,install-wsl-clipboard.sh}"
    log "[dry-run] ensure $WIN_EXE_WSL"
    log "[dry-run] install $BIN_DIR/wl-paste"
    exit 0
fi

mkdir -p "$SHARE_DIR" "$BIN_DIR" "$WIN_OUT_DIR_WSL"

if [[ "$(readlink -f "$SRC_CPP")" != "$(readlink -f "$SHARE_DIR/wl-paste.cpp" 2>/dev/null || true)" ]] && ! cmp -s "$SRC_CPP" "$SHARE_DIR/wl-paste.cpp" 2>/dev/null; then
    install -m 0644 "$SRC_CPP" "$SHARE_DIR/wl-paste.cpp"
fi
if [[ "$(readlink -f "$SRC_INSTALLER")" != "$(readlink -f "$SHARE_DIR/install-wsl-clipboard.sh" 2>/dev/null || true)" ]] && ! cmp -s "$SRC_INSTALLER" "$SHARE_DIR/install-wsl-clipboard.sh" 2>/dev/null; then
    install -m 0755 "$SRC_INSTALLER" "$SHARE_DIR/install-wsl-clipboard.sh"
fi

NEEDS_BUILD=0
if (( FORCE )) || [[ ! -x "$WIN_EXE_WSL" ]] || [[ "$SHARE_DIR/wl-paste.cpp" -nt "$WIN_EXE_WSL" ]]; then
    NEEDS_BUILD=1
fi

if (( NEEDS_BUILD )); then
    VCVARS_WSL="$(find_vcvars || true)"
    if [[ -z "$VCVARS_WSL" ]]; then
        echo "wsl-clipboard: could not find Visual Studio vcvars64.bat" >&2
        exit 1
    fi
    VCVARS_WIN="$(wslpath -w "$VCVARS_WSL")"
    cp "$SHARE_DIR/wl-paste.cpp" "$WIN_OUT_DIR_WSL/wl-paste.cpp"
    cat > "$WIN_OUT_DIR_WSL/_compile.bat" <<BAT
@echo off
call "$VCVARS_WIN" >nul
if errorlevel 1 exit /b 1
cd /d "$WIN_OUT_DIR_WIN"
cl.exe /nologo /O2 /EHsc /MT wl-paste.cpp /Fe:wl-paste.exe
set RC=%ERRORLEVEL%
del /q wl-paste.obj wl-paste.cpp >nul 2>&1
exit /b %RC%
BAT
    (cd /mnt/c && "$CMD_EXE" /d /c "${WIN_OUT_DIR_WIN}\\_compile.bat" </dev/null)
    rm -f "$WIN_OUT_DIR_WSL/_compile.bat"
    log "built $WIN_EXE_WSL"
fi

if [[ -f "$BIN_DIR/wl-paste" ]] && ! grep -q "wsl-winclip\|Fast native Win32 clipboard bridge" "$BIN_DIR/wl-paste" 2>/dev/null; then
    cp -p "$BIN_DIR/wl-paste" "$BIN_DIR/wl-paste.bak-wsl-clipboard"
    log "backed up existing $BIN_DIR/wl-paste to $BIN_DIR/wl-paste.bak-wsl-clipboard"
fi

if [[ -f "$SRC_WRAPPER" ]]; then
    sed "s|/mnt/c/Users/ROG/AppData/Local/wsl-clipboard/wl-paste.exe|$WIN_EXE_WSL|g" "$SRC_WRAPPER" > "$BIN_DIR/wl-paste.tmp"
    install -m 0755 "$BIN_DIR/wl-paste.tmp" "$BIN_DIR/wl-paste"
    rm -f "$BIN_DIR/wl-paste.tmp"
else
    cat > "$BIN_DIR/wl-paste" <<EOF
#!/bin/sh
# Fast native Win32 clipboard bridge for Wayland/WSL2 CLI tools (agy, claude, codex).
# Self-heals via ~/.local/share/wsl-clipboard/install-wsl-clipboard.sh if wl-paste.exe is missing.
export WSLENV="\${WSLENV:+\${WSLENV}:}WSL_DISTRO_NAME"
WINCLIP_EXE="\${WSL_WINCLIP_EXE:-$WIN_EXE_WSL}"
if [ ! -x "\$WINCLIP_EXE" ] && [ -x "\$HOME/.local/share/wsl-clipboard/install-wsl-clipboard.sh" ]; then
    "\$HOME/.local/share/wsl-clipboard/install-wsl-clipboard.sh" --quiet >/dev/null 2>&1 || true
fi
exec "\$WINCLIP_EXE" "\$@" </dev/null
EOF
    chmod 0755 "$BIN_DIR/wl-paste"
fi

for rc in "$HOME/.bashrc" "$HOME/.profile"; do
    if [[ -f "$rc" ]] && ! grep -q '\.local/bin' "$rc"; then
        printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
        log "added ~/.local/bin to PATH in $rc"
    fi
done

log "installed wsl-clipboard: $BIN_DIR/wl-paste -> $WIN_EXE_WSL"
