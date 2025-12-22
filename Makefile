# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
.PHONY: help configure build clean install

help:
	@echo "Common targets:"
	@echo "  make configure       - Install Project dependencies"
	@echo "  make build           - Build Py Wheel and C/C++ Code"
	@echo "  make install         - Install wheel to a Python env"
	@echo "  make clean           - Remove wheel"

configure:
	bash scripts/configure.sh

build:
	bash scripts/build.sh

clean:
	rm -rf build/
	cd package && dh clean