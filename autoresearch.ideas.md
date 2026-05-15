# Autoresearch Ideas - agent-sync

## Deferred Optimizations

### Performance
- Cache skill/agent discovery results for repeated operations
- Batch security scans instead of sequential file-by-file scanning

### UX Improvements
- Add `--verbose` flag for detailed operation logs
- Support for custom skill repository paths

## Completed Experiments

### CLI --json Output (7 commands implemented)
1. `status --json` - sync status as JSON
2. `agents --json` - supported agents as JSON
3. `skills list --json` - skill list as JSON
4. `custom-agents list --json` - custom agents as JSON
5. `skills diff --json` - diff data as JSON
6. `skills reconcile --json` - reconcile data as JSON
7. `secrets list --json` - secrets as JSON

### Test Suite Expansion (31 experiments total)
- 273+ tests passing
- Security scanner, interactive selection, validators coverage

### UX Improvements
- TUI multi-select with single Enter confirmation
- CLI publish flow with interactive mode enabled
- Improved security warnings display

## Summary
- **273 tests passing** across all test files
- **14 feature_cards** (+250% from baseline)
- **7 commands** with `--json` output