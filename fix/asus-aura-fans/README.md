# ASUS Aura Sync Box Fan LEDs Control

Control and adjust brightness / color for the 4 chassis box fans on the ASUS ROG / Prime B650M-A AX6 II system.

## Hardware & Architecture

- **Motherboard**: `ASUSTeK COMPUTER INC. PRIME B650M-A AX6 II`
- **Lighting Zones / Devices (4 total)**:
  1. `Mainboard_Master` (Motherboard lighting)
  2. `AddressableStrip` index 0 (`ARGB HEADER`)
  3. `AddressableStrip` index 1 (`ARGB HEADER`)
  4. `AddressableStrip` index 2 (`ARGB HEADER`)
- **System Service**: `LightingService` (`C:\Program Files (x86)\LightingService\LightingService.exe`)
- **Automation Interface**: `AsRogAuraService.ServiceMediator` (COM automation server, CLSID `{95775DC4-77AA-4E94-8CF6-68267EEF1856}`)
- **Configuration Profiles**:
  - `C:\ProgramData\ASUS\RogAura30\SetV2EngineScript.xml`
  - `C:\Program Files (x86)\LightingService\script\LastScript.xml`
  - `C:\Program Files (x86)\LightingService\LastProfile.xml`
  - `C:\ProgramData\ASUS\RogAura30\AuraSync.ini`

## Color & Brightness Model

The system uses HSL (Hue, Saturation, Lightness):
- **Hue**:
  - `0.000000` = Red
  - `0.333333` = Green
  - `0.666667` = Blue
- **Lightness (Brightness)**:
  - `0.500000` = Pure 100% Brightness (Vibrant, factory max)
  - `0.250000` = 50% Intensity
  - `0.150000` = ~30% Intensity (Ambient glow)
  - `0.100000` = ~20% Intensity (Dimmer soft ambient glow, current default)
  - `0.050000` = ~10% Intensity (Ultra-low night glow)

## Usage

From WSL:

```bash
# Set dim green (20% brightness, current default)
~/AI-management/asus-aura-fans/set-fan-leds.sh 0.10

# Set very soft night green (10% brightness)
~/AI-management/asus-aura-fans/set-fan-leds.sh 0.05

# Revert to full brightness green (100% brightness)
~/AI-management/asus-aura-fans/set-fan-leds.sh 0.50
```

From Windows PowerShell (Admin):

```powershell
.\set-fan-leds.ps1 -Lightness 0.10 -Hue 0.333333
```
