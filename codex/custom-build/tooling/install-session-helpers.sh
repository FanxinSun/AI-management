#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
BIN_DIR=${HOME}/.local/bin
LIB_DIR=${HOME}/.local/lib/codex-session-helpers
DRY_RUN=0

usage() {
    cat <<'EOF'
Usage: install-session-helpers.sh [options]

Install the portable Codex session status/send helpers and their queue schema.
The default locations are ~/.local/bin and ~/.local/lib/codex-session-helpers.
Only those explicitly selected locations are changed; CODEX_HOME state and
policy/hooks are not touched.

Options:
  --bin-dir PATH
  --lib-dir PATH
  --dry-run
EOF
}
die() { printf 'install-session-helpers: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --bin-dir) BIN_DIR=${2:?missing path after --bin-dir}; shift 2 ;;
        --lib-dir) LIB_DIR=${2:?missing path after --lib-dir}; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done

FILES=(live_rpc.py status.py send.py queue-schema-0.154.0.sql test_status.py test_send.py)
for file in "${FILES[@]}"; do
    [[ -f ${ROOT}/session-helpers/${file} ]] || die "missing ${file}"
done
if (( DRY_RUN )); then
    printf '[dry-run] install helper library to %s\n' "${LIB_DIR}"
    printf '[dry-run] install wrappers to %s\n' "${BIN_DIR}"
    exit 0
fi
mkdir -p "${BIN_DIR}" "${LIB_DIR}"
for file in "${FILES[@]}"; do
    target=${LIB_DIR}/${file}
    if [[ -f ${target} ]] && ! cmp -s "${ROOT}/session-helpers/${file}" "${target}"; then
        backup=${target}.bak-codex-custom-$(date +%Y%m%d%H%M%S)
        while [[ -e ${backup} ]]; do
            backup=${target}.bak-codex-custom-$(date +%Y%m%d%H%M%S)-${RANDOM}
        done
        cp -p "${target}" "${backup}"
        printf 'Preserved %s\n' "${backup}"
    fi
    install -m 0644 "${ROOT}/session-helpers/${file}" "${target}"
done
install -m 0755 "${ROOT}/session-helpers/bin/codex-session-status" "${BIN_DIR}/codex-session-status"
install -m 0755 "${ROOT}/session-helpers/bin/codex-session-send" "${BIN_DIR}/codex-session-send"
printf 'Installed session helpers in %s and %s\n' "${LIB_DIR}" "${BIN_DIR}"
