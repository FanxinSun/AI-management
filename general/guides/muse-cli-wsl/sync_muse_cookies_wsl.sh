#!/usr/bin/env bash
# Silently sync muse.ai session cookies from a running Windows Chrome NetworkService
# process into ~/.config/muse-cli/cookies.txt (chmod 600) with zero UI/focus/clipboard changes.
set -euo pipefail

PS_EXE="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
if [ ! -x "$PS_EXE" ]; then
  echo "error: Windows PowerShell not found at $PS_EXE (WSL2 required)" >&2
  exit 1
fi

TMP_WIN_DIR="$("$PS_EXE" -NoProfile -Command '[System.IO.Path]::GetTempPath()' </dev/null | tr -d '\r\n')"
TMP_WIN_FILE="${TMP_WIN_DIR}muse_cookies_sync_$$.txt"
TMP_WSL_FILE="$(wslpath -u "$TMP_WIN_FILE")"

cleanup() {
  rm -f "$TMP_WSL_FILE" 2>/dev/null || true
}
trap cleanup EXIT

"$PS_EXE" -NoProfile -Command "
\$ErrorActionPreference = 'Stop'
\$proc = Get-CimInstance Win32_Process | Where-Object {
  \$_.Name -eq 'chrome.exe' -and \$_.CommandLine -match 'network\.mojom\.NetworkService'
} | Select-Object -First 1
if (-not \$proc) {
  Write-Error 'Chrome NetworkService process not found. Ensure Chrome is running and logged into https://muse.ai/.'
  exit 2
}
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Text.RegularExpressions;
using System.Runtime.InteropServices;

public class MuseCookieScan {
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

    public static string Find(int pid) {
        IntPtr h = OpenProcess(0x0410, false, pid);
        if (h == IntPtr.Zero) return null;
        byte[] needle = Encoding.ASCII.GetBytes(\"hatch_sess=\");
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
                            var m = Regex.Match(line, @\"hatch_sess=[A-Za-z0-9_\\-\\.~%/+=]+\");
                            if (m.Success && (best == null || line.Length > best.Length)) {
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
\$line = [MuseCookieScan]::Find([int]\$proc.ProcessId)
if (-not \$line) {
  Write-Error 'hatch_sess cookie not found in Chrome NetworkService memory. Visit https://muse.ai/ in Chrome first.'
  exit 3
}
[System.IO.File]::WriteAllText('$TMP_WIN_FILE', \$line)
Write-Output \"Extracted cookie header length: \$(\$line.Length) (NetworkService PID \$(\$proc.ProcessId))\"
" </dev/null

python3 - "$TMP_WSL_FILE" <<'PY'
import os
import re
import sys

tmp_path = sys.argv[1]
with open(tmp_path, "r", encoding="utf-8") as fh:
    raw = fh.read()

pairs = re.findall(r"([A-Za-z0-9_\-]+=[A-Za-z0-9_\-\.~%/+=]+)", raw)
if not any(kv.startswith("hatch_sess=") for kv in pairs):
    print("error: hatch_sess missing after parsing cookie pairs", file=sys.stderr)
    sys.exit(4)

cookie_dir = os.path.expanduser("~/.config/muse-cli")
os.makedirs(cookie_dir, mode=0o700, exist_ok=True)
out_path = os.path.join(cookie_dir, "cookies.txt")
fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    out.write("; ".join(pairs) + "\n")

print("Saved cookie names:", [kv.split("=", 1)[0] for kv in pairs])
PY

if command -v muse-cli >/dev/null 2>&1; then
  muse-cli status
fi
