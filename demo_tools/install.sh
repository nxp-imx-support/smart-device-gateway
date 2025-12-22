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

# Install espeak phonetizer
if command -v espeak-ng &> /dev/null; then
    echo "espeak-ng is already installed. Skip it..."
else
    echo "espeak-ng is not installed. Installing from source..."
    # Set variables
    VERSION="1.51"
    TARBALL="${VERSION}.tar.gz"
    URL="https://github.com/espeak-ng/espeak-ng/archive/refs/tags/${TARBALL}"
    EXTRACTED_DIR="espeak-ng-${VERSION}"

    # Download and extract
    curl -L -k -o "$TARBALL" "$URL"
    if [ $? -ne 0 ]; then
        echo "Failed to download espeak-ng source. Exiting."
        exit 1
    fi

    tar xf "$TARBALL"
    if [ $? -ne 0 ]; then
        echo "Failed to extract espeak-ng source. Exiting."
        exit 1
    fi

    cd "$EXTRACTED_DIR" || exit 1

    ./autogen.sh || true

    if [ -f ../ltmain.sh ]; then
        mv ../ltmain.sh ./ltmain.sh
    fi

    # Build
    ./autogen.sh
    ./configure --prefix=/usr \
                --with-klatt=no \
                --with-speechplayer=no \
                --with-mbrola=no \
                --with-extdict-ru=no \
                --with-extdict-cmn=yes \
                --with-extdict-yue=no

    # Install
    make -j "$(nproc)"
    if [ $? -ne 0 ]; then
        echo "Build failed. Exiting."
        exit 1
    fi

    sudo make install
    if [ $? -ne 0 ]; then
        echo "Installation failed. Exiting."
        exit 1
    fi

    # Cleanup
    cd ..
    rm -rf "$EXTRACTED_DIR" "$TARBALL"

    echo "espeak-ng installed successfully."
fi
