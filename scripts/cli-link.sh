#!/usr/bin/env bash
# Keep this machine's `agent-sync` command wired to the local source checkout.
#
# Why this exists
# ---------------
# The active CLI is an editable install: .venv/bin/agent-sync → src/agent_sync.
# Historically the PATH entry was a symlink inside /opt/homebrew/bin, which is
# the console-scripts directory of the Homebrew python. `pip uninstall
# agent-sync` (run against that python to remove a stale copy) deletes every
# script named `agent-sync` in that directory — including OUR symlink — so
# removing someone else's copy silently took the CLI off PATH.
#
# Fix: put the link in ~/.local/bin, which is first on PATH and owned by no
# python interpreter. pip uninstalls elsewhere cannot reach it.
#
# Usage
#   scripts/cli-link.sh           # install / repair the link, then verify
#   scripts/cli-link.sh --check   # verify only; exit 1 if anything is off
#
# Exit codes: 0 = CLI is correctly wired to this checkout, 1 = problem.

set -euo pipefail

CHECK_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=1 ;;
        -h | --help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRY="$ROOT/.venv/bin/agent-sync"
LINK_DIR="$HOME/.local/bin"
LINK="$LINK_DIR/agent-sync"

problems=()
notes=()

if [ ! -x "$ENTRY" ]; then
    echo "✗ missing entry point: $ENTRY" >&2
    echo "  bootstrap the venv first:" >&2
    echo "    uv venv .venv --python 3.14 && uv pip install -e '.[dev]'" >&2
    exit 1
fi

# --- 1. The PATH link -------------------------------------------------------

if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$ENTRY" ]; then
    notes+=("link ok: $LINK -> $ENTRY")
else
    if [ "$CHECK_ONLY" -eq 1 ]; then
        if [ -L "$LINK" ]; then
            problems+=("$LINK points at $(readlink "$LINK"), expected $ENTRY")
        elif [ -e "$LINK" ]; then
            problems+=("$LINK exists but is not a symlink to $ENTRY")
        else
            problems+=("$LINK is missing")
        fi
    else
        mkdir -p "$LINK_DIR"
        ln -sfn "$ENTRY" "$LINK"
        notes+=("link created: $LINK -> $ENTRY")
    fi
fi

# --- 2. Which binary does the shell actually find? --------------------------

RESOLVED=""
if command -v agent-sync >/dev/null 2>&1; then
    RESOLVED="$(command -v agent-sync)"
fi

if [ "$RESOLVED" != "$LINK" ]; then
    if [ "$CHECK_ONLY" -eq 0 ] && [ -L "$LINK" ]; then
        # We just fixed the link; the shell still needs a rehash.
        notes+=("run 'hash -r' (zsh/bash) or open a new shell to pick it up")
    fi
    if [ -z "$RESOLVED" ]; then
        problems+=("'agent-sync' is not on PATH at all")
    else
        problems+=("'agent-sync' resolves to $RESOLVED, expected $LINK")
    fi
fi

# --- 3. Version metadata vs the newest tag ----------------------------------

PY="$ROOT/.venv/bin/python"
META_VERSION=""
if [ -x "$PY" ]; then
    META_VERSION="$("$PY" -c 'import importlib.metadata as m; print(m.version("agent-sync"))' 2>/dev/null || true)"
fi

TAG="$(git -C "$ROOT" describe --tags --abbrev=0 2>/dev/null || true)"
if [ -n "$META_VERSION" ] && [ -n "$TAG" ]; then
    # v0.44.6-alpha -> 0.44.6 ; 0.44.6a0 -> 0.44.6
    tag_core="$(echo "$TAG" | sed -e 's/^v//' -e 's/-.*$//')"
    meta_core="$(echo "$META_VERSION" | sed -e 's/[ab][0-9]*$//' -e 's/\.dev.*$//')"
    if [ "$tag_core" != "$meta_core" ]; then
        msg="installed metadata says $META_VERSION but newest tag is $TAG — run: uv pip install -e ."
        if [ "$CHECK_ONLY" -eq 1 ]; then
            problems+=("$msg")
        else
            notes+=("warning: $msg")
        fi
    else
        notes+=("version ok: $META_VERSION (tag $TAG)")
    fi
fi

# --- 4. Other copies that can shadow or be shadowed -------------------------

# A pip-installed copy inside a system python. Harmless while the link is
# first on PATH, but `pip uninstall` there deletes scripts by NAME — the trap
# this script exists to avoid.
BREW_PY="$(command -v /opt/homebrew/bin/python3 2>/dev/null || true)"
if [ -n "$BREW_PY" ]; then
    BREW_COPY="$("$BREW_PY" -c 'import agent_sync; print(agent_sync.__file__)' 2>/dev/null || true)"
    if [ -n "$BREW_COPY" ]; then
        notes+=("warning: a second copy exists in the Homebrew python ($BREW_COPY); uninstalling it deletes scripts named 'agent-sync' in its bin dir")
    fi
fi

LEGACY="/opt/homebrew/bin/agent-sync"
if [ -L "$LEGACY" ]; then
    notes+=("note: legacy link still present: $LEGACY (harmless, but pip there can delete it)")
fi

# --- Report -----------------------------------------------------------------

echo "agent-sync CLI wiring — $ROOT"
echo
for n in "${notes[@]}"; do
    echo "  · $n"
done

if [ "${#problems[@]}" -gt 0 ]; then
    echo
    for p in "${problems[@]}"; do
        echo "  ✗ $p"
    done
    echo
    echo "Fix: run 'scripts/cli-link.sh' (or 'make cli-link')."
    exit 1
fi

echo
echo "✓ agent-sync is wired to this checkout${META_VERSION:+ ($META_VERSION)}"
