# Public API and CLI

Python: `search -> estimate -> fetch -> load -> merge / plot` (see [Python API Guide](PYTHON_API_GUIDE.md)).

CLI: `hyswift search | get | show | merge | plot | rsms` (see [CLI Usage Guide](CLI_USAGE_GUIDE.md)).

Both are thin layers over `swift_app/engine.py`: one catalog schema, one status model, one manifest.
