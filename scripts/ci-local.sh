#!/bin/bash
# CI-LOCAL: Run the same checks that GitHub Actions runs locally
# Usage: ./scripts/ci-local.sh

set -e

echo "=========================================="
echo "Running CI checks locally..."
echo "=========================================="

echo ""
echo "1. Running tests (same as GitHub Actions)..."
python3 -m pytest tests/ -v --tb=short

echo ""
echo "=========================================="
echo "All checks passed!"
echo "=========================================="