#!/usr/bin/env bash
set -euo pipefail

CODEX_ROOT=${CODEX_HOME:-${HOME}/.codex}
RELEASE=
usage() {
    cat <<'EOF'
Usage: rollback-custom-codex.sh --release RELEASE_NAME [--codex-home PATH]

Atomically point CODEX_HOME/packages/standalone/current at an existing release.
No release is deleted and the current path must already be a symlink.
EOF
}
die() { printf 'rollback-custom-codex: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --release) RELEASE=${2:?missing release after --release}; shift 2 ;;
        --codex-home) CODEX_ROOT=${2:?missing path after --codex-home}; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done
[[ -n ${RELEASE} ]] || die 'release name is required'
STANDALONE=${CODEX_ROOT}/packages/standalone
TARGET=${STANDALONE}/${RELEASE}
[[ -d ${TARGET} ]] || die "release directory does not exist: ${TARGET}"
[[ -L ${STANDALONE}/current || ! -e ${STANDALONE}/current ]] || die 'current is not a symlink; refusing to replace it'
ln -s "${RELEASE}" "${STANDALONE}/current.next.$$"
mv -Tf "${STANDALONE}/current.next.$$" "${STANDALONE}/current"
printf 'Rolled back current to %s\n' "${RELEASE}"
