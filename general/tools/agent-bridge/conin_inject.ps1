# Types text into (or reads) the console this process is attached to (WriteConsoleInput / ReadConsoleOutputCharacter).
# Launched by send_to_tty.sh through the TARGET session's WSL interop socket
# (WSL_INTEROP=/run/WSL/<relay>_interop), which makes this process a child of
# that tab's wsl.exe. It detaches from its own private console and attaches to
# its parent's console (the target Windows Terminal tab) before interacting.
# Text arrives base64(UTF-8) in $env:BRIDGE_B64; "\r" is sent as an Enter key.
# BRIDGE_SUBMIT=1 (Claude Code / Codex targets): afterwards send lone Enters and
# (for Claude targets when screen buffer is readable) verify submission.
# Pre-send guard: inspects CONOUT$ screen tail so an open TUI dialog/picker
# (AskUserQuestion, permission prompt, trust dialog) is never answered by Enter.
# Set BRIDGE_FORCE_SEND=1 to bypass screen checks; BRIDGE_READ_ONLY=1 to dump screen.
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class ConIn {
  [StructLayout(LayoutKind.Explicit, CharSet=CharSet.Unicode)]
  public struct KEY_EVENT_RECORD {
    [FieldOffset(0)] public int bKeyDown;
    [FieldOffset(4)] public short wRepeatCount;
    [FieldOffset(6)] public short wVirtualKeyCode;
    [FieldOffset(8)] public short wVirtualScanCode;
    [FieldOffset(10)] public char UnicodeChar;
    [FieldOffset(12)] public int dwControlKeyState;
  }
  [StructLayout(LayoutKind.Explicit)]
  public struct INPUT_RECORD {
    [FieldOffset(0)] public short EventType;
    [FieldOffset(4)] public KEY_EVENT_RECORD KeyEvent;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct COORD { public short X; public short Y; }
  [StructLayout(LayoutKind.Sequential)]
  public struct SMALL_RECT { public short Left; public short Top; public short Right; public short Bottom; }
  [StructLayout(LayoutKind.Sequential)]
  public struct CONSOLE_SCREEN_BUFFER_INFO {
    public COORD dwSize;
    public COORD dwCursorPosition;
    public short wAttributes;
    public SMALL_RECT srWindow;
    public COORD dwMaximumWindowSize;
  }

  [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
  static extern IntPtr CreateFileW(string n, uint a, uint s, IntPtr sa, uint c, uint f, IntPtr t);
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")]
  static extern bool FreeConsole();
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool AttachConsole(uint pid);
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool WriteConsoleInputW(IntPtr h, INPUT_RECORD[] r, uint n, out uint w);
  [DllImport("kernel32.dll", SetLastError=true)]
  static extern bool GetConsoleScreenBufferInfo(IntPtr h, out CONSOLE_SCREEN_BUFFER_INFO info);
  [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
  static extern bool ReadConsoleOutputCharacterW(IntPtr h, StringBuilder sb, uint len, COORD pos, out uint read);

  public static void Attach(uint pid) {
    FreeConsole();
    if (!AttachConsole(pid))
      throw new Exception("AttachConsole(" + pid + ") failed: " + Marshal.GetLastWin32Error());
  }

  public static void Send(string text) {
    IntPtr h = CreateFileW("CONIN$", 0xC0000000u, 3u, IntPtr.Zero, 3u, 0u, IntPtr.Zero);
    if (h == new IntPtr(-1))
      throw new Exception("CONIN$ open failed: " + Marshal.GetLastWin32Error());
    try {
      var recs = new INPUT_RECORD[text.Length * 2];
      for (int i = 0; i < text.Length; i++) {
        char c = text[i];
        short vk = (short)(c == '\r' ? 0x0D : 0);
        for (int d = 0; d < 2; d++) {
          var r = new INPUT_RECORD();
          r.EventType = 1;
          r.KeyEvent.bKeyDown = d == 0 ? 1 : 0;
          r.KeyEvent.wRepeatCount = 1;
          r.KeyEvent.wVirtualKeyCode = vk;
          r.KeyEvent.UnicodeChar = c;
          recs[i * 2 + d] = r;
        }
      }
      uint w;
      if (!WriteConsoleInputW(h, recs, (uint)recs.Length, out w))
        throw new Exception("WriteConsoleInput failed: " + Marshal.GetLastWin32Error());
      if (w != (uint)recs.Length)
        throw new Exception("WriteConsoleInput short write: " + w + "/" + recs.Length);
    } finally {
      CloseHandle(h);
    }
  }

  public static string ReadScreen() {
    IntPtr h = CreateFileW("CONOUT$", 0x80000000u, 3u, IntPtr.Zero, 3u, 0u, IntPtr.Zero);
    if (h == new IntPtr(-1)) return "";
    try {
      CONSOLE_SCREEN_BUFFER_INFO info;
      if (!GetConsoleScreenBufferInfo(h, out info) || info.dwSize.X <= 0) return "";
      int width = info.dwSize.X;
      int top = Math.Max(0, (int)info.srWindow.Top);
      int bot = Math.Max(top, (int)info.srWindow.Bottom);
      var rows = new List<string>(bot - top + 1);
      for (int y = top; y <= bot; y++) {
        var sb = new StringBuilder(width);
        var pos = new COORD();
        pos.X = 0;
        pos.Y = (short)y;
        uint r;
        if (!ReadConsoleOutputCharacterW(h, sb, (uint)width, pos, out r)) break;
        rows.Add(sb.ToString().TrimEnd());
      }
      return string.Join("\n", rows);
    } finally {
      CloseHandle(h);
    }
  }
}
'@

function Get-CharCount([string]$s, [char]$ch) {
  $cnt = 0
  foreach ($c in $s.ToCharArray()) {
    if ($c -eq $ch) { $cnt++ }
  }
  return $cnt
}

function Get-ScreenState([string]$scr, [bool]$isClaude) {
  if ([string]::IsNullOrWhiteSpace($scr)) { return 'unavailable' }
  $lines = @($scr -split "`n")
  $nonEmpty = @($lines | Where-Object { $_.Trim().Length -gt 0 })
  if ($nonEmpty.Count -eq 0) { return 'unavailable' }

  $tailStart = [Math]::Max(0, $nonEmpty.Count - 4)
  $footer = ($nonEmpty[$tailStart..($nonEmpty.Count - 1)] -join "`n")
  if ($footer -match 'Enter to select|Enter to confirm|Esc to cancel|to navigate|Tab to amend|Do you trust the contents of this') {
    return 'dialog'
  }
  if (-not $isClaude) { return 'ready' }

  $barChar = [char]0x2594  # ▔
  for ($i = 0; $i -lt ($lines.Count - 1); $i++) {
    if ((Get-CharCount $lines[$i] $barChar) -ge 20) {
      $hdr = $lines[$i + 1]
      if ($hdr -match 'Settings' -and $hdr -match 'Status' -and $hdr -match 'Config' -and $hdr -match 'Usage' -and $hdr -match 'Stats') {
        return 'settings'
      }
    }
  }

  $ruleChar = [char]0x2500  # ─
  $ruleIdx = @()
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ((Get-CharCount $lines[$i] $ruleChar) -ge 20) {
      $ruleIdx += $i
    }
  }
  if ($ruleIdx.Count -lt 2) { return 'unknown' }

  $s = $ruleIdx[$ruleIdx.Count - 2] + 1
  $e = $ruleIdx[$ruleIdx.Count - 1] - 1
  $box = if ($e -ge $s) { ($lines[$s..$e] -join "`n") } else { '' }
  $box = $box.Replace([char]0x00A0, ' ').TrimStart()
  if ($box.Length -gt 0 -and $box[0] -eq [char]0x276F) {
    $box = $box.Substring(1)
  }
  if ($box.Trim().Length -gt 0) { return 'text' }
  return 'empty'
}

$parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
if ((Get-Process -Id $parent).ProcessName -ne 'wsl') { throw "parent $parent is not wsl.exe" }
[ConIn]::Attach([uint32]$parent)

if ($env:BRIDGE_READ_ONLY -eq '1') {
  Write-Output ([ConIn]::ReadScreen())
  exit 0
}

$isClaude = ($env:BRIDGE_IS_CLAUDE -eq '1')
$forceSend = ($env:BRIDGE_FORCE_SEND -eq '1')
$noAutoEsc = ($env:BRIDGE_NO_AUTO_ESC -eq '1')
$poll = if ($env:BRIDGE_PROMPT_POLL_SECS) { [int]$env:BRIDGE_PROMPT_POLL_SECS } else { 5 }
$waitMax = if ($env:BRIDGE_PROMPT_WAIT_SECS) { [int]$env:BRIDGE_PROMPT_WAIT_SECS } else { 60 }
$panelNote = ''
$st = 'unavailable'

if (-not $forceSend) {
  $st = Get-ScreenState ([ConIn]::ReadScreen()) $isClaude
  if ($isClaude -and $st -eq 'settings' -and -not $noAutoEsc) {
    $st = Get-ScreenState ([ConIn]::ReadScreen()) $isClaude
    if ($st -eq 'settings') {
      [ConIn]::Send("$([char]27)$([char]27)")
      Start-Sleep -Milliseconds 1500
      $st = Get-ScreenState ([ConIn]::ReadScreen()) $isClaude
      if ($st -eq 'empty' -or $st -eq 'text') { $panelNote = '_closed_panel' }
    }
  }
  $elapsed = 0
  while (($st -eq 'dialog' -or $st -eq 'unknown' -or $st -eq 'settings') -and $elapsed -lt $waitMax) {
    Start-Sleep -Seconds $poll
    $elapsed += $poll
    $st = Get-ScreenState ([ConIn]::ReadScreen()) $isClaude
  }
  if ($st -eq 'dialog' -or $st -eq 'unknown' -or $st -eq 'settings') {
    Write-Output "BRIDGE_STATUS:not_at_prompt:$st"
    exit 0
  }
}

[ConIn]::Send([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:BRIDGE_B64)))
if ($env:BRIDGE_SUBMIT -ne '1') {
  Write-Output "BRIDGE_STATUS:ok$panelNote"
  exit 0
}

if ($isClaude -and $st -ne 'unavailable' -and -not $forceSend) {
  Start-Sleep -Milliseconds 1500
  for ($attempt = 1; $attempt -le 4; $attempt++) {
    [ConIn]::Send("`r")
    Start-Sleep -Milliseconds 600
    $pst = Get-ScreenState ([ConIn]::ReadScreen()) $true
    if ($pst -eq 'empty') {
      Write-Output "BRIDGE_STATUS:ok$panelNote"
      exit 0
    }
    if ($pst -eq 'unknown' -or $pst -eq 'unavailable') {
      if ($attempt -eq 1) {
        Start-Sleep -Milliseconds 1400
        [ConIn]::Send("`r")
      }
      Write-Output "BRIDGE_STATUS:ok_unverified$panelNote"
      exit 0
    }
    if ($pst -eq 'text' -and $attempt -lt 4) {
      Start-Sleep -Milliseconds 1400
    }
  }
  Write-Output "BRIDGE_STATUS:unsubmitted$panelNote"
  exit 0
}

Start-Sleep -Milliseconds 1500; [ConIn]::Send("`r")
Start-Sleep -Milliseconds 2000; [ConIn]::Send("`r")
Write-Output "BRIDGE_STATUS:ok$panelNote"
