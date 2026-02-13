#!/usr/bin/env python3
"""
blurt — on-device speech-to-text for macOS Apple Silicon.

Hold a hotkey, speak, release — text appears at your cursor.
Powered by MLX Whisper. No cloud, no API keys.

Homepage: https://github.com/satyaborg/blurt
License: MIT
"""

import sys
import json
import time
import wave
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd
from pynput import keyboard
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
__version__ = "0.1.0"

# --- Themes ---
THEMES = ["ocean", "vapor"]
THEME_COLORS = {
    "ocean": {
        "accent": "dodger_blue2",
        "rec": "orange1",
        "ok": "spring_green3",
        "dim": "grey58",
        "border": "dodger_blue2",
    },
    "vapor": {
        "accent": "medium_purple1",
        "rec": "hot_pink",
        "ok": "orchid1",
        "dim": "grey50",
        "border": "medium_purple1",
    },
}

THEME = "ocean"
C_ACCENT = C_REC = C_OK = C_DIM = C_BORDER = ""


def _apply_theme(name=None):
    global THEME, C_ACCENT, C_REC, C_OK, C_DIM, C_BORDER
    if name:
        THEME = name
    _t = THEME_COLORS[THEME]
    C_ACCENT = _t["accent"]
    C_REC = _t["rec"]
    C_OK = _t["ok"]
    C_DIM = _t["dim"]
    C_BORDER = _t["border"]


_apply_theme()

# --- Config ---
MODEL = "mlx-community/whisper-large-v3-turbo"  # Best accuracy. Alt: "mlx-community/whisper-base-mlx" for speed
HOTKEY = {keyboard.Key.cmd_r}  # Right Cmd only. Alt: {keyboard.Key.cmd, keyboard.Key.shift}
SAMPLE_RATE = 16000
CHANNELS = 1
BLURT_DIR = Path.home() / ".blurt"
JSONL_PATH = BLURT_DIR / "blurts.jsonl"
AUDIO_DIR = BLURT_DIR / "audio"

# --- State ---
recording = False
audio_buffer = []
pressed_keys = set()
stream = None
lock = threading.Lock()
model_lock = threading.Lock()
whisper_pipe = None
rec_status = None
total_words = 0


def load_stats():
    """Compute global stats from JSONL log."""
    total_w = 0
    total_dur = 0.0
    count = 0
    if JSONL_PATH.exists():
        with open(JSONL_PATH) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    total_w += e.get("words", 0)
                    total_dur += e.get("duration_s", 0)
                    count += 1
                except json.JSONDecodeError:
                    continue
    avg_wpm = (total_w / (total_dur / 60)) if total_dur > 0 else 0
    return total_w, avg_wpm, count


def ensure_dirs():
    BLURT_DIR.mkdir(exist_ok=True)
    AUDIO_DIR.mkdir(exist_ok=True)


def _model_is_cached(repo_id: str) -> bool:
    """Check if a HuggingFace model is already downloaded."""
    try:
        from huggingface_hub import scan_cache_dir
        cache_info = scan_cache_dir()
        return any(r.repo_id == repo_id for r in cache_info.repos)
    except Exception:
        return False


def load_model():
    """Lazy-load mlx-whisper on first use."""
    global whisper_pipe
    with model_lock:
        if whisper_pipe is None:
            cached = _model_is_cached(MODEL)
            if cached:
                import huggingface_hub
                huggingface_hub.utils.disable_progress_bars()
            with console.status(f"Loading model: {MODEL}{'' if cached else ' (first run downloads ~1.6GB)'}..."):
                import mlx_whisper
                # Warm up with empty audio to trigger download/compile
                dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
                mlx_whisper.transcribe(dummy, path_or_hf_repo=MODEL, language="en")
                whisper_pipe = mlx_whisper
            if cached:
                import huggingface_hub
                huggingface_hub.utils.enable_progress_bars()
            console.print("  [bold green]Model ready.[/bold green]")


def audio_callback(indata, frames, time_info, status):
    if status:
        console.print(f"Audio: {status}", style="yellow")
    audio_buffer.append(indata.copy())


def start_recording():
    global recording, stream, audio_buffer, rec_status
    with lock:
        if recording:
            return
        recording = True
        audio_buffer = []
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=audio_callback,
        )
        stream.start()
        rec_status = console.status(f"  [{C_REC}]Recording...[/{C_REC}]")
        rec_status.start()


def _is_hallucination(segments):
    """Detect Whisper hallucinations from segment-level signals."""
    if not segments:
        return False
    # All segments are likely silence
    if all(s.get("no_speech_prob", 0) > 0.6 for s in segments):
        return True
    # Low confidence + high compression = repetitive hallucination
    for s in segments:
        if s.get("avg_logprob", 0) < -1.0 and s.get("compression_ratio", 0) > 2.4:
            return True
    return False


def stop_recording():
    global recording, stream, rec_status
    with lock:
        if not recording:
            return
        recording = False
        if rec_status:
            rec_status.stop()
            rec_status = None
        if stream:
            stream.stop()
            stream.close()
            stream = None

    if not audio_buffer:
        return

    audio_data = np.concatenate(audio_buffer, axis=0).flatten()
    duration_s = round(len(audio_data) / SAMPLE_RATE, 2)

    if duration_s < 0.5:
        return

    t0 = time.monotonic()

    ts = datetime.now(timezone.utc)
    wav_path = AUDIO_DIR / f"{ts.strftime('%Y%m%d_%H%M%S')}.wav"
    save_wav(wav_path, audio_data)

    with console.status(f"  [{C_ACCENT}]Transcribing...[/{C_ACCENT}]"):
        load_model()
        with model_lock:
            result = whisper_pipe.transcribe(
                audio_data,
                path_or_hf_repo=MODEL,
                language="en",
                condition_on_previous_text=False,
            )

    latency_ms = round((time.monotonic() - t0) * 1000)

    text = result["text"].strip()
    segments = result.get("segments", [])

    if not text or _is_hallucination(segments):
        return

    global total_words
    word_count = len(text.split())
    total_words += word_count
    copy_to_clipboard(text)
    paste_to_active()

    entry = {
        "ts": ts.isoformat(),
        "text": text,
        "audio": str(wav_path),
        "duration_s": duration_s,
        "words": word_count,
    }
    with open(JSONL_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    preview = text[:60] + ("..." if len(text) > 60 else "")
    console.print(
        f"  [{C_OK}]\u2713[/{C_OK}] \"{preview}\" "
        f"[{C_DIM}]{latency_ms}ms[/{C_DIM}]"
    )


def save_wav(path: Path, audio: np.ndarray):
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())


def copy_to_clipboard(text: str):
    process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    process.communicate(text.encode("utf-8"))


def paste_to_active():
    """Simulate Cmd+V to paste into whatever input is focused."""
    time.sleep(0.15)
    subprocess.run([
        "osascript", "-e",
        'tell application "System Events" to keystroke "v" using command down',
    ])


# --- Hotkey handling ---
# pynput reports cmd_l/cmd_r/shift_l/shift_r specifically; normalize to generic keys
_KEY_NORMALIZE = {
    keyboard.Key.cmd_l: keyboard.Key.cmd,
    keyboard.Key.shift_l: keyboard.Key.shift,
    keyboard.Key.shift_r: keyboard.Key.shift,
    keyboard.Key.ctrl_l: keyboard.Key.ctrl,
    keyboard.Key.ctrl_r: keyboard.Key.ctrl,
    keyboard.Key.alt_l: keyboard.Key.alt,
    keyboard.Key.alt_r: keyboard.Key.alt,
}


def _normalize(key):
    return _KEY_NORMALIZE.get(key, key)


def on_press(key):
    if key == keyboard.Key.esc:
        console.print(f"\n  [{C_DIM}]bye[/{C_DIM}]")
        return False
    pressed_keys.add(_normalize(key))
    if HOTKEY.issubset(pressed_keys):
        if not recording:
            threading.Thread(target=start_recording, daemon=True).start()


def on_release(key):
    pressed_keys.discard(_normalize(key))
    if recording and not HOTKEY.issubset(pressed_keys):
        threading.Thread(target=stop_recording, daemon=True).start()


def main():
    if "--version" in sys.argv:
        print(f"blurt {__version__}")
        return

    if sys.platform != "darwin":
        print("blurt requires macOS (uses pbcopy, osascript, and MLX for Apple Silicon)")
        sys.exit(1)

    global total_words
    ensure_dirs()

    hist_words, hist_wpm, hist_count = load_stats()
    total_words = hist_words

    _KEY_NAMES = {
        "cmd": "\u2318", "cmd_l": "Left \u2318", "cmd_r": "Right \u2318",
        "ctrl": "\u2303", "ctrl_l": "Left \u2303", "ctrl_r": "Right \u2303",
        "alt": "\u2325", "alt_l": "Left \u2325", "alt_r": "Right \u2325",
        "shift": "\u21e7", "shift_l": "Left \u21e7", "shift_r": "Right \u21e7",
    }
    hotkey_str = "+".join(
        _KEY_NAMES.get(k.name, k.name) if hasattr(k, "name") else str(k)
        for k in HOTKEY
    )
    logo_art = (
        "░█▀▄░█░░░█░█░█▀▄░▀█▀\n"
        "░█▀▄░█░░░█░█░█▀▄░░█░\n"
        "░▀▀░░▀▀▀░▀▀▀░▀░▀░░▀░"
    )
    logo = f"[{C_ACCENT}]{logo_art}[/{C_ACCENT}]\n[{C_DIM}]v{__version__}[/{C_DIM}]"

    info = Table.grid(padding=(0, 2))
    info.add_column(style=f"bold {C_ACCENT}", justify="right")
    info.add_column()
    info.add_row("hotkey", hotkey_str)
    info.add_row("model", MODEL.split("/")[-1])
    info.add_row("log", str(JSONL_PATH))
    info.add_row("audio", str(AUDIO_DIR))

    console.print()
    console.print(Panel(logo, border_style=C_BORDER, padding=(1, 3)))
    console.print(info)

    if hist_count > 0:
        console.print(
            f"\n  [{C_ACCENT}]stats[/{C_ACCENT}]  "
            f"{hist_words} words \u2022 {hist_wpm:.0f} avg wpm \u2022 {hist_count} blurts"
        )

    console.print(f"\n  [{C_DIM}]esc quit \u2022 hold hotkey to record[/{C_DIM}]\n")

    # Pre-load model in background
    threading.Thread(target=load_model, daemon=True).start()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
