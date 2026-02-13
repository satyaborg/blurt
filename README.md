# Blurt

Talk, don't type.

Hold the right cmd ⌘, speak and release - text appears wherever your cursor is. Runs on-device via [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) on macOS Apple Silicon. No cloud, no API keys and forever free.

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.10+

## Install

```bash
pipx install blurt
```

Requires [pipx](https://pipx.pypa.io/) (`brew install pipx`).

First run downloads the Whisper model (~1.6 GB).

macOS will prompt you to grant your terminal:
- **Microphone** access
- **Accessibility** access (System Settings → Privacy & Security)

## License

MIT
