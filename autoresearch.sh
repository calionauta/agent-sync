#!/bin/bash
set -euo pipefail

# Run tests, capture output to temp file
python3 -m pytest --tb=short --no-header -q > /tmp/pytest_out.txt 2>&1 || true

# Parse via python
python3 << 'PYEOF'
import re

with open('/tmp/pytest_out.txt') as f:
    output = f.read()

if 'no tests ran' in output:
    print('METRIC exit_code=1')
    print('METRIC tests_passed=0')
    print('METRIC total_tests=0')
    exit(1)

m_passed = re.search(r'(\d+) passed', output)
m_failed = re.search(r'(\d+) failed', output)
m_errors = re.search(r'(\d+) errors', output)

passed = int(m_passed.group(1)) if m_passed else 0
failed = int(m_failed.group(1)) if m_failed else 0
errors = int(m_errors.group(1)) if m_errors else 0
total = passed + failed + errors

# Count LOC
import glob
loc = 0
for f in sorted(glob.glob('src/**/*.py', recursive=True)):
    with open(f) as fh:
        loc += len(fh.readlines())

print(f'METRIC exit_code={failed}')
print(f'METRIC tests_passed={passed}')
print(f'METRIC total_tests={total}')
print(f'METRIC loc={loc}')

# Print test failures
if failed > 0 or errors > 0:
    for line in output.split('\n'):
        if 'FAILED' in line:
            print(f'  FAIL: {line.strip()}')
    exit(1)
PYEOF
