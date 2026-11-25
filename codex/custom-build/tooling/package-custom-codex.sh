#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR=
ARCHIVE=

usage() {
    cat <<'EOF'
Usage: package-custom-codex.sh --package-dir PATH --archive PATH

Validate the canonical package layout and create a deterministic .tar.gz
archive. Existing outputs are never overwritten.
EOF
}
die() { printf 'package-custom-codex: %s\n' "$*" >&2; exit 1; }

while (($#)); do
    case "$1" in
        --package-dir) PACKAGE_DIR=${2:?missing path after --package-dir}; shift 2 ;;
        --archive) ARCHIVE=${2:?missing path after --archive}; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done
[[ -n ${PACKAGE_DIR} && -d ${PACKAGE_DIR} ]] || die 'package directory is required'
[[ -n ${ARCHIVE} ]] || die 'archive path is required'
[[ ${ARCHIVE} == *.tar.gz || ${ARCHIVE} == *.tgz ]] || die 'archive must end in .tar.gz or .tgz'
[[ ! -e ${ARCHIVE} ]] || die "refusing to overwrite existing archive: ${ARCHIVE}"

python3 - "${PACKAGE_DIR}" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
metadata = json.loads((root / 'codex-package.json').read_text(encoding='utf-8'))
required = [
    root / metadata['entrypoint'],
    root / 'bin' / 'codex-code-mode-host',
    root / 'codex-path' / 'rg',
]
if metadata.get('layoutVersion') != 1 or metadata.get('version') != '0.154.0':
    raise SystemExit(f'unsupported package metadata: {metadata}')
if metadata.get('variant') != 'codex':
    raise SystemExit('package variant is not codex')
for path in required:
    if not path.is_file() or not path.stat().st_mode & 0o111:
        raise SystemExit(f'missing or non-executable package input: {path}')
if metadata.get('target', '').endswith('-linux-gnu') or metadata.get('target', '').endswith('-linux-musl'):
    bwrap = root / 'codex-resources' / 'bwrap'
    if not bwrap.is_file() or not bwrap.stat().st_mode & 0o111:
        raise SystemExit(f'missing Linux bwrap resource: {bwrap}')
PY

ARCHIVE=$(mkdir -p "$(dirname "${ARCHIVE}")" && cd "$(dirname "${ARCHIVE}")" && pwd)/$(basename "${ARCHIVE}")
TMP=${ARCHIVE}.tmp.$$
trap 'rm -f "${TMP}"' EXIT
tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
    -cf - -C "$(dirname "${PACKAGE_DIR}")" "$(basename "${PACKAGE_DIR}")" | gzip -n >"${TMP}"
mv -n "${TMP}" "${ARCHIVE}"
trap - EXIT
sha256sum "${ARCHIVE}" >"${ARCHIVE}.sha256"
printf 'Packaged %s\nSHA-256 file: %s.sha256\n' "${ARCHIVE}" "${ARCHIVE}"
