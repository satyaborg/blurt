# AGENTS.md

This file provides guidance to coding agents (Claude Code, Codex, Cursor etc.) when working with code in this repository.

## What is Blurt

On-device voice-to-text for macOS Apple Silicon. Single-file Python app - press right ⌘ to start, press it again to stop, and text pastes at the cursor. Uses Qwen3-ASR through MLX locally, no cloud/API.

## Commands

```bash
# Dev install
uv pip install -e ".[dev]"

# Run
blurt

# Tests
pytest
pytest tests/test_blurt.py::test_get_model_mode_default  # single test

# Lint
ruff check .
ruff format .

# Release (tags + pushes, triggers PyPI publish via CI)
./release.sh 0.5.0
```

Requires `portaudio` system dep (`brew install portaudio`).

## Architecture

Single package: `blurt/__init__.py` contains everything. No submodules.

**Flow:** `main()` → starts pynput keyboard listener → successive shortcut presses toggle `start_recording()` and `stop_recording()` → stopped audio is concatenated and saved to `~/.blurt/audio/` → the selected Qwen3-ASR model transcribes it → pbcopy+osascript pastes it → the transcript is logged to `~/.blurt/blurts.jsonl`.

**Key design details:**
- The fast (`Qwen3-ASR-0.6B-8bit`) and accurate (`Qwen3-ASR-1.7B-8bit`) models are lazy-loaded and pre-warmed in a background thread at startup
- Transcription paste works by saving/restoring clipboard (pbcopy/pbpaste) and simulating ⌘V via osascript
- Silence is filtered using audio amplitude and RMS thresholds; prompt echo and repetition detection filter unsafe output before paste
- Global mutable state (`recording`, `audio_buffer`, `stream`, etc.) protected by `threading.Lock`
- Versioning via `setuptools-scm` (git tags), no hardcoded version
- Sound feedback files bundled in `blurt/sounds/*.mp3`

## CLI Subcommands

`blurt` (run), `blurt add <phrase>`, `blurt rm <phrase>`, `blurt vocab` (list words), `blurt log` (view transcripts), `blurt upgrade` (self-update via pipx).

## Vocab

`~/.blurt/vocab.txt` - one word/phrase per line. Passed to Qwen as transcription context to bias recognition.

## Conventions

- Line length: 120 (ruff)
- Ruff rules: E, F, I (with E402 ignored in `blurt/__init__.py` for delayed imports)
- Tests use `monkeypatch` to swap module-level paths (`JSONL_PATH`, etc.) with `tmp_path`
- File index tests mock `_file_index` and `_file_index_time` directly to avoid `git ls-files` subprocess calls
- No integration tests requiring audio hardware or Qwen model

## @-mentions

When run from a git repo, Blurt indexes files via `git ls-files` and auto-resolves spoken filenames to `@path/to/file` in transcription output. File index cached with 30s TTL. `_resolve_file_refs()` does case-insensitive matching and handles normalized filenames (e.g., transcribing `__init__.py` as `init.py`).
