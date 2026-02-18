# AGENTS.md

This file provides guidance to coding agents (Claude Code, Codex, Cursor etc.) when working with code in this repository.

## What is Blurt

On-device voice-to-text for macOS Apple Silicon. Single-file Python app - hold right ⌘, speak, release, text pastes at cursor. Uses MLX Whisper locally, no cloud/API.

## Commands

```bash
# Dev install
uv pip install -e ".[dev]"

# Run
blurt

# Tests
pytest
pytest tests/test_blurt.py::test_hallucination_empty_segments  # single test

# Lint
ruff check .
ruff format .

# Release (tags + pushes, triggers PyPI publish via CI)
./release.sh 0.5.0
```

Requires `portaudio` system dep (`brew install portaudio`).

## Architecture

Single package: `blurt/__init__.py` contains everything. No submodules.

**Flow:** `main()` → starts pynput keyboard listener → `on_press`/`on_release` detect shortcut hold → `start_recording()` opens sounddevice stream → `stop_recording()` concatenates audio buffer, saves WAV to `~/.blurt/audio/`, transcribes via `mlx_whisper.transcribe()`, pastes via pbcopy+osascript, logs to `~/.blurt/blurts.jsonl`.

**Key design details:**
- Model (`mlx-community/whisper-large-v3-turbo`) is lazy-loaded on first use and pre-warmed in background thread at startup
- Transcription paste works by saving/restoring clipboard (pbcopy/pbpaste) and simulating ⌘V via osascript
- Hallucination detection (`_is_hallucination`) filters out silence/repetitive outputs using `no_speech_prob`, `avg_logprob`, and `compression_ratio` from Whisper segments
- Global mutable state (`recording`, `audio_buffer`, `stream`, etc.) protected by `threading.Lock`
- Versioning via `setuptools-scm` (git tags), no hardcoded version
- Sound feedback files bundled in `blurt/sounds/*.mp3`

## CLI Subcommands

`blurt` (run), `blurt add <phrase>`, `blurt rm <phrase>`, `blurt vocab` (list words), `blurt log` (view transcripts), `blurt upgrade` (self-update via pipx).

## Vocab

`~/.blurt/vocab.txt` - one word/phrase per line. Joined into `initial_prompt` for `mlx_whisper.transcribe()` to bias recognition.

## Conventions

- Line length: 120 (ruff)
- Ruff rules: E, F, I (with E402 ignored in `blurt/__init__.py` for delayed imports)
- Tests use `monkeypatch` to swap module-level paths (`JSONL_PATH`, etc.) with `tmp_path`
