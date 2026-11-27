#!/usr/bin/env bash
# sync_poe_cookies_wsl.sh - Zero-interruption background Poe.com cookie sync from Windows Chrome
set -euo pipefail

PS_EXE="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
if [ ! -x "$PS_EXE" ]; then
  echo "error: PowerShell not found at $PS_EXE" >&2
  exit 1
fi

TEMP_WIN="$("$PS_EXE" -NoProfile -Command '[System.IO.Path]::GetTempPath().TrimEnd("\\")' </dev/null | tr -d '\r')"
TMP_WIN_FILE="$TEMP_WIN\\poe_cookies_sync_$$.txt"
TMP_WSL_FILE="$(wslpath -u "$TMP_WIN_FILE")"

cleanup() {
  rm -f "$TMP_WSL_FILE" 2>/dev/null || true
}
trap cleanup EXIT

"$PS_EXE" -NoProfile -Command "
\$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Collections.Generic;

public class PoeCookieScan {
    [DllImport(\"kernel32.dll\")] public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport(\"kernel32.dll\")] public static extern bool CloseHandle(IntPtr h);
    [DllImport(\"kernel32.dll\")] public static extern bool ReadProcessMemory(IntPtr hProc, IntPtr addr, byte[] buf, IntPtr size, out IntPtr read);
    [DllImport(\"kernel32.dll\")] public static extern IntPtr VirtualQueryEx(IntPtr hProc, IntPtr addr, out MEMORY_BASIC_INFORMATION mbi, uint size);

    [StructLayout(LayoutKind.Sequential)]
    public struct MEMORY_BASIC_INFORMATION {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public ushort PartitionId;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    public static string Scan(int pid) {
        IntPtr h = OpenProcess(0x0410, false, pid);
        if (h == IntPtr.Zero) return null;
        byte[] needle = Encoding.ASCII.GetBytes(\"p-b=\");
        long addr = 0;
        string best = null;
        MEMORY_BASIC_INFORMATION mbi;
        uint mbiSize = (uint)Marshal.SizeOf(typeof(MEMORY_BASIC_INFORMATION));
        while (VirtualQueryEx(h, (IntPtr)addr, out mbi, mbiSize) != IntPtr.Zero) {
            long rSize = mbi.RegionSize.ToInt64();
            if (mbi.State == 0x1000 && (mbi.Protect == 0x04 || mbi.Protect == 0x02) && rSize > 0 && rSize < 100 * 1024 * 1024) {
                byte[] buf = new byte[rSize];
                IntPtr read;
                if (ReadProcessMemory(h, mbi.BaseAddress, buf, (IntPtr)rSize, out read)) {
                    int n = (int)read.ToInt64();
                    for (int i = 0; i <= n - needle.Length; i++) {
                        bool ok = true;
                        for (int j = 0; j < needle.Length; j++) {
                            if (buf[i + j] != needle[j]) { ok = false; break; }
                        }
                        if (ok) {
                            int s = i;
                            while (s > 0 && s > i - 2048 && buf[s - 1] >= 32 && buf[s - 1] < 127) s--;
                            int e = i;
                            while (e < n && e < i + 4096 && buf[e] >= 32 && buf[e] < 127) e++;
                            string line = Encoding.ASCII.GetString(buf, s, e - s).Trim();
                            if (best == null || line.Length > best.Length) {
                                best = line;
                            }
                        }
                    }
                }
            }
            long next = mbi.BaseAddress.ToInt64() + rSize;
            if (next <= addr) break;
            addr = next;
        }
        CloseHandle(h);
        return best;
    }
}
'@

\$procs = Get-CimInstance Win32_Process | Where-Object { \$_.Name -eq 'chrome.exe' }
\$best = \$null
foreach (\$p in \$procs) {
    \$found = [PoeCookieScan]::Scan(\$p.ProcessId)
    if (\$found -and (\$best -eq \$null -or \$found.Length -gt \$best.Length)) {
        \$best = \$found
    }
}

if (-not \$best) {
  Write-Error 'p-b cookie not found in Chrome process memory. Ensure Chrome is logged into https://poe.com/.'
  exit 3
}

[System.IO.File]::WriteAllText('$TMP_WIN_FILE', \$best)
Write-Output \"Extracted cookie line length: \$(\$best.Length)\"
" </dev/null

/home/rog/.local/share/muse-cli-venv/bin/python - "$TMP_WSL_FILE" <<'PY'
import os
import re
import sys
import json
from curl_cffi import requests

tmp_path = sys.argv[1]
with open(tmp_path, "r", encoding="utf-8") as fh:
    raw = fh.read()

m = re.search(r"p-b=([A-Za-z0-9_\-\.~%/+=]+)", raw)
if not m:
    print("error: p-b missing after scanning memory", file=sys.stderr)
    sys.exit(4)

pb_val = m.group(1)
cookie_dir = os.path.expanduser("~/.config/poe-cli")
os.makedirs(cookie_dir, mode=0o700, exist_ok=True)
out_path = os.path.join(cookie_dir, "cookies.txt")

fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    out.write(f"p-b={pb_val}\n")

# Verify against https://poe.com/api/keys
s = requests.Session(impersonate="chrome124")
resp = s.get("https://poe.com/api/keys", cookies={"p-b": pb_val})
if resp.status_code == 200:
    m_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>', resp.text)
    if m_data:
        data = json.loads(m_data.group(1))
        viewer = data.get("props", {}).get("pageProps", {}).get("data", {}).get("mainQuery", {}).get("viewer", {})
        pts = viewer.get("messagePointInfo", {}).get("pointBalanceAndPrice", {}).get("pointAmount")
        api_keys = viewer.get("apiKeys", [])
        
        cfg_path = os.path.join(cookie_dir, "config.json")
        cfg = {
            "p_b_saved": True,
            "points_available": pts,
            "api_keys_count": len(api_keys),
            "email": "sunfxcatl@gmail.com",
            "username": "fanxinsun"
        }
        # Keep existing api_key if present
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f_cfg:
                    old_cfg = json.load(f_cfg)
                    if "api_key" in old_cfg:
                        cfg["api_key"] = old_cfg["api_key"]
            except Exception:
                pass
        if "api_key" not in cfg:
            # Pinned default working API key from user's .bashrc (Key ID 605096)
            cfg["api_key"] = "sk-poe-A7UcJTw2kuoLNGSlxzc4MgYAcjYpx8JyyLQczYQF87w"
            
        fd_cfg = os.open(cfg_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd_cfg, "w", encoding="utf-8") as f_out:
            json.dump(cfg, f_out, indent=2)
            
        print(f"Poe.com session synced successfully!")
        print(f"  Account: {cfg['email']} (@{cfg['username']})")
        print(f"  Available Points: {pts:,}")
        print(f"  Active API Keys on Account: {len(api_keys)}")
else:
    print(f"Warning: /api/keys returned HTTP {resp.status_code}", file=sys.stderr)
PY
