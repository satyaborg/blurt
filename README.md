# Blurt

Talk, don't type.

![demo](https://raw.githubusercontent.com/satyaborg/blurt/main/demo.gif)

Hold the right cmd ⌘, speak and release - text appears wherever your cursor is. Runs on-device on macOS Apple Silicon. No cloud, no API keys and forever free.

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.10+

## Install

```bash
pipx install blurt
```

Requires [pipx](https://pipx.pypa.io/) (`brew install pipx`).

Update to latest: `pipx upgrade blurt`

First run downloads the Whisper model (~1.6 GB).

macOS will prompt you to grant your terminal:
- **Microphone** access
- **Accessibility** access (System Settings → Privacy & Security)

## Vocab

Add words Whisper often gets wrong (names, jargon, acronyms):

```bash
blurt vocab add Claude Code
blurt vocab                  # list
blurt vocab rm Claude Code    # remove
```

Stored in `~/.blurt/vocab.txt`, one per line.

## Contributing

```bash
git clone https://github.com/satyaborg/blurt.git
cd blurt
pipx install . --force
```

This installs the local version of blurt. After making changes, re-run `pipx install . --force` to test them.

## Privacy

Your audio never leaves your Mac. Everything — recording, transcription, model inference — runs locally. No network calls, no telemetry, no accounts.

## License

MIT
