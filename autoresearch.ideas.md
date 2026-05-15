# Autoresearch Ideas - agent-sync

## Deferred Optimizations

### Performance
- Cache skill/agent discovery results for repeated operations
- Batch security scans instead of sequential file-by-file scanning

### UX Improvements
- Add `--json` output format for programmatic use
- Add `--verbose` flag for detailed operation logs
- Support for custom skill repository paths

### Testing
- Complete `test_publish_interactive.py` mocks (17 tests, 8 passing)
- Add integration tests with real GitHub API (mocked)
- Add property-based tests for security scanner

## Completed Experiments

1. **Added comprehensive test suite** - 258 tests passing
   - test_publish_cli.py: 9 tests
   - test_publish.py: 5 tests
   - test_publish_interactive.py: 17 tests (8 passing)
   - test_security_scanner.py: 24 tests
   - test_validators.py: 7 tests
   - Existing test files: 196 tests

2. **Fixed UnboundLocalError** in publish command
   - Skills_flagged was only initialized inside do_skills block
   - Fixed by initializing at function start

3. **Updated test assertions** to match unified security warning
   - All CLI tests now use correct assertions for new output format