# set-fan-leds.ps1 — Adjusts ASUS Aura Sync case fan LEDs via ServiceMediator COM interface
param(
    [ValidateRange(0.01, 1.0)]
    [double]$Lightness = 0.10,

    [ValidateRange(0.0, 1.0)]
    [double]$Hue = 0.333333,

    [ValidateRange(0.0, 1.0)]
    [double]$Saturation = 1.0
)

$ErrorActionPreference = "Stop"

$scriptPath = "C:\ProgramData\ASUS\RogAura30\SetV2EngineScript.xml"
if (-not (Test-Path $scriptPath)) {
    Write-Error "SetV2EngineScript.xml not found at $scriptPath"
    exit 1
}

$xml = [System.IO.File]::ReadAllText($scriptPath)

# Format lightness string with 6 decimal places
$lStr = $Lightness.ToString("0.000000", [System.Globalization.CultureInfo]::InvariantCulture)
$hStr = $Hue.ToString("0.000000", [System.Globalization.CultureInfo]::InvariantCulture)
$sStr = $Saturation.ToString("0.000000", [System.Globalization.CultureInfo]::InvariantCulture)

# Replace hue, saturation, lightness in all initColor nodes
$newXml = [System.Text.RegularExpressions.Regex]::Replace($xml, "<hue>[0-9\.]+</hue>", "<hue>$hStr</hue>")
$newXml = [System.Text.RegularExpressions.Regex]::Replace($newXml, "<saturation>[0-9\.]+</saturation>", "<saturation>$sStr</saturation>")
$newXml = [System.Text.RegularExpressions.Regex]::Replace($newXml, "<lightness>[0-9\.]+</lightness>", "<lightness>$lStr</lightness>")

[System.IO.File]::WriteAllText($scriptPath, $newXml, [System.Text.Encoding]::UTF8)

# Apply via COM interface
Add-Type -TypeDefinition @"
using System;
using System.Reflection;
public class AuraFanControl {
    public static void Apply(string xml) {
        Type t = Type.GetTypeFromProgID("AsRogAuraService.ServiceMediator");
        object mediator = Activator.CreateInstance(t);
        t.InvokeMember("SetScript", BindingFlags.SetProperty, null, mediator, new object[] { xml, 0 });
    }
}
"@ -ErrorAction SilentlyContinue

[AuraFanControl]::Apply($newXml)

# Update LastProfile.xml if present
$profilePath = "C:\Program Files (x86)\LightingService\LastProfile.xml"
if (Test-Path $profilePath) {
    try {
        $pXml = [System.IO.File]::ReadAllText($profilePath)
        $pXml = [System.Text.RegularExpressions.Regex]::Replace($pXml, "<lightness>[0-9\.]+</lightness>", "<lightness>$lStr</lightness>")
        $pXml = [System.Text.RegularExpressions.Regex]::Replace($pXml, "<hue>[0-9\.]+</hue>", "<hue>$hStr</hue>")
        [System.IO.File]::WriteAllText($profilePath, $pXml, [System.Text.Encoding]::UTF8)
    } catch {
        Write-Warning "Could not update LastProfile.xml: $_"
    }
}

Write-Output "==> Fan LEDs updated: Hue=$hStr, Saturation=$sStr, Lightness=$lStr"
