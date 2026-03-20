# HydroSwift Installation

## Local pip installation

Clone the repository and install HydroSwift into your current Python environment:

```bash
git clone https://github.com/carbform/HydroSwift.git
cd swift
python -m pip install --upgrade pip
python -m pip install -e .
```

If you want the optional plotting and geospatial extras as well:

```bash
python -m pip install -e .[all]
```

## Verify the install

```bash
python -m hydroswift --help
hyswift --version
```

## CLI helper script

A convenience installer is included at `scripts/install_hyswift_cli.sh`.
It installs the package in editable mode and confirms the `hyswift` executable is available.

Run it with:

```bash
bash scripts/install_hyswift_cli.sh
```
