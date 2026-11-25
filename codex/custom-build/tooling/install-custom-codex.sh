#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CUSTOM_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
PACKAGE_DIR=
CODEX_ROOT=${CODEX_HOME:-${HOME}/.codex}
LAUNCHER_PATH=

usage() {
    cat <<'EOF'
Usage: install-custom-codex.sh --package-dir PATH [options]

Install one validated package as a new release below CODEX_HOME/packages/
standalone and atomically switch only that home's current symlink. The old
release is retained. Pass --launcher-path to install the portable launcher at
an explicitly chosen path; no launcher is changed by default.

Options:
  --package-dir PATH
  --codex-home PATH       CODEX_HOME override
  --launcher-path PATH    Optional wrapper destination
EOF
}
die() { printf 'install-custom-codex: %s\n' "$*" >&2; exit 1; }

while (($#)); do
    case "$1" in
        --package-dir) PACKAGE_DIR=${2:?missing path after --package-dir}; shift 2 ;;
        --codex-home) CODEX_ROOT=${2:?missing path after --codex-home}; shift 2 ;;
        --launcher-path) LAUNCHER_PATH=${2:?missing path after --launcher-path}; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done
[[ -n ${PACKAGE_DIR} && -d ${PACKAGE_DIR} ]] || die 'package directory is required'
"${SCRIPT_DIR}/verify-custom-codex.sh" --package-dir "${PACKAGE_DIR}" --no-run
CODEX_ROOT=$(mkdir -p "${CODEX_ROOT}" && cd "${CODEX_ROOT}" && pwd)
STANDALONE=${CODEX_ROOT}/packages/standalone
mkdir -p "${STANDALONE}"
if [[ -e ${STANDALONE}/current && ! -L ${STANDALONE}/current ]]; then
    die "refusing to replace non-symlink current path: ${STANDALONE}/current"
fi

METADATA=$(python3 - "${PACKAGE_DIR}" <<'PY'
import json
from pathlib import Path
import sys
data = json.loads((Path(sys.argv[1]) / 'codex-package.json').read_text())
print(data['version'])
print(data['target'])
PY
)
VERSION=$(sed -n '1p' <<<"${METADATA}")
TARGET=$(sed -n '2p' <<<"${METADATA}")
HASH=$(sha256sum "${PACKAGE_DIR}/bin/codex" | awk '{print $1}')
RELEASE_NAME=${VERSION}-${TARGET}-custom-${HASH:0:16}
RELEASE=${STANDALONE}/${RELEASE_NAME}
if [[ -e ${RELEASE} ]]; then
    die "release already exists; refusing to overwrite: ${RELEASE}"
fi

STAGE=$(mktemp -d "${STANDALONE}/.install.XXXXXX")
cleanup() { rm -rf "${STAGE}"; }
trap cleanup EXIT
install -d -m 0755 "${STAGE}/release"
cp -a "${PACKAGE_DIR}/." "${STAGE}/release/"
mv "${STAGE}/release" "${RELEASE}"
ln -s "${RELEASE_NAME}" "${STANDALONE}/current.next.$$"
mv -Tf "${STANDALONE}/current.next.$$" "${STANDALONE}/current"

if [[ -n ${LAUNCHER_PATH} ]]; then
    LAUNCHER_PATH=$(mkdir -p "$(dirname "${LAUNCHER_PATH}")" && cd "$(dirname "${LAUNCHER_PATH}")" && pwd)/$(basename "${LAUNCHER_PATH}")
    if [[ -e ${LAUNCHER_PATH} || -L ${LAUNCHER_PATH} ]]; then
        BACKUP=${LAUNCHER_PATH}.bak-codex-custom-$(date +%Y%m%d%H%M%S)
        while [[ -e ${BACKUP} || -L ${BACKUP} ]]; do
            BACKUP=${LAUNCHER_PATH}.bak-codex-custom-$(date +%Y%m%d%H%M%S)-${RANDOM}
        done
        mv "${LAUNCHER_PATH}" "${BACKUP}"
        printf 'Preserved existing launcher at %s\n' "${BACKUP}"
    fi
    install -m 0755 "${CUSTOM_ROOT}/launcher/codex" "${LAUNCHER_PATH}"
fi
trap - EXIT
printf 'Installed %s\nCurrent: %s\nEntrypoint SHA-256: %s\n' "${RELEASE}" "${STANDALONE}/current" "${HASH}"
