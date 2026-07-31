<p align="center">
  <pre align="center">
░█▀▄░█░░░█░█░█▀▄░▀█▀
░█▀▄░█░░░█░█░█▀▄░░█░
░▀▀░░▀▀▀░▀▀▀░▀░▀░░▀░
  </pre>
  <p align="center">Talk to your coding agents.</p>
  <p align="center">
    <a href="https://pypi.org/project/blurt/"><img src="https://img.shields.io/pypi/v/blurt?color=blue" alt="PyPI"></a>
    <a href="https://pepy.tech/project/blurt"><img src="https://img.shields.io/pepy/dt/blurt?color=green" alt="Downloads"></a>
    <a href="https://github.com/satyaborg/blurt/blob/main/LICENSE"><img src="https://img.shields.io/github/license/satyaborg/blurt" alt="License"></a>
  </p>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/satyaborg/blurt/main/demo.gif" alt="demo" width="600">
</p>

On-device voice-to-text for macOS. Press right **⌘**, speak, then press it again - your words go straight into Claude Code, Codex, Cursor, OpenCode or any other agent, wherever your cursor is.

## Install

```bash
brew tap satyaborg/blurt
brew install blurt
```

Or via [pipx](https://pipx.pypa.io/):

```bash
pipx install blurt
```

> Requires macOS with Apple Silicon.

First run downloads the selected transcription model once. macOS will prompt for **Microphone** and **Accessibility** access (System Settings → Privacy & Security).

## Usage

| Action | Description |
|---|---|
| Press right **⌘** | Start recording |
| Press right **⌘** again | Stop, transcribe, paste at cursor |
| **Ctrl + C** | Quit |

## Models

| Mode | Model | Use case |
|---|---|---|
| `fast` | Whisper Base | Default, lowest latency |
| `accurate` | Whisper Large v3 Turbo | Higher Whisper accuracy |
| `qwen` | Qwen3-ASR 1.7B 8-bit | Experimental accuracy mode |

```bash
blurt mode qwen       # use experimental Qwen3-ASR
blurt mode accurate   # return to Whisper Large v3 Turbo
blurt mode fast       # return to the default
```

Qwen mode downloads an approximately 2.5 GB [MLX checkpoint](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit). Custom words and repository file names are passed to Qwen as transcription context. Existing Whisper models remain available when you switch modes.

## Custom Words

Teach Blurt words it gets wrong (names, jargon, acronyms):

```bash
blurt add "Claude Code"   # add a word
blurt vocab               # list all
blurt rm "Claude Code"    # remove
```

Words are stored in `~/.blurt/vocab.txt` (one per line).

## @-mentions

Run Blurt from a git repo and spoken filenames automatically resolve to `@path/to/file` references that coding agents understand. For example, saying _"check init.py for the bug"_ becomes `check @blurt/__init__.py for the bug`.

## Transcript History

```bash
blurt log                 # view recent transcripts
```

Logs are stored in `~/.blurt/log.txt`.

## Update

```bash
blurt upgrade
```

## Troubleshooting

| Issue | Fix |
|---|---|
| "Microphone access" prompt doesn't appear | System Settings → Privacy & Security → Microphone → enable your terminal |
| "Accessibility" error | System Settings → Privacy & Security → Accessibility → enable your terminal |
| No audio / recording fails | `brew install portaudio` then restart your terminal |
| Model download stalls | Check available space in `~/.cache/huggingface/` for the selected model |

## Contributing

```bash
git clone https://github.com/satyaborg/blurt.git
cd blurt
uv pip install -e ".[dev]"
pytest
```

## Privacy

Everything runs on your Mac. No network calls, no telemetry, no data collection. Audio files are saved locally to `~/.blurt/audio/` and never leave your device.

## License

[MIT](LICENSE)
