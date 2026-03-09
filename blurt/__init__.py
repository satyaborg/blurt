#!/usr/bin/env python3
"""
Blurt - Talk to your coding agents.

On-device voice-to-text for macOS Apple Silicon.
Hold a shortcut, speak, release - text appears at your cursor.
Powered by MLX Whisper. No cloud, no API keys.

Homepage: https://github.com/satyaborg/blurt
License: MIT
"""

import json
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

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

THEME = "vapor"
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
VOCAB_PATH = BLURT_DIR / "vocab.txt"
CONFIG_PATH = BLURT_DIR / "config.toml"

# --- Supported languages (Whisper large-v3-turbo) ---
SUPPORTED_LANGUAGES = {
    "en": "English",
    "zh": "Chinese",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "ko": "Korean",
    "fr": "French",
    "ja": "Japanese",
    "pt": "Portuguese",
    "tr": "Turkish",
    "pl": "Polish",
    "ca": "Catalan",
    "nl": "Dutch",
    "ar": "Arabic",
    "sv": "Swedish",
    "it": "Italian",
    "id": "Indonesian",
    "hi": "Hindi",
    "fi": "Finnish",
    "vi": "Vietnamese",
    "he": "Hebrew",
    "uk": "Ukrainian",
    "el": "Greek",
    "ms": "Malay",
    "cs": "Czech",
    "ro": "Romanian",
    "da": "Danish",
    "hu": "Hungarian",
    "ta": "Tamil",
    "no": "Norwegian",
    "th": "Thai",
    "ur": "Urdu",
    "hr": "Croatian",
    "bg": "Bulgarian",
    "lt": "Lithuanian",
    "la": "Latin",
    "mi": "Maori",
    "ml": "Malayalam",
    "cy": "Welsh",
    "sk": "Slovak",
    "te": "Telugu",
    "fa": "Persian",
    "lv": "Latvian",
    "bn": "Bengali",
    "sr": "Serbian",
    "az": "Azerbaijani",
    "sl": "Slovenian",
    "kn": "Kannada",
    "et": "Estonian",
    "mk": "Macedonian",
    "br": "Breton",
    "eu": "Basque",
    "is": "Icelandic",
    "hy": "Armenian",
    "ne": "Nepali",
    "mn": "Mongolian",
    "bs": "Bosnian",
    "kk": "Kazakh",
    "sq": "Albanian",
    "sw": "Swahili",
    "gl": "Galician",
    "mr": "Marathi",
    "pa": "Punjabi",
    "si": "Sinhala",
    "km": "Khmer",
    "sn": "Shona",
    "yo": "Yoruba",
    "so": "Somali",
    "af": "Afrikaans",
    "oc": "Occitan",
    "ka": "Georgian",
    "be": "Belarusian",
    "tg": "Tajik",
    "sd": "Sindhi",
    "gu": "Gujarati",
    "am": "Amharic",
    "yi": "Yiddish",
    "lo": "Lao",
    "uz": "Uzbek",
    "fo": "Faroese",
    "ht": "Haitian Creole",
    "ps": "Pashto",
    "tk": "Turkmen",
    "nn": "Nynorsk",
    "mt": "Maltese",
    "sa": "Sanskrit",
    "lb": "Luxembourgish",
    "my": "Myanmar",
    "bo": "Tibetan",
    "tl": "Tagalog",
    "mg": "Malagasy",
    "as": "Assamese",
    "tt": "Tatar",
    "haw": "Hawaiian",
    "ln": "Lingala",
    "ha": "Hausa",
    "ba": "Bashkir",
    "jw": "Javanese",
    "su": "Sundanese",
    "yue": "Cantonese",
}


# --- Config ---
def _load_config() -> dict:
    """Load config from ~/.blurt/config.toml. Returns empty dict if missing."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            # Fallback: parse simple key = "value" lines
            config = {}
            for line in CONFIG_PATH.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    config[k.strip()] = v.strip().strip('"').strip("'")
            return config
    try:
        return tomllib.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def _get_language() -> str:
    """Get configured language from config, defaulting to 'en'."""
    config = _load_config()
    lang = config.get("language", "en")
    if lang not in SUPPORTED_LANGUAGES:
        console.print(f"  [yellow]Unknown language '{lang}' in config, using 'en'[/yellow]")
        return "en"
    return lang


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
_last_input_device: int | str | None = None  # track default input device for hot-swap detection


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


# --- Vocab ---


def _load_vocab():
    """Load vocabulary words from vocab.txt, one per line."""
    if not VOCAB_PATH.exists():
        return []
    lines = VOCAB_PATH.read_text().strip().splitlines()
    return [line.strip() for line in lines if line.strip()]


def _save_vocab(words):
    """Write vocabulary words to vocab.txt."""
    VOCAB_PATH.write_text("\n".join(words) + "\n" if words else "")


def _vocab_prompt():
    """Build an initial_prompt string from vocab words and file names for keyword boosting."""
    words = _load_vocab()
    file_names = _file_basenames()
    combined = words + file_names
    if not combined:
        return None
    return ", ".join(combined)


def _file_basenames() -> list[str]:
    """Get unique file basenames from git index for Whisper prompting."""
    paths = _build_file_index()
    if not paths:
        return []
    seen = set()
    names = []
    for p in paths:
        name = p.rsplit("/", 1)[-1]
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def show_vocab():
    """Display current vocabulary as a Rich table."""
    words = _load_vocab()
    console.print(f"  [{C_DIM}]{str(VOCAB_PATH).replace(str(Path.home()), '~')}[/{C_DIM}]")
    if not words:
        console.print(f"  [{C_DIM}]No vocab words yet. Add with: blurt add <word>[/{C_DIM}]")
        return
    table = Table(border_style=C_BORDER)
    table.add_column("#", style=f"bold {C_ACCENT}", justify="right")
    table.add_column("word / phrase")
    for i, w in enumerate(words, 1):
        table.add_row(str(i), w)
    console.print(table)
    console.print(f"  [{C_DIM}]{len(words)} word(s)[/{C_DIM}]")


def add_vocab(phrase):
    """Add a word or phrase to the vocabulary."""
    ensure_dirs()
    words = _load_vocab()
    if phrase in words:
        console.print(f"  [{C_DIM}]Already in vocab: {phrase}[/{C_DIM}]")
        return
    words.append(phrase)
    _save_vocab(words)
    console.print(f"  [{C_OK}]\u2713[/{C_OK}] Added: {phrase}")


def rm_vocab(phrase):
    """Remove a word or phrase from the vocabulary."""
    words = _load_vocab()
    if phrase not in words:
        console.print(f"  [{C_DIM}]Not in vocab: {phrase}[/{C_DIM}]")
        return
    words.remove(phrase)
    _save_vocab(words)
    console.print(f"  [{C_OK}]\u2713[/{C_OK}] Removed: {phrase}")


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
                    mlx_whisper.transcribe(
                        dummy,
                        path_or_hf_repo=MODEL,
                        language=_get_language(),
                        condition_on_previous_text=False,
                        temperature=0.0,
                        without_timestamps=True,
                    )
                    whisper_pipe = mlx_whisper
                huggingface_hub.utils.enable_progress_bars()
            else:
                console.print(f"  [{C_ACCENT}]Downloading model (~1.6 GB, first run only)...[/{C_ACCENT}]")
                import mlx_whisper

                dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
                mlx_whisper.transcribe(
                    dummy,
                    path_or_hf_repo=MODEL,
                    language=_get_language(),
                    condition_on_previous_text=False,
                    temperature=0.0,
                    without_timestamps=True,
                )
                whisper_pipe = mlx_whisper
            console.print(f"  [{C_OK}]Ready.[/{C_OK}]")


def audio_callback(indata, frames, time_info, status):
    if status:
        console.print(f"Audio: {status}", style="yellow")
    audio_buffer.append(indata.copy())


def _refresh_audio_device():
    """Re-query sounddevice for the current default input device (handles hot-swap)."""
    global _last_input_device
    try:
        sd._terminate()
        sd._initialize()
        current = sd.default.device[0]
        if _last_input_device is not None and current != _last_input_device:
            dev_info = sd.query_devices(current)
            console.print(f"  [{C_DIM}]Audio input switched to: {dev_info['name']}[/{C_DIM}]")
        _last_input_device = current
    except Exception:
        pass


def start_recording():
    global recording, stream, audio_buffer, rec_status
    with lock:
        if recording:
            return
        recording = True
        audio_buffer = []
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32",
                    callback=audio_callback,
                )
                stream.start()
                break
            except sd.PortAudioError:
                stream = None
                if attempt == 0:
                    # Device may have changed — refresh PortAudio and retry
                    lock.release()
                    _refresh_audio_device()
                    lock.acquire()
                elif attempt < max_retries - 1:
                    console.print(f"  [{C_REC}]Reconnecting audio... ({attempt + 1}/{max_retries})[/{C_REC}]")
                    lock.release()
                    time.sleep(1)
                    lock.acquire()
                else:
                    recording = False
                    console.print(f"  [{C_REC}]Audio device unavailable[/{C_REC}]")
                    console.print(f"  [{C_DIM}]try: sudo killall coreaudiod — or replug/switch input[/{C_DIM}]")
                    return
        rec_status = console.status(f"  [{C_REC}]Listening...[/{C_REC}]")
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


# --- File reference resolution ---

_file_index: list[str] | None = None
_file_index_time: float = 0.0
_FILE_INDEX_TTL = 30  # seconds


def _build_file_index() -> list[str]:
    """Build file index from git ls-files (cached with 30s TTL)."""
    global _file_index, _file_index_time
    if _file_index is not None and (time.monotonic() - _file_index_time) < _FILE_INDEX_TTL:
        return _file_index

    try:
        result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, timeout=5)
        _file_index = [p for p in result.stdout.strip().split("\n") if p]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _file_index = []

    _file_index_time = time.monotonic()
    return _file_index


def _normalize_filename(name: str) -> str:
    """Strip leading/trailing underscores from filename stem for fuzzy matching.

    Whisper often drops underscores, so __init__.py gets transcribed as init.py.
    """
    stem, _, ext = name.rpartition(".")
    if not stem:
        return name
    return stem.strip("_") + "." + ext


def _resolve_file_refs(text: str) -> str:
    """Replace recognized filenames with @full/path for coding agent compatibility."""
    paths = _build_file_index()
    if not paths:
        return text

    # Build lookup: collect (pattern_text, full_path) for both original and normalized names
    # Longest patterns first so longer matches take priority
    variants: list[tuple[str, str]] = []
    seen_patterns: set[str] = set()
    for p in paths:
        name = p.rsplit("/", 1)[-1]
        for variant in {name, _normalize_filename(name)}:
            if variant not in seen_patterns:
                seen_patterns.add(variant)
                variants.append((variant, p))

    result = text
    for match_name, full_path in sorted(variants, key=lambda x: -len(x[0])):
        pattern = re.compile(re.escape(match_name), re.IGNORECASE)
        result = pattern.sub(f"@{full_path} ", result)

    # Collapse any double spaces introduced by trailing space in replacement
    result = re.sub(r"  +", " ", result)
    return result.strip()


def _vad_trim(audio: np.ndarray, sr: int, frame_ms: int = 30, energy_threshold: float = 0.005) -> np.ndarray:
    """Trim leading and trailing silence using energy-based voice activity detection.

    Splits audio into frames, computes RMS energy per frame, and strips silent
    frames from the start and end. Keeps a small margin (2 frames) for natural speech.
    """
    frame_len = int(sr * frame_ms / 1000)
    if len(audio) < frame_len:
        return audio

    n_frames = len(audio) // frame_len
    energies = np.array([np.sqrt(np.mean(audio[i * frame_len : (i + 1) * frame_len] ** 2)) for i in range(n_frames)])

    # Find first and last frames above threshold
    active = np.where(energies > energy_threshold)[0]
    if len(active) == 0:
        return audio  # all silence — let downstream handle it

    start = max(0, active[0] - 2) * frame_len
    end = min(n_frames, active[-1] + 3) * frame_len  # +3 for margin (2 frames after last active)
    return audio[start:end]


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

    # Trim silence from start/end for faster transcription
    audio_data = _vad_trim(audio_data, SAMPLE_RATE)
    duration_s = round(len(audio_data) / SAMPLE_RATE, 2)

    if duration_s < 0.5:
        return

    # Skip all-zero audio (CoreAudio bug on macOS Tahoe) or silence
    if np.max(np.abs(audio_data)) == 0:
        console.print(f"  [{C_REC}]Audio device returned silence — try: sudo killall coreaudiod[/{C_REC}]")
        return
    rms = np.sqrt(np.mean(audio_data**2))
    if rms < 0.003:
        return

    t0 = time.monotonic()

    ts = datetime.now(timezone.utc)
    wav_path = AUDIO_DIR / f"{ts.strftime('%Y%m%d_%H%M%S')}.wav"
    save_wav(wav_path, audio_data)

    with console.status(f"  [{C_ACCENT}]Transcribing...[/{C_ACCENT}]"):
        load_model()
        transcribe_kwargs = dict(
            path_or_hf_repo=MODEL,
            language=_get_language(),
            condition_on_previous_text=False,
            temperature=0.0,
            without_timestamps=True,
        )
        prompt = _vocab_prompt()
        if prompt:
            transcribe_kwargs["initial_prompt"] = prompt
        with model_lock:
            result = whisper_pipe.transcribe(audio_data, **transcribe_kwargs)

    latency_ms = round((time.monotonic() - t0) * 1000)

    text = result["text"].strip()
    segments = result.get("segments", [])

    if not text or _is_hallucination(segments):
        return

    text = _resolve_file_refs(text)

    global total_words
    word_count = len(text.split())
    total_words += word_count
    paste_transcription(text)

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


def _simulate_paste() -> bool:
    """Simulate Cmd+V via osascript. Returns True on success."""
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def paste_transcription(text: str):
    """Copy text, paste it, then restore the previous clipboard."""
    prev = _get_clipboard()
    _set_clipboard(text.encode("utf-8"))
    time.sleep(0.15)
    if not _simulate_paste():
        # Retry once after a short delay (works around transient osascript failures on macOS Tahoe)
        time.sleep(0.3)
        if not _simulate_paste():
            console.print(f"  [{C_REC}]Paste failed — text is in clipboard, use ⌘V manually[/{C_REC}]")
            return
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


def _check_update_bg():
    """Background update check — auto-upgrades if a newer version exists."""
    try:
        # Skip auto-upgrade for dev/editable installs
        if ".dev" in __version__ or "+" in __version__:
            return

        resp = urlopen("https://pypi.org/pypi/blurt/json", timeout=5)
        data = json.loads(resp.read())
        latest = data["info"]["version"]
        from packaging.version import Version

        if Version(latest) <= Version(__version__):
            return

        console.print(f"\n  [bold {C_ACCENT}]updating:[/bold {C_ACCENT}] v{__version__} → v{latest}...")

        if shutil.which("pipx"):
            cmd = ["pipx", "upgrade", "blurt"]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "blurt"]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            console.print(
                f"  [bold {C_ACCENT}]updated to v{latest}[/bold {C_ACCENT}] — restart blurt to use the new version"
            )
        else:
            console.print(f"  [{C_DIM}]auto-update failed — run `blurt upgrade` manually[/{C_DIM}]")
    except Exception:
        pass


def cmd_upgrade():
    """Check PyPI for a newer version and upgrade if available."""
    console.print(f"\n  [{C_DIM}]checking for updates...[/{C_DIM}]")
    try:
        resp = urlopen("https://pypi.org/pypi/blurt/json", timeout=10)
        data = json.loads(resp.read())
        latest = data["info"]["version"]
    except (URLError, OSError, json.JSONDecodeError, KeyError):
        console.print("  [red]couldn't check for updates - try manually:[/red]")
        console.print(f"  [{C_DIM}]pipx upgrade blurt[/{C_DIM}]\n")
        sys.exit(1)

    from packaging.version import Version

    if Version(latest) <= Version(__version__):
        console.print(f"  blurt [bold {C_ACCENT}]v{__version__}[/bold {C_ACCENT}] is up to date\n")
        return

    console.print(
        f"  blurt [bold {C_ACCENT}]v{__version__}[/bold {C_ACCENT}] → [bold {C_ACCENT}]v{latest}[/bold {C_ACCENT}]"
    )

    # Detect install method and upgrade
    if shutil.which("pipx"):
        cmd = ["pipx", "upgrade", "blurt"]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "blurt"]

    console.print(f"  [{C_DIM}]{' '.join(cmd)}[/{C_DIM}]\n")
    sys.exit(subprocess.call(cmd))


def _check_microphone():
    """Probe microphone access by opening a brief test stream."""
    try:
        test_stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32")
        test_stream.start()
        test_stream.stop()
        test_stream.close()
    except sd.PortAudioError as e:
        err = str(e).lower()
        if "permission" in err or "not allowed" in err or "denied" in err:
            console.print(f"  [{C_REC}]Microphone permission not granted[/{C_REC}]")
            console.print(
                f"  [{C_DIM}]System Settings → Privacy & Security → Microphone → enable your terminal[/{C_DIM}]"
            )
        else:
            console.print(f"  [{C_REC}]No audio input device available[/{C_REC}]")
            console.print(f"  [{C_DIM}]check your microphone is connected and set as default input[/{C_DIM}]")
    except Exception:
        pass


def _check_accessibility():
    """Warn if Accessibility permissions are not granted (keyboard listener will silently fail)."""
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to return name of first process'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            console.print(f"  [{C_REC}]Accessibility permission may not be granted[/{C_REC}]")
            console.print(
                f"  [{C_DIM}]System Settings → Privacy & Security → Accessibility → enable your terminal[/{C_DIM}]"
            )
            console.print(f"  [{C_DIM}]if already enabled, try: sudo tccutil reset Accessibility[/{C_DIM}]")
    except Exception:
        pass


def cmd_doctor():
    """Run health checks and report system status."""
    console.print(f"\n  [bold {C_ACCENT}]blurt doctor[/bold {C_ACCENT}]\n")
    all_ok = True

    # 1. macOS check
    if sys.platform == "darwin":
        console.print(f"  [{C_OK}]✓[/{C_OK}] macOS detected")
    else:
        console.print("  [red]✗[/red] not macOS — blurt requires macOS with Apple Silicon")
        all_ok = False

    # 2. PortAudio / sounddevice
    try:
        devices = list(sd.query_devices())
        input_devs = [d for d in devices if d["max_input_channels"] > 0]
        console.print(f"  [{C_OK}]✓[/{C_OK}] portaudio ok — {len(input_devs)} input device(s)")
        default_in = sd.query_devices(sd.default.device[0])
        console.print(f"    [{C_DIM}]default: {default_in['name']}[/{C_DIM}]")
    except Exception as e:
        console.print(f"  [red]✗[/red] portaudio error: {e}")
        console.print(f"    [{C_DIM}]try: brew install portaudio[/{C_DIM}]")
        all_ok = False

    # 3. Microphone access
    try:
        test_stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32")
        test_stream.start()
        test_stream.stop()
        test_stream.close()
        console.print(f"  [{C_OK}]✓[/{C_OK}] microphone access granted")
    except sd.PortAudioError as e:
        err = str(e).lower()
        if "permission" in err or "denied" in err:
            console.print("  [red]✗[/red] microphone permission denied")
            console.print(
                f"    [{C_DIM}]System Settings → Privacy & Security → Microphone → enable your terminal[/{C_DIM}]"
            )
        else:
            console.print(f"  [red]✗[/red] microphone unavailable: {e}")
        all_ok = False
    except Exception as e:
        console.print(f"  [red]✗[/red] microphone check failed: {e}")
        all_ok = False

    # 4. Accessibility (osascript)
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to return name of first process'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                console.print(f"  [{C_OK}]✓[/{C_OK}] accessibility permission granted")
            else:
                console.print("  [red]✗[/red] accessibility permission not granted")
                console.print(
                    f"    [{C_DIM}]System Settings → Privacy & Security → Accessibility"
                    f" → enable your terminal[/{C_DIM}]"
                )
                all_ok = False
        except Exception:
            console.print("  [yellow]?[/yellow] could not check accessibility")

    # 5. Whisper model cached
    if _model_is_cached(MODEL):
        console.print(f"  [{C_OK}]✓[/{C_OK}] model cached ({MODEL.split('/')[-1]})")
    else:
        console.print("  [yellow]![/yellow] model not cached — will download (~1.6 GB) on first use")

    # 6. Config / language
    config = _load_config()
    lang = config.get("language", "en")
    lang_name = SUPPORTED_LANGUAGES.get(lang, "Unknown")
    if lang in SUPPORTED_LANGUAGES:
        console.print(f"  [{C_OK}]✓[/{C_OK}] language: {lang} ({lang_name})")
    else:
        console.print(f"  [yellow]![/yellow] unknown language '{lang}' in config")
        all_ok = False

    # 7. Vocab
    words = _load_vocab()
    console.print(f"  [{C_OK}]✓[/{C_OK}] vocab: {len(words)} word(s)")

    # 8. Git repo (for @-mentions)
    file_count = len(_build_file_index())
    if file_count > 0:
        console.print(f"  [{C_OK}]✓[/{C_OK}] git repo: {file_count} files indexed")
    else:
        console.print(f"  [{C_DIM}]-[/{C_DIM}] no git repo (run from project dir for @-mentions)")

    # 9. Data dirs
    console.print(f"  [{C_OK}]✓[/{C_OK}] data dir: {str(BLURT_DIR).replace(str(Path.home()), '~')}")
    if AUDIO_DIR.exists():
        wav_count = len(list(AUDIO_DIR.glob("*.wav")))
        console.print(f"    [{C_DIM}]{wav_count} audio file(s)[/{C_DIM}]")

    # Summary
    if all_ok:
        console.print(f"\n  [bold {C_OK}]All checks passed![/bold {C_OK}]\n")
    else:
        console.print("\n  [bold yellow]Some checks failed — see above.[/bold yellow]\n")


def show_help():
    """Print CLI usage."""
    console.print(f"\n  [bold {C_ACCENT}]blurt[/bold {C_ACCENT}] - on-device voice-to-text for macOS\n")
    console.print("  [bold]Usage:[/bold]")
    console.print("    blurt                      start listening (hold shortcut to record)")
    console.print("    blurt add <word/phrase>     add word to vocab for better recognition")
    console.print("    blurt rm <word/phrase>      remove word from vocab")
    console.print("    blurt vocab                 list vocab words")
    console.print("    blurt log [-n N]            show recent transcriptions (default 20)")
    console.print("    blurt doctor                run health checks")
    console.print("    blurt upgrade|update        check for updates and upgrade")
    console.print("    blurt help                  show this help")
    console.print("    blurt --version             show version")
    console.print()


def main():
    if "--version" in sys.argv:
        print(f"blurt {__version__}")
        return

    if len(sys.argv) >= 2 and sys.argv[1] in ("help", "--help", "-h"):
        show_help()
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
        show_vocab()
        return

    if len(sys.argv) >= 3 and sys.argv[1] == "add":
        add_vocab(" ".join(sys.argv[2:]))
        return

    if len(sys.argv) >= 3 and sys.argv[1] == "rm":
        rm_vocab(" ".join(sys.argv[2:]))
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "doctor":
        cmd_doctor()
        return

    if len(sys.argv) >= 2 and sys.argv[1] in ("upgrade", "update"):
        cmd_upgrade()
        return

    if len(sys.argv) >= 2 and not sys.argv[1].startswith("-"):
        console.print(f"  [red]unknown command:[/red] {sys.argv[1]}")
        show_help()
        sys.exit(1)

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
    lang = _get_language()
    lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
    info.add_row("language", f"{lang_name} ({lang})")
    home = str(Path.home())
    info.add_row("log", str(JSONL_PATH).replace(home, "~"))
    info.add_row("audio", str(AUDIO_DIR).replace(home, "~"))
    vocab_count = len(_load_vocab())
    info.add_row("vocab", str(VOCAB_PATH).replace(home, "~"))

    console.print()
    console.print(Panel(logo, border_style=C_BORDER, padding=(1, 3)))
    console.print(info)

    if hist_count > 0 or vocab_count > 0:
        parts = []
        if hist_count > 0:
            parts.extend([f"{hist_words} words", f"{hist_wpm:.0f} avg wpm", f"{hist_count} blurts"])
        if vocab_count > 0:
            parts.append(f"{vocab_count} vocab")
        console.print(f"\n  [{C_ACCENT}]stats[/{C_ACCENT}]  " + " \u2022 ".join(parts))

    file_count = len(_build_file_index())
    if file_count > 0:
        msg = f"{file_count} files indexed — spoken filenames auto-resolve to @-mentions"
        console.print(f"\n  [{C_DIM}]{msg}[/{C_DIM}]")
    else:
        console.print(f"\n  [{C_DIM}]no git repo — run from a project directory to enable @-mentions[/{C_DIM}]")

    console.print(f"\n  [{C_DIM}]ctrl+c quit \u2022 hold shortcut to record[/{C_DIM}]\n")

    # Check permissions (keyboard + microphone)
    _check_accessibility()
    _check_microphone()

    # Check for updates in background
    threading.Thread(target=_check_update_bg, daemon=True).start()

    # Pre-load model in background
    threading.Thread(target=load_model, daemon=True).start()

    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        console.print(f"\n  [{C_DIM}]bye[/{C_DIM}]")


if __name__ == "__main__":
    main()
