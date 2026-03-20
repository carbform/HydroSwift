#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "[HydroSwift] Upgrading pip in the active Python environment..."
python -m pip install --upgrade pip

echo "[HydroSwift] Installing HydroSwift in editable mode..."
python -m pip install -e .

echo "[HydroSwift] Verifying the CLI entrypoint..."
hyswift --version

echo "[HydroSwift] Installation complete. Use 'hyswift --help' to get started."
