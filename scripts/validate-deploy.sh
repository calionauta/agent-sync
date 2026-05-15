#!/bin/bash
# Pre-deployment validation script
# Run this before pushing to ensure everything is correct

set -e

echo "🔍 Validating deployment structure..."

# Check index.html exists at root
if [ ! -f "index.html" ]; then
    echo "❌ Missing index.html at root"
    exit 1
fi
echo "✅ index.html exists at root"

# Build MkDocs locally to test
echo ""
echo "📦 Building MkDocs documentation..."
python -m mkdocs build --strict --site-dir site_docs

# Check site_docs was created
if [ ! -d "site_docs" ]; then
    echo "❌ site_docs directory not created"
    exit 1
fi
echo "✅ MkDocs built successfully"

# Check site_docs has required files
required_files=("index.html" "cli/index.html" "quickstart/index.html" "protocols/dotagents/index.html" "protocols/gitagent/index.html")
for file in "${required_files[@]}"; do
    if [ ! -f "site_docs/$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
done
echo "✅ All required docs files exist"

# Simulate _site structure
echo ""
echo "🏗️ Simulating deployment structure..."
mkdir -p _site
cp index.html _site/
mkdir -p _site/docs
cp -r site_docs/* _site/docs/

# Verify structure
if [ ! -f "_site/index.html" ]; then
    echo "❌ Root index.html not copied"
    exit 1
fi

if [ ! -f "_site/docs/index.html" ]; then
    echo "❌ Docs index.html not copied"
    exit 1
fi

echo "✅ Deployment structure is valid"

# Cleanup
rm -rf _site site_docs

echo ""
echo "✅ All validations passed!"
echo "🚀 Safe to push!"