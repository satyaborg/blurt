# macOS Tahoe Compatibility Investigation

## Summary

Blurt's unreliability on macOS Tahoe (macOS 26) is most likely caused by OS-level regressions in CoreAudio and osascript, not by Python or MLX issues. A Rust rewrite would **not** fix these problems since they are in macOS itself.

## Probable Root Causes (in order of likelihood)

### 1. CoreAudio / sounddevice instability — HIGH risk

macOS Tahoe shipped with significant CoreAudio regressions:

- **Audio devices intermittently disappear** from the system entirely
- **USB audio devices return all-zero data** (built-in mic may be unaffected, but underlying CoreAudio instability is systemic)
- Rogue Amoeba identified two critical audio bugs in 26.0; partially fixed in 26.1, but crackling/dropout issues returned in 26.3.1
- Workaround: `sudo killall coreaudiod` temporarily restores audio

In Blurt, this manifests as `sd.PortAudioError` in `start_recording()`, or worse — silent failures where audio captures silence/garbage, bypassing retry logic.

### 2. osascript paste failures — MEDIUM-HIGH risk

Blurt's paste mechanism uses `osascript` to simulate Cmd+V. On Tahoe:

- GUI app activation from command line **randomly fails** — app launches but doesn't come to foreground
- "Not allowed to send keystrokes" errors persist; may require re-granting Accessibility permissions after OS upgrade
- Scripts can return `-600` ("application not running") errors on 26.1

This means transcription completes but text never gets pasted — looks like "nothing happened."

### 3. pynput / Accessibility permissions — MEDIUM risk

pynput breaks with nearly every major macOS release due to reliance on Quartz event taps:

- Privacy & Security UI reorganized — users may think they've granted permissions but haven't
- **TCC database corruption** (predating Tahoe but persisting) can silently revoke Accessibility permissions even when they appear approved
- Nuclear fix: `sudo tccutil reset All` then re-grant permissions

### Things that are fine

- **MLX / mlx-whisper**: LOW risk. Apple's own framework, actively improved. Tahoe adds MLX support for M5.
- **pbcopy/pbpaste**: Still work. New Clipboard History is opt-in.
- **afconvert**: No evidence of removal or changes.

## Should We Rewrite in Rust + whisper.cpp?

### No — the problems are OS-level, not language-level.

#### What Rust would fix
- No portaudio dependency (cpal uses CoreAudio directly)
- No subprocess shelling (arboard/enigo replace pbcopy/osascript)
- Single binary distribution (no Python/pip/brew)
- No GIL — truly concurrent threads
- Faster startup (milliseconds vs Python import overhead)

#### What Rust would NOT fix
- **CoreAudio bugs are in the OS** — cpal uses the same broken CoreAudio
- **Accessibility permission issues are in the OS** — rdev uses the same Quartz event taps as pynput
- **Keystroke simulation permissions** — enigo uses the same Accessibility API as osascript

#### Performance goes the wrong way
- **mlx-whisper is 30-80% faster** than whisper.cpp on Apple Silicon
- On M1 Max with large-v3-turbo: mlx-whisper 2x faster (13.1s vs 26.7s)
- MLX is purpose-built for Apple Silicon unified memory; whisper.cpp's Metal support is structurally disadvantaged
- Apple continues investing in MLX — gap may widen

#### Rust ecosystem readiness

| Capability | Python (Blurt) | Rust Equivalent | Maturity |
|---|---|---|---|
| Keyboard hooks | pynput | rdev | Good |
| Audio input | sounddevice (portaudio) | cpal (CoreAudio) | Excellent (8.7M downloads) |
| Clipboard | pbcopy/pbpaste subprocess | arboard (1Password) | Good |
| Keystroke simulation | osascript subprocess | enigo | Good |
| Whisper inference | mlx-whisper | whisper-rs | Moderate (0.15.x) |

## Recommended Fixes (Python, current codebase)

1. **Zero-audio detection** — check if captured audio is all zeros before transcribing (catches CoreAudio silent-failure bug)
2. **osascript error handling + retry** — catch paste subprocess failures, retry once, or notify user to Cmd+V manually
3. **CoreAudio restart guidance** — when `sd.PortAudioError` exhausts retries, suggest `sudo killall coreaudiod`
4. **Permission check on startup** — detect if Accessibility/Input Monitoring are actually working, warn early
5. **Require macOS 26.1+** — the 26.0 audio bugs are severe enough to warrant this

## References

- Rogue Amoeba macOS Tahoe audio bug reports
- [pollen-robotics/reachy_mini#820](https://github.com/pollen-robotics/reachy_mini/issues/820) — all-zero USB audio on Tahoe
- [cpython#135675](https://github.com/python/cpython/issues/135675) — platform.mac_ver() returns 16.0 on Tahoe
- [mlx-examples#1083](https://github.com/ml-explore/mlx-examples/issues/1083) — mlx-whisper Python 3.13 install issue
- [mac-whisper-speedtest benchmarks](https://github.com/anvanvan/mac-whisper-speedtest)
- [whisper-rs](https://crates.io/crates/whisper-rs), [cpal](https://crates.io/crates/cpal), [rdev](https://crates.io/crates/rdev), [arboard](https://github.com/1Password/arboard), [enigo](https://crates.io/crates/enigo)
