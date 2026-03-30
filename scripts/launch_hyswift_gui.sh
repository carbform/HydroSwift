#!/bin/bash

# HydroSwift GUI Quick Start Script
# This script helps set up and launch the HydroSwift GUI application

set -e

echo "╔════════════════════════════════════════╗"
echo "║  HydroSwift GUI - Quick Start          ║"
echo "║  Version 1.0.0                         ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check Python version
echo "📦 Checking Python installation..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python version: $python_version"

# Check minimum version
major=$(echo $python_version | cut -d. -f1)
minor=$(echo $python_version | cut -d. -f2)

if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 9 ]); then
    echo "   ✗ Python 3.9+ required"
    exit 1
fi
echo "   ✓ Python version OK"

# Install dependencies
echo ""
echo "📥 Installing HydroSwift with GUI support..."
pip install -e ".[gui]" --upgrade

# Verify PyQt5
echo ""
echo "✓ Checking PyQt5..."
python3 -c "from PyQt5.QtWidgets import QApplication; print('   ✓ PyQt5 available')"

# Check HydroSwift
echo ""
echo "✓ Checking HydroSwift..."
python3 -c "import hydroswift; print('   ✓ HydroSwift available')"

# Create output directory
echo ""
echo "📂 Setting up output directory..."
mkdir -p output
echo "   ✓ output/ directory ready"

# Launch GUI
echo ""
echo "🚀 Launching HydroSwift GUI..."
echo ""
echo "If the GUI doesn't open automatically, you can:"
echo "  • Run:  hyswift-gui"
echo "  • Or:   python -m swift_app.gui"
echo ""

hyswift-gui &
wait
