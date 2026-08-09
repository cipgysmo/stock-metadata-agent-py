#!/bin/bash
# Build script for macOS
set -e

echo "=== AI Stock Metadata Agent - macOS Build ==="

# Create virtual environment if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

# Build with PyInstaller
echo "Building application..."
pyinstaller --clean stock-metadata-agent.spec

echo ""
echo "=== Build Complete ==="
echo "App location: dist/AI Stock Metadata Agent.app"
