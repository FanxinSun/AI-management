#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
TARGET=${CODEX_TARGET:-x86_64-unknown-linux-musl}
CARGO_BIN=${CARGO_BIN:-cargo}
RUSTC_BIN=${RUSTC_BIN:-}
RG_BIN=${RG_BIN:-}
BWRAP_BIN=${BWRAP_BIN:-}
KEEP=0
WORK=$(mktemp -d "${TMPDIR:-/tmp}/codex-custom-clean.XXXXXX")
cleanup() { (( KEEP )) || rm -rf "${WORK}"; }
trap cleanup EXIT

usage() {
    cat <<'EOF'
Usage: clean-checkout-verify.sh [options]

Run helper/tooling tests, build the pinned source patch, package it, install it
into an isolated temporary CODEX_HOME, verify the launcher, and exercise an
atomic rollback. Defaults to the release target x86_64-unknown-linux-musl.

Options: --target TRIPLE, --cargo PATH, --rustc PATH, --rg-bin PATH,
         --bwrap-bin PATH, --keep-work, --help
EOF
}
die() { printf 'clean-checkout-verify: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --target) TARGET=${2:?missing target after --target}; shift 2 ;;
        --cargo) CARGO_BIN=${2:?missing cargo after --cargo}; shift 2 ;;
        --rustc) RUSTC_BIN=${2:?missing rustc after --rustc}; shift 2 ;;
        --rg-bin) RG_BIN=${2:?missing rg after --rg-bin}; shift 2 ;;
        --bwrap-bin) BWRAP_BIN=${2:?missing bwrap after --bwrap-bin}; shift 2 ;;
        --keep-work) KEEP=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done

"${SCRIPT_DIR}/test-tooling.sh"
BUILD_ARGS=(--output-root "${WORK}/build" --target "${TARGET}" --cargo "${CARGO_BIN}")
[[ -n ${RUSTC_BIN} ]] && BUILD_ARGS+=(--rustc "${RUSTC_BIN}")
[[ -n ${RG_BIN} ]] && BUILD_ARGS+=(--rg-bin "${RG_BIN}")
[[ -n ${BWRAP_BIN} ]] && BUILD_ARGS+=(--bwrap-bin "${BWRAP_BIN}")
"${SCRIPT_DIR}/build-custom-codex.sh" "${BUILD_ARGS[@]}"
"${SCRIPT_DIR}/package-custom-codex.sh" --package-dir "${WORK}/build/package" \
    --archive "${WORK}/codex-custom-${TARGET}.tar.gz"
"${SCRIPT_DIR}/verify-custom-codex.sh" --package-dir "${WORK}/build/package"

ISOLATED_HOME=${WORK}/codex-home
ISOLATED_BIN=${WORK}/bin/codex
"${SCRIPT_DIR}/install-custom-codex.sh" --package-dir "${WORK}/build/package" \
    --codex-home "${ISOLATED_HOME}" --launcher-path "${ISOLATED_BIN}"
"${SCRIPT_DIR}/verify-custom-codex.sh" --release-dir "${ISOLATED_HOME}/packages/standalone/current"
"${ISOLATED_BIN}" --version
FIRST_RELEASE=$(readlink "${ISOLATED_HOME}/packages/standalone/current")
"${SCRIPT_DIR}/rollback-custom-codex.sh" --codex-home "${ISOLATED_HOME}" --release "${FIRST_RELEASE}"

STYLE_HOME=${WORK}/style-home
CODEX_HOME=${STYLE_HOME} bash "${ROOT}/../style/codex-focus/install-codex-style.sh" --dry-run
printf 'Clean-checkout validation passed for %s. Work: %s\n' "${TARGET}" "${WORK}"
