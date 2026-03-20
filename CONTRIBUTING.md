# Contributing to HydroSwift

Thank you for your interest in contributing to HydroSwift! We welcome contributions from everyone.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and considerate of other contributors.

## How to Contribute

### 1. Reporting Bugs
- Ensure the bug was not already reported by searching on GitHub under Issues.
- If you're unable to find an open issue addressing the problem, open a new one. Be sure to include a title and clear description, as much relevant information as possible, and a code sample or an executable test case demonstrating the expected behavior that is not occurring.

### 2. Suggesting Enhancements
- Open a new Issue and describe the enhancement clearly. Explain why this enhancement would be useful to most users.
- Provide examples of how it would be used if possible.

### 3. Submitting Pull Requests
- Fork the repository and create your branch from `main`.
- If you've added code that should be tested, add tests.
- Ensure the test suite passes (`pytest tests/`).
- Update the documentation if you change the API or add features.
- Ensure your code lints (e.g., using `flake8` or `black`).
- Open a Pull Request!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/carbform/HydroSwift.git
   cd swift
   ```

2. Install in editable mode with test dependencies (if using a virtual environment):
   ```bash
   pip install -e .
   pip install pytest
   ```

3. Run the tests to verify your setup:
   ```bash
   pytest tests/
   ```

## Architectural Guidelines

- HydroSwift is designed to be extensible. When adding a new data source, ensure it follows the pattern established by the existing WRIS and CWC integrations.
- Keep the CLI layer separate from the core business logic (e.g., `download.py`, `cwc.py`, `api.py`) to maintain a clean Python-accessible API.

Thank you for helping improve HydroSwift!
