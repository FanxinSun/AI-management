# Samsung Odyssey G8 (SAM7256) Display Configuration & Verification

Canonical display profile, registry architecture, independent Volume Shadow Copy (VSS) auditing methodology, and eye protection subsystem documentation for the Samsung Odyssey G8 on Windows 11.

---

## 1. Hardware & Target Specifications

| Parameter | Canonical Value | Windows / Driver Representation | Status |
| :--- | :--- | :--- | :--- |
| **Monitor Model** | Samsung Odyssey G8 (32" 4K OLED) | `SAM7256` / `SAM7256HNBL300063_00_08C5_B0` | Verified |
| **Graphics Adapter** | NVIDIA GeForce RTX 5080 | DisplayPort 1.4 with Display Stream Compression (DSC) | Verified |
| **Resolution & Aspect** | **3840 × 2160** (16:9 Landscape) | `dmPelsWidth=3840`, `dmPelsHeight=2160`, `Rotation=1` | **[PASS]** |
| **Refresh Rate** | **240 Hz** | `dmDisplayFrequency=240`, Pixel Rate = 2376 MHz (`240/1`) | **[PASS]** |
| **Color Depth / Format**| **32 bpp (10 bpc, RGB 4:4:4)** | `PixelFormat=21` (NVIDIA DisplayDatabase), `dmBitsPerPel=32` | **[PASS]** |
| **DPI Scaling** | **175%** (Effective DPI: 168) | `DpiValue=1` in `PerMonitorSettings` | **[PASS]** |
| **High Dynamic Range** | **HDR Enabled** | `HDREnabled=1` in `MonitorDataStore` | **[PASS]** |
| **Auto Color Mgmt** | **ACM Enabled** | `AutoColorManagementEnabled=1` in `MonitorDataStore` | **[PASS]** |
| **SDR White Level** | **240 nits** | Raw `SDRWhiteLevel=3000` (`3000 / 1000 * 80 = 240 nits`) | **[PASS]** |

---

## 2. Replug Incident & Fast Recovery

### Root Cause
When the DisplayPort cable is disconnected and reconnected while Windows is running, Windows PnP and the graphics driver initiate hot-plug link renegotiation. If the monitor panel completes its power/EDID handshake before high-bandwidth DSC link training settles, Windows temporarily falls back to a fail-safe timing (e.g. 60 Hz or native aspect ratio mismatch).

### Recovery Procedure
- **No PC restart required**: Simply power-cycle the monitor (turn the monitor off and back on using its physical button or remote). This triggers a full DisplayPort link renegotiation, allowing the NVIDIA driver to immediately restore 3840×2160 @ 240 Hz DSC operation.
- Run `~/AI-management/samsung-odyssey-g8/check-display.sh` to confirm all parameters show `[PASS]`.

---

## 3. Windows Display Registry Architecture

Display parameters are partitioned across four distinct Windows registry locations:

1. **Monitor Calibration & HDR Data Store**:
   `HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers\MonitorDataStore\SAM7256HNBL300063_00_08C5_B0`
   - Stores `HDREnabled`, `AutoColorManagementEnabled`, `SDRWhiteLevel`, and EDID calibration curves.
2. **NVIDIA Driver Display Database**:
   `HKLM\SYSTEM\CurrentControlSet\Services\nvlddmkm\State\DisplayDatabase\SAM7256HNBL300063_FF_08C5_B0`
   - Stores hardware-specific timings: `ScalingConfig`, `MonitorDataRegistryKey`, `DpDscPpsOverrideDataRegistryKey`, `DPDscCapsDataRegistryKey`, `SmoothScalingData`, and `PixelFormat`.
3. **PnP Device Parameters (EDID)**:
   `HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY\SAM7256\5&1243201c&0&UID4353\Device Parameters`
   - Stores the raw 384-byte monitor EDID binary block (`EDID` value, SHA-256 prefix: `9CFA4639F25AB0A7`).
4. **Per-Monitor Scaling Factors**:
   `HKCU\Control Panel\Desktop\PerMonitorSettings\SAM7256HNBL300063_00_08C5_B0`
   - Stores user DPI scaling override (`DpiValue=1` corresponds to 175% scaling / 168 DPI).

---

## 4. Independent Historical Verification (VSS + `offreg.dll`)

In strict adherence to **Executor Regulation #8** (*"A check must be able to fail: compare against an independent source, never against a copy of itself"*):
- Live registry values were not compared against themselves or in-memory API wrappers.
- The system was compared against an independent **Volume Shadow Copy (VSS)** snapshot taken 12 hours earlier (`\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy5` at `2026-11-23 13:11:47`).
- Offline hives (`\Windows\System32\config\SYSTEM` and `\Users\ROG\NTUSER.DAT`) were parsed directly using Windows `offreg.dll` (Offline Registry API) via C# P/Invoke, ensuring read-only, non-invasive verification without mounting.

### 12-Hour Verification Audit

```text
=== ControlSet001\Enum\DISPLAY\SAM7256\5&1243201c&0&UID4353\Device Parameters ===
  [IDENTICAL] EDID : 13:11=len=384B sha=9CFA4639F25AB0A7 | LIVE=len=384B sha=9CFA4639F25AB0A7

=== ControlSet001\Services\nvlddmkm\State\DisplayDatabase\SAM7256HNBL300063_FF_08C5_B0 ===
  [IDENTICAL] ScalingConfig                     : 13:11=DB0200001000000000010000EE000000 | LIVE=DB0200001000000000010000EE000000
  [IDENTICAL] MonitorDataRegistryKey             : 13:11=DB020000140000000000000000000000F1000000 | LIVE=DB020000140000000000000000000000F1000000
  [IDENTICAL] DpDscPpsOverrideDataRegistryKey   : 13:11=len=144B sha=D075F669950F13F8 | LIVE=len=144B sha=D075F669950F13F8
  [IDENTICAL] DPDscCapsDataRegistryKey          : 13:11=len=32B  sha=5A1A0FCB681DA7CA | LIVE=len=32B  sha=5A1A0FCB681DA7CA
  [IDENTICAL] SmoothScalingMultiplierData       : 13:11=len=280B sha=BF0857D96759C872 | LIVE=len=280B sha=BF0857D96759C872

=== Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreduction.settings ===
  [IDENTICAL] Data (User Schedule & Temp)       : 13:11=len=57B  sha=D993A312AA107DFC | LIVE=len=57B  sha=D993A312AA107DFC
```

---

## 5. Eye Protection & Color Temperature Subsystems

Screen color temperature and blue light filtering are handled by three independent, decoupled layers:

### Layer 1: Windows 11 Native Night Light (`windows.data.bluelightreduction.*`)
- **Location**: Windows Settings $\rightarrow$ System $\rightarrow$ Display $\rightarrow$ Night light (`ms-settings:nightlight`).
- **Registry storage**: Stored in the Windows CloudStore hive (`HKCU\Software\Microsoft\Windows\CurrentVersion\CloudStore\...`).
- **Key differences between `settings` and `bluelightreductionstate`**:
  - `default$windows.data.bluelightreduction.settings`: Stores static user configuration (schedule active, sunset-to-sunrise toggle, target color temperature).
  - `default$windows.data.bluelightreduction.bluelightreductionstate`: Stores dynamic runtime state managed by DWM (Desktop Window Manager). It records whether the filter is actively engaged at this moment and the timestamp of the last transition. It changes automatically as night falls.

### Layer 2: Third-Party Eye Care Application (**Iris**)
- **Process**: `Iris.exe` (installed at `C:\Users\ROG\AppData\Local\Iris\Iris.exe`).
- **Mechanism**: Manipulates the GPU video signal directly via the Win32 Gamma Ramp API (`SetDeviceGammaRamp`).
- **Registry impact**: **None.** Iris does not read, write, or touch Windows `CloudStore` or `bluelightreduction` registry keys.
- **Stacking caution**: If both Windows Night Light and Iris are enabled simultaneously at night, both will adjust color temperature simultaneously, causing an overly warm/orange cast.

### Layer 3: Physical Monitor Hardware OSD
- **Feature**: "Eye Saver Mode" (护眼模式) in the Samsung Odyssey G8 internal firmware menu.
- **Mechanism**: Modifies the monitor's internal scaler output.
- **Registry impact**: **None.** Hardware OSD adjustments are completely decoupled from Windows and generate no OS registry events.

---

## 6. Verification CLI Tools

### Audit Current Display Settings
Run from WSL:
```bash
~/AI-management/samsung-odyssey-g8/check-display.sh
```

Or from Windows PowerShell:
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\ROG\AI-management\samsung-odyssey-g8\check-display.ps1
```
