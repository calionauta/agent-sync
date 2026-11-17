## v0.44.7-alpha (2026-11-17)

### Fixes
- 🐛 `agent-sync update` no longer knows about a package index. It always ran
  `pipx upgrade agent-sync`, which for this project either did nothing or
  upgraded the *unrelated* `agent-sync` package on PyPI while printing
  `✓ Updated from 0.44.6a0 → 1.2.0`. It now classifies the install as
  `editable`, `vcs` or `installed` and acts accordingly:
  - source checkouts are never mutated — you get the exact command
    (`git pull --ff-only && uv pip install -e .`, or
    `pipx install --force "git+<url>@<tag>"`);
  - `installed` copies are reinstalled from
    `git+https://github.com/calionauta/agent-sync.git@<tag>`.

  `--check` compares the installed version against the latest GitHub release
  through `packaging.version`, so `v0.44.7-alpha` and `0.44.7a0` compare equal.
  Network failures are reported, not raised. `agent-sync version` now prints
  where the running copy came from.
- 🐛 Documentation installed the wrong package. `pipx install agent-sync`
  appeared in the README, quickstart, docs index, the `agent-sync` skill and
  the release template — all of them installing an unrelated project. Every
  snippet installs from the repository now, and the collision is stated out
  loud.
- 🐛 CI reported version `0.1.dev1`. Both workflows checked out with
  `fetch-depth: 1` and no tags, leaving `hatch-vcs` nothing to derive a version
  from. Fixed with `fetch-depth: 0`; the new `update` tests also pin
  `agent_sync.__version__` so they no longer depend on checkout depth.
- 🐛 Guarded a crash in `_install_kind`: a `direct_url.json` containing valid
  JSON that is not an object raised `AttributeError`.

### Tooling
- 🛠 `scripts/cli-link.sh` + `make doctor` / `make cli-link`: the `agent-sync`
  command used to be a symlink inside `/opt/homebrew/bin`, the console-scripts
  directory of the Homebrew python. `pip uninstall agent-sync` there deletes
  scripts by name, so removing a stale 0.42.0a0 copy took the CLI off PATH
  while the editable install was fine. The link now lives in `~/.local/bin`
  (first on PATH, owned by no interpreter) and `make doctor` verifies the shell
  actually resolves it, plus that the metadata matches the newest tag.

### Installation
```bash
# CLI, pinned to this release (the PyPI `agent-sync` is an unrelated project)
pipx install --force "git+https://github.com/calionauta/agent-sync.git@v0.44.7-alpha"
# or
uv tool install --force "git+https://github.com/calionauta/agent-sync.git@v0.44.7-alpha"
# or just the skill for AI agents
npx skills update calionauta/agent-sync -g
```

> Do **not** run `pip install agent-sync` / `pipx upgrade agent-sync`: that
> distribution name on PyPI belongs to another project.

### Changelog
635 tests passing (was 632). `ruff check` and `ruff format --check` clean on
Python 3.10 → 3.14; the suite also passes with a virgin `HOME`
(`HOME=$(mktemp -d) pytest tests/ -q`), which reproduces the CI environment.

**Full Changelog**: https://github.com/calionauta/agent-sync/compare/v0.44.6-alpha...v0.44.7-alpha
