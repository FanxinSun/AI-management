#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR=
RELEASE_DIR=
EXPECTED_HASH=
RUN_VERSION=1

usage() {
    cat <<'EOF'
Usage: verify-custom-codex.sh (--package-dir PATH | --release-dir PATH) [options]

Validate package metadata, required executables, and SHA-256 values. The
entrypoint is run with --version unless --no-run is supplied.
EOF
}
die() { printf 'verify-custom-codex: %s\n' "$*" >&2; exit 1; }

while (($#)); do
    case "$1" in
        --package-dir) PACKAGE_DIR=${2:?missing path after --package-dir}; shift 2 ;;
        --release-dir) RELEASE_DIR=${2:?missing path after --release-dir}; shift 2 ;;
        --expected-hash) EXPECTED_HASH=${2:?missing hash after --expected-hash}; shift 2 ;;
        --no-run) RUN_VERSION=0; shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done
[[ -n ${PACKAGE_DIR} || -n ${RELEASE_DIR} ]] || die 'package or release directory is required'
[[ -z ${PACKAGE_DIR} || -z ${RELEASE_DIR} ]] || die 'choose package or release, not both'
ROOT=${PACKAGE_DIR:-${RELEASE_DIR}}
[[ -d ${ROOT} ]] || die "directory does not exist: ${ROOT}"

readarray -t META < <(python3 - "${ROOT}" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
data = json.loads((root / 'codex-package.json').read_text(encoding='utf-8'))
for key in ('version', 'target', 'variant', 'entrypoint'):
    print(f'{key}={data.get(key, "")}')
PY
)
for item in "${META[@]}"; do
    case ${item} in
        version=*) VERSION=${item#*=} ;;
        target=*) TARGET=${item#*=} ;;
        variant=*) VARIANT=${item#*=} ;;
        entrypoint=*) ENTRYPOINT_REL=${item#*=} ;;
    esac
done
[[ ${VERSION} == 0.154.0 ]] || die "unexpected package version: ${VERSION}"
[[ ${VARIANT} == codex ]] || die "unexpected package variant: ${VARIANT}"
ENTRYPOINT=${ROOT}/${ENTRYPOINT_REL}
[[ -x ${ENTRYPOINT} ]] || die "entrypoint is not executable: ${ENTRYPOINT}"
[[ -x ${ROOT}/bin/codex-code-mode-host ]] || die 'missing codex-code-mode-host'
[[ -x ${ROOT}/codex-path/rg ]] || die 'missing packaged ripgrep'
if [[ ${TARGET} == *-linux-* ]]; then
    [[ -x ${ROOT}/codex-resources/bwrap ]] || die 'missing packaged bwrap'
fi
ACTUAL_HASH=$(sha256sum "${ENTRYPOINT}" | awk '{print $1}')
[[ -z ${EXPECTED_HASH} || ${ACTUAL_HASH} == ${EXPECTED_HASH} ]] || die "entrypoint hash mismatch: ${ACTUAL_HASH}"
if (( RUN_VERSION )); then
    VERSION_OUTPUT=$("${ENTRYPOINT}" --version 2>&1) || die "entrypoint --version failed: ${VERSION_OUTPUT}"
    printf '%s\n' "${VERSION_OUTPUT}"
fi
printf 'Verified Codex %s package for %s\nEntrypoint SHA-256: %s\n' "${VERSION}" "${TARGET}" "${ACTUAL_HASH}"
