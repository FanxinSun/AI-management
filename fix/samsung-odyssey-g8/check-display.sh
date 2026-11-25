#!/usr/bin/env bash
# check-display.sh — Run Samsung Odyssey G8 display setting audit from WSL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIN_PS_SCRIPT="$(wslpath -w "${SCRIPT_DIR}/check-display.ps1")"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "${WIN_PS_SCRIPT}" < /dev/null
