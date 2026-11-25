#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CODEX_ROOT=${CODEX_HOME:-${HOME}/.codex}
CONFIG_PATH=${CODEX_ROOT}/config.toml
THEME_SOURCE=${SCRIPT_DIR}/themes/codex-focus.tmTheme
THEME_NAME=codex-focus.tmTheme
DRY_RUN=0

usage() {
    cat <<'EOF'
Usage: install-codex-style.sh [--dry-run]

Install the Codex Focus theme and the recorded [tui] appearance settings.
CODEX_HOME may point at a non-default Codex home.
EOF
}

case "${1:-}" in
    "") ;;
    --dry-run) DRY_RUN=1 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

if [[ ! -f ${THEME_SOURCE} ]]; then
    printf 'Missing bundled theme: %s\n' "${THEME_SOURCE}" >&2
    exit 1
fi

WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/codex-style.XXXXXX")
cleanup() {
    rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

REAL_CODEX_ROOT=${CODEX_ROOT}
REAL_CONFIG_PATH=${CONFIG_PATH}
CANDIDATE_CONFIG=${WORK_DIR}/config.toml
if (( DRY_RUN )); then
    CODEX_ROOT=${WORK_DIR}/codex
    mkdir -p "${CODEX_ROOT}/themes"
    if [[ -f ${REAL_CONFIG_PATH} ]]; then
        cp -p "${REAL_CONFIG_PATH}" "${CANDIDATE_CONFIG}"
    else
        : > "${CANDIDATE_CONFIG}"
    fi
else
    mkdir -p "${CODEX_ROOT}/themes"
    if [[ -f ${CONFIG_PATH} ]]; then
        cp -p "${CONFIG_PATH}" "${CANDIDATE_CONFIG}"
    else
        : > "${CANDIDATE_CONFIG}"
    fi
fi

# tomllib needs Python 3.11+; macOS's /usr/bin/python3 is 3.9, so pick the first that has it.
PYTHON=
for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
    if command -v "${candidate}" >/dev/null 2>&1 && "${candidate}" -c 'import tomllib' 2>/dev/null; then
        PYTHON=${candidate}; break
    fi
done
[[ -n ${PYTHON} ]] || { printf 'Needs Python 3.11+ (for tomllib); none found on PATH\n' >&2; exit 1; }

"${PYTHON}" - "${CANDIDATE_CONFIG}" <<'PY'
from pathlib import Path
import re
import sys
import tomllib

path = Path(sys.argv[1])
values = {
    "theme": '"codex-focus"',
    "status_line": '["thread-title", "model-with-reasoning", "current-dir", "permissions", "approval-mode", "five-hour-limit", "weekly-limit"]',
    "status_line_use_colors": "true",
    "terminal_title": '["activity", "thread-title", "project-name"]',
}

text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
start = next((i for i, line in enumerate(lines) if line.strip() == "[tui]"), None)

if start is None:
    prefix = text
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += "\n"
    new_text = prefix + "\n[tui]\n" + "".join(
        f"{key} = {value}\n" for key, value in values.items()
    )
else:
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if re.match(r"^\s*\[", lines[i])
        ),
        len(lines),
    )
    found = set()
    for i in range(start + 1, end):
        match = re.match(r"^\s*(theme|status_line|status_line_use_colors|terminal_title)\s*=", lines[i])
        if match:
            key = match.group(1)
            lines[i] = f"{key} = {values[key]}\n"
            found.add(key)
    missing = [f"{key} = {values[key]}\n" for key in values if key not in found]
    lines[end:end] = missing
    new_text = "".join(lines)

try:
    tomllib.loads(new_text)
except (tomllib.TOMLDecodeError, ValueError) as exc:
    raise SystemExit(f"refusing to write invalid TOML: {exc}")

with path.open("w", encoding="utf-8", newline="") as handle:
    handle.write(new_text)
PY

if (( DRY_RUN )); then
    printf '[dry-run] would install %s to %s\n' "${THEME_NAME}" "${REAL_CODEX_ROOT}/themes/${THEME_NAME}"
    printf '[dry-run] would merge the recorded [tui] settings into %s\n' "${REAL_CONFIG_PATH}"
    printf '[dry-run] TOML merge validation passed\n'
    exit 0
fi

if [[ -f ${CONFIG_PATH} ]] && ! cmp -s "${CONFIG_PATH}" "${WORK_DIR}/config.toml"; then
    backup=${CONFIG_PATH}.bak-style-$(date +%Y%m%d%H%M%S)
    while [[ -e ${backup} ]]; do
        backup=${CONFIG_PATH}.bak-style-$(date +%Y%m%d%H%M%S)-${RANDOM}
    done
    cp -p "${CONFIG_PATH}" "${backup}"
    cp -p "${WORK_DIR}/config.toml" "${CONFIG_PATH}"
    printf 'Updated %s (backup: %s)\n' "${CONFIG_PATH}" "${backup}"
else
    if [[ ! -f ${CONFIG_PATH} ]]; then
        install -m 0644 "${WORK_DIR}/config.toml" "${CONFIG_PATH}"
        printf 'Created %s\n' "${CONFIG_PATH}"
    else
        printf 'TUI settings already match %s\n' "${CONFIG_PATH}"
    fi
fi

THEME_TARGET=${CODEX_ROOT}/themes/${THEME_NAME}
if [[ -f ${THEME_TARGET} ]] && cmp -s "${THEME_SOURCE}" "${THEME_TARGET}"; then
    printf 'Theme already matches %s\n' "${THEME_TARGET}"
elif [[ -f ${THEME_TARGET} ]]; then
    backup=${THEME_TARGET}.bak-style-$(date +%Y%m%d%H%M%S)
    while [[ -e ${backup} ]]; do
        backup=${THEME_TARGET}.bak-style-$(date +%Y%m%d%H%M%S)-${RANDOM}
    done
    cp -p "${THEME_TARGET}" "${backup}"
    install -m 0644 "${THEME_SOURCE}" "${THEME_TARGET}"
    printf 'Updated %s (backup: %s)\n' "${THEME_TARGET}" "${backup}"
else
    install -m 0644 "${THEME_SOURCE}" "${THEME_TARGET}"
    printf 'Installed %s\n' "${THEME_TARGET}"
fi

printf 'Codex Focus style installation complete. Restart Codex sessions to reload it.\n'
