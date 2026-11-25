#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CUSTOM_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
PATCH_FILE=${CUSTOM_ROOT}/source/codex-custom-0.154.0.patch
LOCK_FILE=${CUSTOM_ROOT}/source/source-lock.toml
NO_ZSH=${CUSTOM_ROOT}/source/no-zsh.json

UPSTREAM_URL=${CODEX_UPSTREAM_URL:-https://github.com/openai/codex.git}
UPSTREAM_COMMIT=${CODEX_UPSTREAM_COMMIT:-6b9826e3aa83b1a5947db50f4332cb9c65f1b340}
TARGET=${CODEX_TARGET:-x86_64-unknown-linux-musl}
OUTPUT_ROOT=${CODEX_BUILD_ROOT:-}
CARGO_BIN=${CARGO_BIN:-cargo}
RUSTC_BIN=${RUSTC_BIN:-}
RG_BIN=${RG_BIN:-}
BWRAP_BIN=${BWRAP_BIN:-}

usage() {
    cat <<'EOF'
Usage: build-custom-codex.sh [options]

Fetch the pinned upstream Codex commit into a temporary source tree, apply the
tracked custom-build patch, and build a canonical package directory. The
default target is the pinned release target x86_64-unknown-linux-musl.

Options:
  --output-root PATH  Required output directory (or CODEX_BUILD_ROOT).
  --target TRIPLE     Rust target (or CODEX_TARGET).
  --cargo PATH        Cargo executable (or CARGO_BIN).
  --rustc PATH        Rust compiler paired with Cargo (or RUSTC_BIN).
  --rg-bin PATH       Existing executable to package as codex-path/rg.
  --bwrap-bin PATH    Existing Linux bubblewrap executable.
  --help              Show this help.

The output is self-contained under PATH and does not modify CODEX_HOME,
the active Codex release, native Windows configuration, or policy/hooks.
EOF
}

die() {
    printf 'build-custom-codex: %s\n' "$*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
        --output-root) OUTPUT_ROOT=${2:?missing path after --output-root}; shift 2 ;;
        --target) TARGET=${2:?missing target after --target}; shift 2 ;;
        --cargo) CARGO_BIN=${2:?missing path after --cargo}; shift 2 ;;
        --rustc) RUSTC_BIN=${2:?missing path after --rustc}; shift 2 ;;
        --rg-bin) RG_BIN=${2:?missing path after --rg-bin}; shift 2 ;;
        --bwrap-bin) BWRAP_BIN=${2:?missing path after --bwrap-bin}; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done

[[ -f ${PATCH_FILE} ]] || die "missing source patch: ${PATCH_FILE}"
[[ -f ${LOCK_FILE} ]] || die "missing source lock: ${LOCK_FILE}"
[[ -f ${NO_ZSH} ]] || die "missing no-zsh manifest: ${NO_ZSH}"
[[ -n ${OUTPUT_ROOT} ]] || OUTPUT_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/codex-custom-build.XXXXXX")
OUTPUT_ROOT=$(mkdir -p "${OUTPUT_ROOT}" && cd "${OUTPUT_ROOT}" && pwd)
SOURCE_DIR=${OUTPUT_ROOT}/source
PACKAGE_DIR=${OUTPUT_ROOT}/package
CARGO_TARGET_DIR=${OUTPUT_ROOT}/cargo-target
METADATA=${OUTPUT_ROOT}/build-metadata.env

[[ ! -e ${SOURCE_DIR} ]] || die "output already contains source: ${SOURCE_DIR}"
[[ ! -e ${PACKAGE_DIR} ]] || die "output already contains package: ${PACKAGE_DIR}"

command -v git >/dev/null 2>&1 || die 'git is required'
command -v python3 >/dev/null 2>&1 || die 'python3 is required'
command -v sha256sum >/dev/null 2>&1 || die 'sha256sum is required'
if [[ ! -x ${CARGO_BIN} ]]; then
    CARGO_BIN=$(command -v "${CARGO_BIN}" 2>/dev/null || true)
fi
[[ -n ${CARGO_BIN} && -x ${CARGO_BIN} ]] || die "cargo is not executable: ${CARGO_BIN:-unset}"

if [[ -z ${RUSTC_BIN} ]]; then
    CARGO_REAL=$(readlink -f "${CARGO_BIN}")
    RUSTC_BIN=$(dirname "${CARGO_REAL}")/rustc
fi
if [[ ! -x ${RUSTC_BIN} ]]; then
    RUSTC_BIN=$(command -v rustc 2>/dev/null || true)
fi
[[ -n ${RUSTC_BIN} && -x ${RUSTC_BIN} ]] || die "rustc is not executable; pass --rustc"

[[ -n ${RG_BIN} ]] || RG_BIN=$(command -v rg 2>/dev/null || true)
[[ -n ${RG_BIN} && -x ${RG_BIN} ]] || die 'ripgrep is required; pass --rg-bin PATH'
if [[ -n ${BWRAP_BIN} ]]; then
    [[ -x ${BWRAP_BIN} ]] || die "bwrap is not executable: ${BWRAP_BIN}"
else
    BWRAP_BIN=$(command -v bwrap 2>/dev/null || true)
fi

RUSTC_VERSION=$("${RUSTC_BIN}" --version)
[[ ${RUSTC_VERSION} == *' 1.95.0 '* ]] || die "expected Rust 1.95.0, got: ${RUSTC_VERSION}"
TARGET_LIBDIR=$("${RUSTC_BIN}" --print target-libdir --target "${TARGET}" 2>/dev/null || true)
if [[ -z ${TARGET_LIBDIR} || ! -d ${TARGET_LIBDIR} ]] || ! compgen -G "${TARGET_LIBDIR}/libstd-*.rlib" >/dev/null; then
    printf 'build-custom-codex: Rust target %s is not installed for %s.\n' "${TARGET}" "${RUSTC_VERSION}" >&2
    printf 'Install the pinned target/toolchain in the build environment or pass a target available there (for example x86_64-unknown-linux-gnu for host validation).\n' >&2
    exit 3
fi

printf 'Fetching %s at %s\n' "${UPSTREAM_URL}" "${UPSTREAM_COMMIT}"
git -c init.defaultBranch=main init -q "${SOURCE_DIR}"
git -C "${SOURCE_DIR}" remote add origin "${UPSTREAM_URL}"
git -C "${SOURCE_DIR}" fetch --depth=1 origin "${UPSTREAM_COMMIT}"
git -C "${SOURCE_DIR}" checkout --detach -q FETCH_HEAD
[[ $(git -C "${SOURCE_DIR}" rev-parse HEAD) == "${UPSTREAM_COMMIT}" ]] || die 'fetched commit does not match the pinned commit'

printf 'Checking and applying the custom source patch\n'
git -C "${SOURCE_DIR}" apply --check --binary "${PATCH_FILE}"
git -C "${SOURCE_DIR}" apply --binary "${PATCH_FILE}"
git -C "${SOURCE_DIR}" add -A
# Snapshot fixtures intentionally contain right-padding that is part of the
# rendered TUI contract; check all source text while excluding only snapshots.
git -C "${SOURCE_DIR}" diff --cached --check -- . ':(exclude)**/*.snap'
SOURCE_TREE=$(git -C "${SOURCE_DIR}" write-tree)

mkdir -p "${PACKAGE_DIR}"
export CODEX_REPO_ROOT=${SOURCE_DIR}
export CARGO_TARGET_DIR
export RUSTC=${RUSTC_BIN}
export RUST_MIN_STACK=${RUST_MIN_STACK:-16777216}
export PATH=$(dirname "${RUSTC_BIN}"):$(dirname "${CARGO_BIN}"):${PATH}

BUILD_CMD=(python3 "${SOURCE_DIR}/scripts/build_codex_package.py"
    --target "${TARGET}" --variant codex --package-version 0.154.0
    --package-dir "${PACKAGE_DIR}" --cargo "${CARGO_BIN}"
    --cargo-profile release --rg-bin "${RG_BIN}" --zsh-manifest "${NO_ZSH}")
if [[ -n ${BWRAP_BIN} ]]; then
    BUILD_CMD+=(--bwrap-bin "${BWRAP_BIN}")
fi
"${BUILD_CMD[@]}"

ENTRYPOINT=${PACKAGE_DIR}/bin/codex
[[ -x ${ENTRYPOINT} ]] || die "package builder did not create executable entrypoint"
PACKAGE_HASH=$(sha256sum "${ENTRYPOINT}" | awk '{print $1}')
cat >"${METADATA}" <<EOF
CODEX_VERSION=0.154.0
UPSTREAM_URL=${UPSTREAM_URL}
UPSTREAM_COMMIT=${UPSTREAM_COMMIT}
SOURCE_TREE=${SOURCE_TREE}
SOURCE_PATCH_SHA256=$(sha256sum "${PATCH_FILE}" | awk '{print $1}')
TARGET=${TARGET}
RUSTC_VERSION=${RUSTC_VERSION}
RUST_MIN_STACK=${RUST_MIN_STACK}
PACKAGE_DIR=${PACKAGE_DIR}
ENTRYPOINT_SHA256=${PACKAGE_HASH}
EOF
chmod 0644 "${METADATA}"
printf 'Build complete.\nPackage: %s\nMetadata: %s\nEntrypoint SHA-256: %s\n' "${PACKAGE_DIR}" "${METADATA}" "${PACKAGE_HASH}"
