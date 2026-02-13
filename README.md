# Blurt

Talk, don't type.

![demo](https://github.com/user-attachments/assets/bd4eadbf-2b45-442f-813c-0ed0a2341b7e)

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

## Privacy

Your audio never leaves your Mac. Everything — recording, transcription, model inference — runs locally. No network calls, no telemetry, no accounts.

## License

MIT
