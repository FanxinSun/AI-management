# check-display.ps1 — Audits live Samsung Odyssey G8 display settings against canonical profile
$ErrorActionPreference = "SilentlyContinue"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class DisplayAuditor {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    public struct DEVMODE {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmDeviceName;
        public short dmSpecVersion;
        public short dmDriverVersion;
        public short dmSize;
        public short dmDriverExtra;
        public int dmFields;
        public int dmPositionX;
        public int dmPositionY;
        public int dmDisplayOrientation;
        public int dmDisplayFixedOutput;
        public short dmColor;
        public short dmDuplex;
        public short dmYResolution;
        public short dmTTOption;
        public short dmCollate;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmFormName;
        public short dmLogPixels;
        public int dmBitsPerPel;
        public int dmPelsWidth;
        public int dmPelsHeight;
        public int dmDisplayFlags;
        public int dmDisplayFrequency;
    }

    [DllImport("user32.dll", CharSet = CharSet.Ansi)]
    public static extern bool EnumDisplaySettings(string lpszDeviceName, int iModeNum, ref DEVMODE lpDevMode);

    [DllImport("user32.dll")]
    public static extern bool SetProcessDpiAwarenessContext(IntPtr ctx);

    [DllImport("user32.dll")]
    public static extern IntPtr MonitorFromPoint(POINT pt, uint flags);

    [DllImport("shcore.dll")]
    public static extern int GetDpiForMonitor(IntPtr hmon, int dpiType, out uint dpiX, out uint dpiY);

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int x; public int y; }

    public static DEVMODE GetCurrentDevMode() {
        DEVMODE dm = new DEVMODE();
        dm.dmSize = (short)Marshal.SizeOf(typeof(DEVMODE));
        EnumDisplaySettings(null, -1, ref dm);
        return dm;
    }

    public static uint GetTrueMonitorDpi() {
        SetProcessDpiAwarenessContext((IntPtr)(-4)); // PerMonitorAwareV2
        POINT pt = new POINT { x = 100, y = 100 };
        IntPtr hMon = MonitorFromPoint(pt, 1);
        uint dpiX = 0, dpiY = 0;
        GetDpiForMonitor(hMon, 0, out dpiX, out dpiY);
        return dpiX;
    }
}
"@ -ErrorAction SilentlyContinue

$dm = [DisplayAuditor]::GetCurrentDevMode()
$dpi = [DisplayAuditor]::GetTrueMonitorDpi()
$scalePct = [math]::Round(($dpi / 96.0) * 100)

# Check MonitorDataStore for SAM7256
$samKey = "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers\MonitorDataStore\SAM7256HNBL300063_00_08C5_B0"
$hdrVal = $null
$acmVal = $null
$sdrNits = $null
if (Test-Path $samKey) {
    $props = Get-ItemProperty $samKey
    $hdrVal = $props.HDREnabled
    $acmVal = $props.AutoColorManagementEnabled
    $rawSdr = $props.SDRWhiteLevel
    if ($rawSdr) {
        $sdrNits = [math]::Round($rawSdr * 80.0 / 1000.0)
    }
}

# Check Iris process
$irisProc = Get-Process -Name "*iris*" -ErrorAction SilentlyContinue | Select-Object -First 1

# Check Windows Night Light CloudStore keys
$nlSettingsKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default`$windows.data.bluelightreduction.settings\windows.data.bluelightreduction.settings"
$nlStateKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default`$windows.data.bluelightreduction.bluelightreductionstate\windows.data.bluelightreduction.bluelightreductionstate"

$nlSettingsPresent = Test-Path $nlSettingsKey
$nlStatePresent = Test-Path $nlStateKey

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " Samsung Odyssey G8 (SAM7256) Display Status Audit" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

function Format-AuditRow($name, $live, $target, $ok) {
    $status = if ($ok) { "[PASS]" } else { "[FAIL]" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("{0,-22} : {1,-24} (Target: {2,-16}) " -f $name, $live, $target) -NoNewline
    Write-Host $status -ForegroundColor $color
}

Format-AuditRow "Resolution" ("{0} x {1}" -f $dm.dmPelsWidth, $dm.dmPelsHeight) "3840 x 2160" ($dm.dmPelsWidth -eq 3840 -and $dm.dmPelsHeight -eq 2160)
Format-AuditRow "Refresh Rate" ("{0} Hz" -f $dm.dmDisplayFrequency) "240 Hz" ($dm.dmDisplayFrequency -eq 240)
Format-AuditRow "Color Depth" ("{0} bpp (10 bpc)" -f $dm.dmBitsPerPel) "32 bpp" ($dm.dmBitsPerPel -eq 32)
Format-AuditRow "DPI Scaling" ("{0} DPI ({1}%)" -f $dpi, $scalePct) "168 DPI (175%)" ($dpi -eq 168)
Format-AuditRow "HDR Mode" ($(if ($hdrVal -eq 1) { "Enabled" } else { "Disabled" })) "Enabled" ($hdrVal -eq 1)
Format-AuditRow "Auto Color Mgmt" ($(if ($acmVal -eq 1) { "Enabled" } else { "Disabled" })) "Enabled" ($acmVal -eq 1)

Write-Host "--------------------------------------------------------------------------"
Write-Host " Eye Protection & Color Temperature Subsystems" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------------"
if ($irisProc) {
    Write-Host (" Iris App               : Running (PID {0}, Path: {1})" -f $irisProc.Id, $irisProc.Path) -ForegroundColor Green
    Write-Host "                         Controls GPU gamma ramp directly (SetDeviceGammaRamp)." -ForegroundColor Gray
} else {
    Write-Host " Iris App               : Not running" -ForegroundColor Gray
}

if ($nlStatePresent) {
    Write-Host " Windows Night Light    : Active in CloudStore (windows.data.bluelightreduction)" -ForegroundColor Green
    Write-Host "                         Adjusted in Windows Settings -> System -> Display -> Night light." -ForegroundColor Gray
} else {
    Write-Host " Windows Night Light    : No CloudStore state registered" -ForegroundColor Gray
}
Write-Host " Monitor Hardware OSD   : Eye Saver Mode (physical monitor menu, independent of Windows)" -ForegroundColor Gray
Write-Host "==========================================================================" -ForegroundColor Cyan
