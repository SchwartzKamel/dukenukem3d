#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# tools/install_hooks.sh
# Activates Git hooks from .githooks/ by configuring git core.hooksPath.
# Run once after cloning to enable pre-commit secret scanning.

set -e

# Configure git to use .githooks directory for hooks
git config core.hooksPath .githooks

echo "Hooks activated: core.hooksPath = .githooks"
echo "Secret scanning will run on every 'git commit'"
