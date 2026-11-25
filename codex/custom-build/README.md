# Full Codex custom build

This bundle makes the complete WSL Codex 0.154.0 customization reproducible:
it fetches the pinned upstream source, applies the accepted source patch, builds
the release package, installs it without replacing older releases, and supports
an atomic rollback. The patch contains the full TUI/transcript/selection/print
and queue changes accepted from the source worktree; it is not an appearance-only
subset.

## Reproducible source and package

The source lock is in [`source/source-lock.toml`](source/source-lock.toml).
It pins upstream commit `6b9826e3aa83b1a5947db50f4332cb9c65f1b340`, Rust 1.95.0,
the `x86_64-unknown-linux-musl` release target, and the patch digest. The patch
is applied with `git apply --check --binary`; temporary `.snap.new` and
`.pending-snap` files are not included.

On WSL, provide the pinned Rust toolchain and an installed target. The current
machine's active build used the following explicit tool paths; other machines
may use their own paths:

```bash
codex-custom/tooling/clean-checkout-verify.sh \
  --target x86_64-unknown-linux-musl \
  --cargo /path/to/rust-1.95.0/bin/cargo \
  --rustc /path/to/rust-1.95.0/bin/rustc \
  --rg-bin /path/to/rg \
  --bwrap-bin /usr/bin/bwrap
```

If a host-validation target is available but the release musl target is not,
use `--target x86_64-unknown-linux-gnu`; record that result as host validation,
not as a musl release build. The build script fails explicitly when the
requested Rust target is unavailable.

The lower-level sequence is:

```bash
codex-custom/tooling/build-custom-codex.sh --output-root /tmp/codex-custom-build \
  --target x86_64-unknown-linux-musl --cargo /path/to/cargo --rustc /path/to/rustc \
  --rg-bin /path/to/rg --bwrap-bin /usr/bin/bwrap
codex-custom/tooling/package-custom-codex.sh \
  --package-dir /tmp/codex-custom-build/package \
  --archive /tmp/codex-custom-0.154.0.tar.gz
```

The build output is outside the checkout. No script changes the active
`~/.codex` release or native Windows configuration unless the caller explicitly
invokes the installer with a chosen `--codex-home`/`--launcher-path`.

## Install and rollback

Use an isolated home for validation or an explicitly selected Codex home:

```bash
codex-custom/tooling/install-custom-codex.sh \
  --package-dir /tmp/codex-custom-build/package \
  --codex-home /path/to/.codex \
  --launcher-path /path/to/bin/codex
codex-custom/tooling/verify-custom-codex.sh \
  --release-dir /path/to/.codex/packages/standalone/current
codex-custom/tooling/rollback-custom-codex.sh \
  --codex-home /path/to/.codex \
  --release 0.154.0-x86_64-unknown-linux-musl-custom-<hash-prefix>
```

Installation copies the canonical package into a new content-addressed release
directory and atomically switches only `packages/standalone/current`. Existing
releases and launcher backups remain recoverable.

## Portable cross-agent helpers

The actual `codex-session-status` and `codex-session-send` implementations,
their 0.154.0 queue schema, tests, and WSL wrappers are tracked under
[`session-helpers/`](session-helpers/). They use `CODEX_HOME` and do not contain
machine-specific `/home/rog` paths or protected policy imports. Install them to
an explicit WSL location with:

```bash
codex-custom/tooling/install-session-helpers.sh \
  --bin-dir "$HOME/.local/bin" \
  --lib-dir "$HOME/.local/lib/codex-session-helpers"
```

Run `codex-custom/tooling/test-tooling.sh` to validate shell syntax and the
read-only/helper unit tests.

macOS (checked 2026-11-14, Codex 0.167.2): the helpers install, but 8 of the 60
helper tests fail there because the status probes are Linux-only (`/proc/locks`,
WSL paths). Treat their macOS availability output as unreliable; on macOS use
`general/tools/agent-bridge/send_to_tty.sh` to reach Codex sessions. The helpers inspect or queue session state only;
they do not grant authorization or bypass the collaboration policy.

## Exclusions

Credentials, responsibility policy and hooks, session databases/history,
handover records, logs, receipts, plugin state, private runtime artifacts,
temporary snapshot debris, active release files, and native Windows settings
are intentionally excluded. The appearance-only settings remain in the
separate [`../style/codex-focus/`](../style/codex-focus/) bundle.
