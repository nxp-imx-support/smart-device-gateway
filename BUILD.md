# Building the Smart Device Gateway Debian Package

This document provides detailed instructions for building the Debian package for the Smart Device Gateway demo application.

## Prerequisites

### System Requirements

- **Operating System**: Ubuntu/Debian-based Linux distribution
- **Network**: Internet connection for downloading dependencies

### Required Tools

- `git` - for repository management and submodule handling
- `python3` (>= 3.13) - Python interpreter
- `uv` - Modern Python package and project manager

## Quick Build

For a quick build using the provided automation, follow these steps:

```bash
# 1. Clone the repository
git clone <repository-url>
cd smart-device-gateway

# 2. Configure build environment (Run it only the first time you build the Debian package.)
make configure

# 3. Build the Debian package
make build
```

The built packages will be available in the `build/deb/` directory.

## Build Artifacts

After a successful build, you'll find the following artifacts in `build/deb/`:

- `smart-device-gateway_<version>_all.deb` - The main Debian package
- `smart-device-gateway_<version>_all.changes` - Changes file for package management

## Package Contents

The built Debian package includes:

### Installed Files

- **Python Wheel**: `/usr/share/python-wheels/smart_device_gateway-<version>-py3-none-any.whl`
- **Configuration**: `/usr/share/smart-device-gateway/config.yaml`

### Dependencies

- `rt-sdk-ara2` - Kinara Runtime SDK for ARA2
- `eiq-aaf-connector` -  REST-based server that enables LLM inference on NXP i.MX processors
> If you don't have the `rt-sdk-ara2` or `eiq-aaf-connector` packages installed, you can't install this package

## Installation

After building, install the package:

```bash
dpkg -i build/deb/smart_device_gateway_<version>_all.deb
```

## Configuration

The configuration process should be done on the `postinst` script. Please review it for detail.

## Related Documentation

- [README.md](README.md) - Usage and configuration instructions
- [Debian Policy Manual](https://www.debian.org/doc/debian-policy/) - Debian packaging guidelines
- [Python Packaging Guide](https://packaging.python.org/) - Python packaging best practices
