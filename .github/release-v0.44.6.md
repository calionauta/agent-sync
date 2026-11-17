## v0.44.6-alpha (2026-11-17)

### Features
- ✨ `agent-sync backup --yes` (`-y`): skip the confirmation prompt and push
  immediately. `pull` had `--force` and `skills prune` had `--yes`, while
  `backup` forced an interactive `[Enter] push / [q] quit` that scripts had to
  defeat by piping a newline into it.

### Fixes
- 🐛 `agent-sync diff` is implemented for real. It was a stub — it printed bare
  `Skills Diff:` / `Configs Diff:` headers above `# Show skills diff` comments
  while being advertised in the top-level help. It now renders what `backup`
  would push (shared `group_changed_files` / `_render_change_groups`), honours
  `--skills` / `--configs` on the *output* (not only on staging), and adds
  `--exit-code` for CI gates (`git diff --exit-code` semantics).
- 🐛 `agent-sync push` exists again, as an alias of `backup`. The orphan
  warning, the setup wizard, `sync.py` and `AGENTS.md` all told users to run
  `agent-sync push` / `agent-sync push --prune`, but only `backup` was
  registered — every one of those pointers raised `Error: No such command
  'push'`. The smoke tests that invoked `push` had been passing vacuously
  (a missing command prints no `TypeError` either).
- 🐛 `skills audit` no longer contradicts its own table. The header counted
  `report.hub_count` / `repo_count` before `skills_exclude` filtering, so a real
  hub read "116 in hub, 79 in repo" above 81 rows. Counts now derive from the
  rendered rows, the number hidden by `skills_exclude` is shown explicitly, and
  `--json` reports the same numbers plus `hidden_count`.
- 🐛 One definition of "skill". `skills_audit._list_hub_skills()` accepted any
  directory while `sync.py` required a `SKILL.md`. Directories without
  `SKILL.md` can never be pushed (git does not track empty directories), so they
  sat in the audit forever as `new (will push)`. Added
  `paths.is_skill_dir()` and used it in the audit on both sides (repo side via
  `git ls-tree -r`, so a nested `references/SKILL.md` does not register), in
  `status`, in the `skills list` TUI, and in the "Syncing N skills" count.
- 🐛 `python -m agent_sync.cli backup` no longer reports
  `Error: No such command 'backup'`. The `BACKUP COMMAND` block sat *after* the
  `if __name__ == "__main__"` guard, so running the module directly called
  `main()` before the command was registered. The guard moved to end of file.
- 🐛 CI-only test failure (run 43958718430): the new audit-header tests patched
  `agent_sync.cli.Config`, but `audit` imports `Config` locally from `.config`,
  so the patch was ignored and the tests read the real user config. They passed
  locally only because that config sets `skills_exclude: [stelow*, degustia*,
  kata*]`; with no config (CI) all rows rendered and the assertions failed. Now
  patched at `agent_sync.config.Config`.

  Note: `_detect_orphan_skills()` was intentionally left name-based. It feeds
  `--prune`, which removes skills from the repository; requiring `SKILL.md`
  there would let an empty local directory delete the only copy of a skill.

### Docs
- 📚 Full help lists the real `skills` subcommands
  (`list | audit | explain | prune | centralize`) instead of `list |
  centralize`, and marks `backup` as `(alias: push)`.
- 📚 `share add` / `share remove` docstrings no longer teach
  `agent-sync publish add` (removed command).
- 📚 `docs/cli.md` documents `diff --exit-code`, `backup --yes` and the `push`
  alias. Edited by hand on purpose: `scripts/generate_cli_docs.py` regenerates
  the file from Click and would delete the hand-written "Vendored (pinned)
  skills" section.

### Installation
```bash
pipx upgrade agent-sync
# or
pip install --upgrade agent-sync
```

### Changelog
608 tests passing (was 585). `ruff check` and `ruff format --check` clean on
Python 3.10 → 3.14. Full suite also passes with a virgin `HOME`
(`HOME=$(mktemp -d) pytest tests/ -q`), which reproduces the CI environment
without waiting for a runner.

**Full Changelog**: https://github.com/calionauta/agent-sync/compare/v0.44.5-alpha...v0.44.6-alpha
