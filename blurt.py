#!/usr/bin/env python3
"""
Blurt - Talk, don't type.

On-device speech-to-text for macOS Apple Silicon.
Hold a shortcut, speak, release — text appears at your cursor.
Powered by MLX Whisper. No cloud, no API keys.

Homepage: https://github.com/satyaborg/blurt
License: MIT
"""

import difflib
import json
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd
from pynput import keyboard
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
from importlib.metadata import version as _v

__version__ = _v("blurt")

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
SHORTCUT = {keyboard.Key.cmd_r}  # Right Cmd only. Alt: {keyboard.Key.cmd, keyboard.Key.shift}
SAMPLE_RATE = 16000
CHANNELS = 1
BLURT_DIR = Path.home() / ".blurt"
JSONL_PATH = BLURT_DIR / "blurts.jsonl"
AUDIO_DIR = BLURT_DIR / "audio"
VOCAB_PATH = BLURT_DIR / "vocabulary.txt"

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
last_pasted_text = None


def show_log(n=20):
    """Display recent blurts as a Rich table."""
    if not JSONL_PATH.exists():
        console.print(f"  [{C_DIM}]No blurts yet.[/{C_DIM}]")
        return

    entries = []
    with open(JSONL_PATH) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        console.print(f"  [{C_DIM}]No blurts yet.[/{C_DIM}]")
        return

    entries = entries[-n:]

    table = Table(border_style=C_BORDER)
    table.add_column("#", style=f"bold {C_ACCENT}", justify="right")
    table.add_column("time", style=C_DIM)
    table.add_column("text", max_width=80, no_wrap=False)
    table.add_column("dur", style=C_DIM, justify="right")
    table.add_column("words", style=C_ACCENT, justify="right")

    for i, e in enumerate(entries, 1):
        ts = datetime.fromisoformat(e["ts"]).strftime("%Y-%m-%d %H:%M:%S")
        text = e.get("text", "")
        dur = f"{e.get('duration_s', 0)}s"
        words = str(e.get("words", 0))
        table.add_row(str(i), ts, text, dur, words)

    console.print(table)


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
                with console.status("  Loading..."):
                    import mlx_whisper

                    dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
                    mlx_whisper.transcribe(dummy, path_or_hf_repo=MODEL, language="en")
                    whisper_pipe = mlx_whisper
                huggingface_hub.utils.enable_progress_bars()
            else:
                console.print(f"  [{C_ACCENT}]Downloading model (~1.6 GB, first run only)...[/{C_ACCENT}]")
                import mlx_whisper

                dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
                mlx_whisper.transcribe(dummy, path_or_hf_repo=MODEL, language="en")
                whisper_pipe = mlx_whisper
            console.print(f"  [{C_OK}]Ready.[/{C_OK}]")


def audio_callback(indata, frames, time_info, status):
    if status:
        console.print(f"Audio: {status}", style="yellow")
    audio_buffer.append(indata.copy())


# --- Vocabulary learning ---


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def _read_focused_text():
    """Read text value of the currently focused UI element via macOS Accessibility API."""
    try:
        from ApplicationServices import AXUIElementCopyAttributeValue, AXUIElementCreateSystemWide

        system = AXUIElementCreateSystemWide()
        err, focused_app = AXUIElementCopyAttributeValue(system, "AXFocusedApplication", None)
        if err or not focused_app:
            return None
        err, focused_elem = AXUIElementCopyAttributeValue(focused_app, "AXFocusedUIElement", None)
        if err or not focused_elem:
            return None
        err, value = AXUIElementCopyAttributeValue(focused_elem, "AXValue", None)
        if err:
            return None
        return str(value) if value else None
    except Exception:
        return None


def _extract_corrections(original: str, field_text: str) -> list[tuple[str, str]]:
    """Extract word-level corrections by diffing original pasted text against edited field text.

    Returns list of (wrong, right) tuples where Levenshtein distance is within threshold.
    """
    orig_words = original.split()
    field_words = field_text.split()

    corrections = []
    matcher = difflib.SequenceMatcher(None, orig_words, field_words)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "replace":
            continue
        # For each original word, find the closest match in the replacement field words
        for orig_w in orig_words[i1:i2]:
            best_dist = float("inf")
            best_match = None
            for new_w in field_words[j1:j2]:
                dist = _levenshtein(orig_w.lower(), new_w.lower())
                if dist < best_dist:
                    best_dist = dist
                    best_match = new_w
            if best_match and best_match != orig_w:
                max_len = max(len(orig_w), len(best_match))
                if max_len > 0 and best_dist / max_len < 0.5:
                    corrections.append((orig_w, best_match))
    return corrections


def _load_vocabulary() -> dict[str, str]:
    """Load vocabulary corrections from file. Returns {wrong_lower: right}."""
    vocab = {}
    if VOCAB_PATH.exists():
        for line in VOCAB_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("->")
            if len(parts) == 2:
                wrong, right = parts[0].strip(), parts[1].strip()
                vocab[wrong.lower()] = right
    return vocab


def _save_corrections(corrections: list[tuple[str, str]]):
    """Append new corrections to vocabulary file."""
    if not corrections:
        return
    existing = _load_vocabulary()
    new_entries = []
    for wrong, right in corrections:
        if wrong.lower() not in existing:
            new_entries.append(f"{wrong} -> {right}")
            existing[wrong.lower()] = right
    if new_entries:
        with open(VOCAB_PATH, "a") as f:
            for entry in new_entries:
                f.write(entry + "\n")
        console.print(f"  [{C_DIM}]learned: {', '.join(new_entries)}[/{C_DIM}]")


def _vocabulary_prompt() -> str:
    """Build initial_prompt from vocabulary for Whisper keyword boosting."""
    vocab = _load_vocabulary()
    if not vocab:
        return ""
    words = sorted(set(vocab.values()))
    return ", ".join(words)


def _check_corrections():
    """Read focused text field and diff against last pasted text to learn corrections."""
    global last_pasted_text
    if last_pasted_text is None:
        return

    field_text = _read_focused_text()
    pasted = last_pasted_text
    last_pasted_text = None

    if not field_text:
        return

    corrections = _extract_corrections(pasted, field_text)
    if corrections:
        _save_corrections(corrections)


def show_vocab():
    """Display learned vocabulary."""
    vocab = _load_vocabulary()
    if not vocab:
        console.print(f"  [{C_DIM}]No vocabulary learned yet.[/{C_DIM}]")
        console.print(f"  [{C_DIM}]Blurt learns corrections automatically as you edit transcriptions.[/{C_DIM}]")
        return

    table = Table(border_style=C_BORDER)
    table.add_column("whisper hears", style=C_DIM)
    table.add_column("corrected to", style=f"bold {C_ACCENT}")
    for wrong, right in sorted(vocab.items()):
        table.add_row(wrong, right)
    console.print(table)
    console.print(f"  [{C_DIM}]{len(vocab)} entries \u2022 {VOCAB_PATH}[/{C_DIM}]")


def start_recording():
    global recording, stream, audio_buffer, rec_status
    _check_corrections()
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
        prompt = _vocabulary_prompt()
        transcribe_kwargs = dict(
            path_or_hf_repo=MODEL,
            language="en",
            condition_on_previous_text=False,
        )
        if prompt:
            transcribe_kwargs["initial_prompt"] = prompt
        with model_lock:
            result = whisper_pipe.transcribe(audio_data, **transcribe_kwargs)

    latency_ms = round((time.monotonic() - t0) * 1000)

    text = result["text"].strip()
    segments = result.get("segments", [])

    if not text or _is_hallucination(segments):
        return

    global total_words
    word_count = len(text.split())
    total_words += word_count
    global last_pasted_text
    paste_transcription(text)
    last_pasted_text = text

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
    console.print(f'  [{C_OK}]\u2713[/{C_OK}] "{preview}" [{C_DIM}]{latency_ms}ms[/{C_DIM}]')


def save_wav(path: Path, audio: np.ndarray):
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())


def _get_clipboard():
    """Read current clipboard contents."""
    result = subprocess.run(["pbpaste"], capture_output=True)
    return result.stdout


def _set_clipboard(data: bytes):
    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    proc.communicate(data)


def paste_transcription(text: str):
    """Copy text, paste it, then restore the previous clipboard."""
    prev = _get_clipboard()
    _set_clipboard(text.encode("utf-8"))
    time.sleep(0.15)
    subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ]
    )
    time.sleep(0.1)
    _set_clipboard(prev)


# --- Shortcut handling ---
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
    pressed_keys.add(_normalize(key))
    if SHORTCUT.issubset(pressed_keys):
        if not recording:
            threading.Thread(target=start_recording, daemon=True).start()


def on_release(key):
    pressed_keys.discard(_normalize(key))
    if recording and not SHORTCUT.issubset(pressed_keys):
        threading.Thread(target=stop_recording, daemon=True).start()


def main():
    if "--version" in sys.argv:
        print(f"blurt {__version__}")
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "log":
        n = 20
        if "-n" in sys.argv:
            idx = sys.argv.index("-n")
            if idx + 1 < len(sys.argv):
                n = int(sys.argv[idx + 1])
        show_log(n)
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "vocab":
        _apply_theme()
        show_vocab()
        return

    if sys.platform != "darwin":
        print("blurt requires macOS (uses pbcopy, osascript, and MLX for Apple Silicon)")
        sys.exit(1)

    global total_words
    ensure_dirs()

    hist_words, hist_wpm, hist_count = load_stats()
    total_words = hist_words

    _KEY_NAMES = {
        "cmd": "\u2318",
        "cmd_l": "Left \u2318",
        "cmd_r": "Right \u2318",
        "ctrl": "\u2303",
        "ctrl_l": "Left \u2303",
        "ctrl_r": "Right \u2303",
        "alt": "\u2325",
        "alt_l": "Left \u2325",
        "alt_r": "Right \u2325",
        "shift": "\u21e7",
        "shift_l": "Left \u21e7",
        "shift_r": "Right \u21e7",
    }
    shortcut_str = "+".join(_KEY_NAMES.get(k.name, k.name) if hasattr(k, "name") else str(k) for k in SHORTCUT)
    logo_art = "░█▀▄░█░░░█░█░█▀▄░▀█▀\n░█▀▄░█░░░█░█░█▀▄░░█░\n░▀▀░░▀▀▀░▀▀▀░▀░▀░░▀░"
    logo = f"[{C_ACCENT}]{logo_art}[/{C_ACCENT}]\n[{C_DIM}]v{__version__}[/{C_DIM}]"

    info = Table.grid(padding=(0, 2))
    info.add_column(style=f"bold {C_ACCENT}", justify="right")
    info.add_column()
    info.add_row("shortcut", shortcut_str)
    info.add_row("model", MODEL.split("/")[-1])
    info.add_row("log", str(JSONL_PATH))
    info.add_row("audio", str(AUDIO_DIR))
    vocab = _load_vocabulary()
    info.add_row("vocab", f"{len(vocab)} words" if vocab else "learning...")

    console.print()
    console.print(Panel(logo, border_style=C_BORDER, padding=(1, 3)))
    console.print(info)

    if hist_count > 0:
        console.print(
            f"\n  [{C_ACCENT}]stats[/{C_ACCENT}]  "
            f"{hist_words} words \u2022 {hist_wpm:.0f} avg wpm \u2022 {hist_count} blurts"
        )

    console.print(f"\n  [{C_DIM}]ctrl+c quit \u2022 hold shortcut to record[/{C_DIM}]\n")

    # Pre-load model in background
    threading.Thread(target=load_model, daemon=True).start()

    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        console.print(f"\n  [{C_DIM}]bye[/{C_DIM}]")


if __name__ == "__main__":
    main()
