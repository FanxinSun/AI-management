# NuPhy Air96 Keyboard Remap & Snipping Bridge (PowerToys + Kernel Scancode)

Automated host configuration and key remapping for the **NuPhy Air96** keyboard on Windows 11 / WSL2.

## Problem & Background

When the NuPhy Air96 (V1, non-QMK/VIA firmware) is adjusted, physically moved, or after a system restart:
1. **Volume requires `Fn`**: The top row enters standard function mode (`F1`–`F12`), forcing volume adjustment (`F10`/`F11`/`F12`) to require holding `Fn`.
2. **Screenshot key fails to open Snipping Tool**:
   - The dedicated screenshot key (between `F12` and `DEL`) sends raw `Print Screen` (`VK_SNAPSHOT` / code `44`), which by default silently captures the full screen to clipboard without opening the Windows 11 Snipping Tool rectangular crop overlay.
   - If the keyboard is in Mac mode or Mac screenshot chords are sent (`Cmd+Shift+4` or `Cmd+Shift+3`), Windows receives `Win+Shift+4` or `Win+Shift+3`, which does nothing on Windows.
3. **The "Reversal" Bug (Windows UIPI Elevation Gap)**:
   - When Windows Terminal (or any app) runs with Administrator privileges (`High Mandatory Level`), standard unelevated PowerToys (`RunLevel: Limited`) is blocked by Windows UIPI (User Interface Privilege Isolation) from intercepting keystrokes or injecting remaps into the elevated window.
   - After a Windows reboot, standard PowerToys startup launched unelevated, causing the keyboard to act as if the settings "reversed" whenever the user was in an elevated terminal.

## Permanent Solution Architecture

The fix uses a two-tier permanent strategy:

### Layer 1: Kernel-Level Scancode Map (`win32k.sys`)
- Written directly to `HKLM\SYSTEM\CurrentControlSet\Control\Keyboard Layout\Scancode Map`.
- Handled at the OS driver level by the Windows kernel:
  - `F10` (`0x0044`) $\rightarrow$ `Volume Mute` (`0xE020`)
  - `F11` (`0x0057`) $\rightarrow$ `Volume Down` (`0xE02E`)
  - `F12` (`0x0058`) $\rightarrow$ `Volume Up` (`0xE030`)
- Immune to UAC elevation boundaries, lock screens, and works even if PowerToys is not running.

### Layer 2: Elevated PowerToys Keyboard Manager & Windows Snipping
- Scheduled Task `\PowerToys\Autorun for ROG` configured with `RunLevel: Highest` (`run_elevated: true` in `settings.json`).
- Automatically starts PowerToys as Administrator on every Windows boot/logon.
- PowerToys interceptor (`WH_KEYBOARD_LL`) runs with High Mandatory Level, allowing it to intercept and inject keystrokes into elevated Windows Terminal without UIPI drops.
- **Mappings (`default.json`)**:
  - `Print Screen` (`44`) $\rightarrow$ `Win + Shift + S` (`91;160;83`)
  - `Win + Shift + 4` (`91;160;52`) $\rightarrow$ `Win + Shift + S` (`91;160;83`)
  - `Win + Shift + 3` (`91;160;51`) $\rightarrow$ `Win + Shift + S` (`91;160;83`)
- **Native Registry Setting**:
  - `HKCU\Control Panel\Keyboard\PrintScreenKeyForSnippingEnabled = 1`

## Apply / Re-apply

Run from WSL:

```bash
~/AI-management/nuphy-air96/apply-nuphy-air96-mappings.sh
```

## Verification

Check elevation and processes:

```powershell
Get-Process -Name "PowerToys.KeyboardManagerEngine"
(Get-ScheduledTask -TaskPath "\PowerToys\" -TaskName "Autorun for ROG").Principal.RunLevel
```

## As first recorded in the WSL agent-control guide (moved here 2026-11-25)

- **Symptom.** After adjusting the NuPhy Air96 keyboard, volume adjustment requires holding `Fn` (`Fn + F11`/`F12`), and the dedicated screenshot key (between `F12` and `DEL`) fails to open the Snipping Tool region selector (it only performs silent full-screen capture or does nothing).
- **Cause.** The NuPhy Air96 (V1, non-QMK) switched into standard function mode (`F1`–`F12`), mapping F10/F11/F12 to standard function keys rather than media volume controls. The screenshot key sends raw `Print Screen` (`VK_SNAPSHOT` / `44`), but Windows 11 defaults to full-screen capture unless `PrintScreenKeyForSnippingEnabled` is set. Furthermore, Mac screenshot chords (`Cmd+Shift+4` / `Win+Shift+4`) have no action in Windows.
- **Fix.** [`nuphy-air96/apply-nuphy-air96-mappings.sh`](apply-nuphy-air96-mappings.sh) applies a permanent OS-level remapping via PowerToys Keyboard Manager (`default.json`):
  1. `F10` (`121`) $\rightarrow$ `Volume Mute` (`173`), `F11` (`122`) $\rightarrow$ `Volume Down` (`174`), `F12` (`123`) $\rightarrow$ `Volume Up` (`175`).
  2. `Print Screen` (`44`), `Win+Shift+4` (`91;160;52`), and `Win+Shift+3` (`91;160;51`) $\rightarrow$ `Win+Shift+S` (`91;160;83`).
  3. Sets `HKCU\Control Panel\Keyboard\PrintScreenKeyForSnippingEnabled = 1` and restarts PowerToys Keyboard Manager.
