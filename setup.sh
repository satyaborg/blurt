#!/bin/bash
# Dev setup for blurt on macOS Apple Silicon
set -e

echo "=== Blurt Dev Setup ==="

# Check Apple Silicon
if [[ $(uname -m) != "arm64" ]]; then
    echo "Warning: This is optimized for Apple Silicon (M1/M2/M3/M4)"
fi

# Install system deps
if ! brew list portaudio &>/dev/null; then
    echo "Installing portaudio via Homebrew..."
    brew install portaudio
fi

# Create venv and install
python3 -m venv ~/.blurt-venv
source ~/.blurt-venv/bin/activate
pip install --upgrade pip
pip install -e .

echo ""
echo "=== Setup complete ==="
echo ""
echo "Activate the venv:  source ~/.blurt-venv/bin/activate"
echo "Run:                blurt"
echo ""
echo "First run will download the Whisper large-v3-turbo model (~1.6 GB)."
echo "Grant Accessibility permissions to Terminal/iTerm when prompted."
