#!/usr/bin/env bash
# set-fan-leds.sh — Wrapper to adjust ASUS Aura box fan LEDs from WSL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIN_PS_SCRIPT="$(wslpath -w "${SCRIPT_DIR}/set-fan-leds.ps1")"

LIGHTNESS="${1:-0.10}" # Default 0.10 (dimmer, soft ambient glow)
HUE="${2:-0.333333}"   # Default Green (0.333333)
SAT="${3:-1.0}"        # Default Full Saturation

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
    & '${WIN_PS_SCRIPT}' -Lightness ${LIGHTNESS} -Hue ${HUE} -Saturation ${SAT}
" < /dev/null
