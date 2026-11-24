# HydroSwift Installation

## Local pip installation

Clone the repository and install HydroSwift into your current Python environment:

```bash
git clone https://github.com/carbform/HydroSwift.git
cd HydroSwift
python -m pip install --upgrade pip
python -m pip install -e .
```

If you want the optional plotting and geospatial extras as well:

```bash
python -m pip install -e .[all]
```

### Verify the install

```bash
python -m hydroswift --help
hyswift --version
```

## For Linux users

An installer for Linux is included at `scripts/install.sh`.

Run it with:

```bash
bash scripts/install.sh
```
