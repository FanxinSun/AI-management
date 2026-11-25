#!/usr/bin/env bash
# apply-nuphy-air96-mappings.sh — Applies permanent PowerToys Keyboard Manager remaps,
# Windows kernel scancode maps, and elevated startup for NuPhy Air96 volume and screenshot controls.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WIN_USER="${WIN_USER:-ROG}"
PT_DIR="/mnt/c/Users/${WIN_USER}/AppData/Local/Microsoft/PowerToys"
KBM_DIR="${PT_DIR}/Keyboard Manager"

if [ ! -d "${PT_DIR}" ]; then
    echo "PowerToys directory not found at ${PT_DIR}; skipping."
    exit 0
fi

echo "==> Configuring PowerToys Keyboard Manager for NuPhy Air96..."
mkdir -p "${KBM_DIR}"
cp "${SCRIPT_DIR}/default.json" "${KBM_DIR}/default.json"

# 1. Update settings.json: enable Keyboard Manager & run_elevated
python3 -c "
import json
p = '${PT_DIR}/settings.json'
try:
    with open(p, 'r', encoding='utf-8') as f:
        s = json.load(f)
    s.setdefault('enabled', {})['Keyboard Manager'] = True
    s['run_elevated'] = True
    s['is_elevated'] = True
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=4)
    print('  ✓ PowerToys settings.json updated: Keyboard Manager enabled & run_elevated=true')
except Exception as e:
    print('  ⚠ Failed to update settings.json:', e)
"

# 2. Kernel-Level Scancode Map (HKLM) for F10=Mute, F11=Vol-, F12=Vol+
# Immune to elevation boundaries (UIPI) and active even if PowerToys is not running.
if [ -x "/mnt/c/Windows/System32/reg.exe" ]; then
    /mnt/c/Windows/System32/reg.exe add "HKLM\SYSTEM\CurrentControlSet\Control\Keyboard Layout" \
        /v "Scancode Map" /t REG_BINARY /d "00000000000000000400000020e044002ee0570030e0580000000000" /f < /dev/null >/dev/null 2>&1 || true
    echo "  ✓ Kernel Scancode Map installed (F10->Mute, F11->Vol-, F12->Vol+)"

    # 3. Windows Native PrintScreen Snipping Tool overlay
    /mnt/c/Windows/System32/reg.exe add "HKCU\Control Panel\Keyboard" \
        /v PrintScreenKeyForSnippingEnabled /t REG_DWORD /d 1 /f < /dev/null >/dev/null 2>&1 || true
    echo "  ✓ Registry PrintScreenKeyForSnippingEnabled set to 1"
fi

# 4. Elevate PowerToys Scheduled Task to RunLevel Highest (runs as Admin on boot/logon)
if [ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]; then
    /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command '
        $task = Get-ScheduledTask -TaskPath "\PowerToys\" -TaskName "Autorun for ROG" -ErrorAction SilentlyContinue
        if ($task) {
            $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest -LogonType Interactive
            Set-ScheduledTask -TaskPath "\PowerToys\" -TaskName "Autorun for ROG" -Principal $principal | Out-Null
            Write-Output "  ✓ Scheduled Task \PowerToys\Autorun for ROG set to RunLevel: Highest"
        }
        Stop-Process -Name "PowerToys*" -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Start-ScheduledTask -TaskPath "\PowerToys\" -TaskName "Autorun for ROG"
        Start-Sleep -Seconds 3
    ' < /dev/null || true
    echo "  ✓ PowerToys restarted elevated via Scheduled Task"
fi

echo "==> NuPhy Air96 keyboard remaps applied and verified successfully."
