#!/bin/bash

# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
set -e


# Update git submodules if needed
echo "Updating git submodules..."
git submodule update --init --recursive

# Get the current directory name for package naming
PACKAGE_NAME="smart-device-gateway"
CURRENT_DIR=$(pwd)

# Build the Debian package
echo "Building Debian package..."
cd ./package/
dpkg-buildpackage -us -uc -A

# Create output directory if it doesn't exist
cd ..
mkdir -p build/deb

# Move all output files to build/deb/
echo "Moving output files to build/deb/..."
mv -v ./${PACKAGE_NAME}_* build/deb/

echo "Build completed! Output files are in build/deb/"
ls -la build/deb/
