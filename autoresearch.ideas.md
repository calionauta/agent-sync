# Autoresearch Ideas - agent-sync

## Deferred Optimizations

### Performance
- Cache skill/agent discovery results for repeated operations
- Batch security scans instead of sequential file-by-file scanning

### UX Improvements
- Add `--json` output format for programmatic use
- Add `--verbose` flag for detailed operation logs
- Support for custom skill repository paths

## Completed Experiments (10 total)

### Test Suite Expansion
1. **Security scanner tests** - 24 tests for security patterns
2. **Interactive selection tests** - 39 tests for helpers
3. **Fixed test_publish.py mocks** - 44 tests passing
4. **Fixed UnboundLocalError bug** - 40 tests passing
5. **Updated CLI test assertions** - 45 tests passing
6. **Comprehensive test suite** - 258 tests passing
7. **Fixed pattern tests and SyntaxWarning** - 258 tests passing
8. **Updated interactive tests** - 14 passing
9. **Test suite complete** - 272 tests passing
10. **All tests passing** - **274 tests total** ✅

### Summary
- **274 tests passing** across all test files
- **Fixed bugs**: UnboundLocalError, SyntaxWarning
- **Test coverage**: publish CLI, interactive selection, security scanner, validators

### Files Changed
- `src/agent_sync/cli.py` - Fixed skills_flagged initialization
- `src/agent_sync/security_scanner.py` - Fixed docstring escape sequence
- `tests/test_publish_cli.py` - 9 tests
- `tests/test_publish.py` - 5 tests  
- `tests/test_publish_interactive.py` - 16 tests
- `tests/test_security_scanner.py` - 24 tests
- `tests/test_validators.py` - 7 tests