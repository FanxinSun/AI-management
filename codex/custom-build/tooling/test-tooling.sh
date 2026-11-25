#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

for script in "${ROOT}"/tooling/*.sh "${ROOT}"/launcher/codex "${ROOT}"/session-helpers/bin/*; do
    bash -n "${script}"
done
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${ROOT}/session-helpers${PYTHONPATH:+:${PYTHONPATH}}" \
    python3 -m unittest discover -s "${ROOT}/session-helpers" -p 'test_*.py'
"${ROOT}/tooling/install-session-helpers.sh" --dry-run \
    --bin-dir "${TMPDIR:-/tmp}/codex-custom-test-bin" \
    --lib-dir "${TMPDIR:-/tmp}/codex-custom-test-lib"
printf 'Codex custom tooling and helper tests passed.\n'
