#!/usr/bin/env python3
"""
Blurt - Talk to your coding agents.

On-device voice-to-text for macOS Apple Silicon.
Press the shortcut to start, then press it again to stop - text appears at your cursor.
Powered by MLX. No cloud, no API keys.

Homepage: https://github.com/satyaborg/blurt
License: MIT
"""

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.error import URLError
from urllib.request import urlopen

import numpy as np
import sounddevice as sd
from pynput import keyboard

_mr_lib = None
try:
    _mr_lib = ctypes.cdll.LoadLibrary("/System/Library/PrivateFrameworks/MediaRemote.framework/MediaRemote")
    _mr_lib.MRMediaRemoteSendCommand.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    _mr_lib.MRMediaRemoteSendCommand.restype = ctypes.c_bool
except OSError:
    pass

_IS_AUDIO_ACTIVE_SWIFT = """\
import Foundation
import CoreAudio
var propAddr = AudioObjectPropertyAddress(
    mSelector: kAudioHardwarePropertyDefaultOutputDevice,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
)
var defaultDev: AudioDeviceID = 0
var size = UInt32(MemoryLayout<AudioDeviceID>.size)
AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &propAddr, 0, nil, &size, &defaultDev)
propAddr.mSelector = kAudioDevicePropertyDeviceIsRunningSomewhere
var isRunning: UInt32 = 0
size = UInt32(MemoryLayout<UInt32>.size)
AudioObjectGetPropertyData(defaultDev, &propAddr, 0, nil, &size, &isRunning)
exit(isRunning > 0 ? 0 : 1)
"""

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
ModelBackend = Literal["qwen", "whisper"]


class ModelModeConfig(TypedDict):
    repo: str
    label: str
    backend: ModelBackend


MODEL_MODES: dict[str, ModelModeConfig] = {
    "fast": {
        "repo": "mlx-community/whisper-base-mlx",
        "label": "lower latency",
        "backend": "whisper",
    },
    "accurate": {
        "repo": "mlx-community/whisper-large-v3-turbo",
        "label": "best Whisper accuracy",
        "backend": "whisper",
    },
    "qwen": {
        "repo": "mlx-community/Qwen3-ASR-1.7B-8bit",
        "label": "experimental Qwen accuracy",
        "backend": "qwen",
    },
}
DEFAULT_MODEL_MODE = "fast"
SHORTCUT = {keyboard.Key.cmd_r}  # Right Cmd only. Alt: {keyboard.Key.cmd, keyboard.Key.shift}
SAMPLE_RATE = 16000
CHANNELS = 1
MEDIA_RESUME_DELAY_S = 2.0
VAD_LEADING_MARGIN_FRAMES = 2
VAD_TRAILING_MARGIN_FRAMES = 8
BLURT_DIR = Path.home() / ".blurt"
JSONL_PATH = BLURT_DIR / "blurts.jsonl"
AUDIO_DIR = BLURT_DIR / "audio"
VOCAB_PATH = BLURT_DIR / "vocab.txt"
SOUNDS_DIR = Path(__file__).parent / "sounds"
CONFIG_PATH = BLURT_DIR / "config.json"
LEGACY_CONFIG_PATH = BLURT_DIR / "config.toml"
CLIPBOARD_PASTE_SETTLE_S = 0.05
CLIPBOARD_RESTORE_DELAY_S = 0.05
PASTE_RETRY_DELAY_S = 0.2
PROMPT_MAX_CHARS = 700  # stay well under Whisper's prompt window
PROMPT_MAX_KEYWORD_CHARS = 420
PROMPT_MAX_FILES = 32
CODING_HINT_TERMS = (
    "python",
    "pytest",
    "ruff",
    "uv",
    "__init__.py",
    "pyproject.toml",
    "README.md",
    "AGENTS.md",
    "JSONL",
    "TOML",
    "CLI",
    "snake_case",
    "camelCase",
    "Codex",
    "Cursor",
    "Claude Code",
)

# --- Supported transcription languages ---
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
def _default_config() -> dict:
    return {
        "language": "en",
        "model_mode": DEFAULT_MODEL_MODE,
        "pause_media": True,
    }


def _load_legacy_config() -> dict:
    """Load legacy TOML config if present."""
    if not LEGACY_CONFIG_PATH.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            config = {}
            for line in LEGACY_CONFIG_PATH.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    config[k.strip()] = v.strip().strip('"').strip("'")
            return config
    try:
        return tomllib.loads(LEGACY_CONFIG_PATH.read_text())
    except Exception:
        return {}


def _load_config() -> dict:
    """Load config from ~/.blurt/config.json, creating it if needed."""
    defaults = _default_config()
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            if isinstance(data, dict):
                config = defaults.copy()
                config.update(data)
                return config
            return defaults
        except Exception:
            return defaults

    legacy_config = _load_legacy_config()
    config = defaults.copy()
    config.update(legacy_config)
    if legacy_config and "model_mode" not in legacy_config:
        # Preserve existing behavior for upgrades from pre-mode installs.
        config["model_mode"] = "accurate"
    try:
        ensure_dirs()
        CONFIG_PATH.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    except Exception:
        pass
    return config


def _get_language() -> str:
    """Get configured language from config, defaulting to 'en'."""
    config = _load_config()
    lang = config.get("language", "en")
    if lang not in SUPPORTED_LANGUAGES:
        console.print(f"  [yellow]Unknown language '{lang}' in config, using 'en'[/yellow]")
        return "en"
    return lang


def _get_model_mode() -> str:
    """Get configured model mode, defaulting to the current default mode."""
    config = _load_config()
    mode = config.get("model_mode", DEFAULT_MODEL_MODE)
    if mode not in MODEL_MODES:
        console.print(f"  [yellow]Unknown model_mode '{mode}' in config, using '{DEFAULT_MODEL_MODE}'[/yellow]")
        return DEFAULT_MODEL_MODE
    return mode


def _get_model_repo() -> str:
    """Return the Hugging Face repo for the active model mode."""
    return MODEL_MODES[_get_model_mode()]["repo"]


def _get_model_backend() -> ModelBackend:
    """Return the transcription backend for the active model mode."""
    return MODEL_MODES[_get_model_mode()]["backend"]


def _get_model_language(backend: ModelBackend) -> str:
    """Return the language value expected by a transcription backend."""
    language = _get_language()
    if backend == "qwen":
        return SUPPORTED_LANGUAGES[language]
    return language


# --- State ---
recording = False
record_requested = False
start_pending = False
audio_buffer = []
pressed_keys = set()
stream = None
lock = threading.Lock()
model_lock = threading.Lock()
transcription_model: Any | None = None
loaded_model_repo: str | None = None
loaded_model_backend: ModelBackend | None = None
rec_status = None
total_words = 0
recording_session_id = 0
_last_input_device: int | str | None = None  # track default input device for hot-swap detection
_sound_cache: dict[str, tuple[np.ndarray, int]] = {}  # name -> (samples, sample_rate)
_media_paused_session_id: int | None = None


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


def _save_config(config: dict):
    """Write settings to config.json."""
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


# --- Vocab ---


def _dedupe_preserve_order(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _join_with_budget(items, max_chars: int, sep: str = ", ") -> str:
    parts = []
    total = 0
    for item in items:
        extra = len(item) if not parts else len(sep) + len(item)
        if parts and total + extra > max_chars:
            break
        if not parts and len(item) > max_chars:
            break
        parts.append(item)
        total += extra
    return sep.join(parts)


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
    """Build an initial_prompt tuned for coding-heavy dictation."""
    words = _load_vocab()
    file_names = _prompt_file_names()
    if not words and not file_names:
        return None
    if not file_names:
        return ", ".join(words)

    keywords = _dedupe_preserve_order(words + file_names + list(CODING_HINT_TERMS))
    keyword_tail = _join_with_budget(keywords, PROMPT_MAX_KEYWORD_CHARS)
    examples = _coding_prompt_examples(file_names)

    prompt = " ".join(examples + ([keyword_tail] if keyword_tail else []))
    return prompt[:PROMPT_MAX_CHARS].rstrip(" ,.")


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


def _prompt_file_names() -> list[str]:
    """Choose a capped, coding-relevant set of file names for Whisper prompting."""
    names = _file_basenames()
    if not names:
        return []

    ranked = list(enumerate(names))

    def _priority(entry: tuple[int, str]) -> tuple[int, int]:
        index, name = entry
        lower = name.lower()
        score = 0
        if lower in {"pyproject.toml", "package.json", "cargo.toml", "go.mod", "readme.md", "agents.md", "claude.md"}:
            score += 4
        if "test" in lower or lower.startswith("spec"):
            score += 3
        if lower.endswith(
            (
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".go",
                ".rs",
                ".swift",
                ".java",
                ".kt",
                ".rb",
                ".php",
                ".c",
                ".cc",
                ".cpp",
                ".h",
                ".hpp",
                ".cs",
                ".json",
                ".toml",
                ".yaml",
                ".yml",
                ".md",
            )
        ):
            score += 2
        if lower.startswith("__") and lower.endswith(".py"):
            score += 1
        return (-score, index)

    return [name for _, name in sorted(ranked, key=_priority)[:PROMPT_MAX_FILES]]


def _coding_prompt_examples(file_names: list[str]) -> list[str]:
    """Short transcript-style examples work better than instruction-like prompts."""
    primary = next((n for n in file_names if n.lower().endswith((".py", ".ts", ".tsx", ".js", ".jsx"))), "__init__.py")
    test_file = next((n for n in file_names if "test" in n.lower()), "test_app.py")
    config_file = next(
        (n for n in file_names if n.lower() in {"pyproject.toml", "package.json", "cargo.toml", "go.mod"}),
        "pyproject.toml",
    )
    docs_file = next((n for n in file_names if n.lower() in {"readme.md", "agents.md", "claude.md"}), "README.md")
    return [
        f"open {primary} and update the function.",
        f"add a test in {test_file} and run pytest.",
        f"check {config_file} and {docs_file}.",
    ]


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
        return any(
            file.file_name.endswith((".npz", ".safetensors"))
            for repo in cache_info.repos
            if repo.repo_id == repo_id
            for revision in repo.revisions
            for file in revision.files
        )
    except Exception:
        return False


def _create_transcription_model(repo_id: str, backend: ModelBackend) -> Any:
    """Load a transcription model without running inference."""
    if backend == "qwen":
        from mlx_audio.stt import load as load_stt_model

        return load_stt_model(repo_id)

    import mlx_whisper

    return mlx_whisper


def _qwen_system_prompt(prompt: str) -> str:
    """Turn Blurt vocabulary hints into a Qwen transcription instruction."""
    return f"Transcribe only the spoken words. Prefer these spellings for technical terms and file names: {prompt}"


def _transcribe_with_model(
    model: Any,
    backend: ModelBackend,
    repo_id: str,
    audio_data: np.ndarray,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Transcribe audio and normalize backend output."""
    language = _get_model_language(backend)
    if backend == "qwen":
        kwargs: dict[str, Any] = {
            "language": language,
            "temperature": 0.0,
        }
        if prompt:
            kwargs["system_prompt"] = _qwen_system_prompt(prompt)
        result = model.generate(audio_data, **kwargs)
        return {
            "text": str(result.text),
            "segments": list(result.segments or []),
        }

    kwargs = {
        "path_or_hf_repo": repo_id,
        "language": language,
        "condition_on_previous_text": False,
        "temperature": 0.0,
        "without_timestamps": True,
    }
    if prompt:
        kwargs["initial_prompt"] = prompt
    result = model.transcribe(audio_data, **kwargs)
    return {
        "text": str(result.get("text", "")),
        "segments": list(result.get("segments", []) or []),
    }


def _transcribe(audio_data: np.ndarray, prompt: str | None = None) -> dict[str, Any]:
    """Transcribe with the active loaded model."""
    if transcription_model is None or loaded_model_repo is None or loaded_model_backend is None:
        raise RuntimeError("transcription model is not loaded")
    return _transcribe_with_model(
        transcription_model,
        loaded_model_backend,
        loaded_model_repo,
        audio_data,
        prompt,
    )


def _warm_transcription_model(model: Any, backend: ModelBackend, repo_id: str) -> None:
    """Run minimal inference to load model weights into memory."""
    dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
    if backend == "qwen":
        model.generate(
            dummy,
            language=_get_model_language(backend),
            temperature=0.0,
            max_tokens=1,
        )
        return

    model.transcribe(
        dummy,
        path_or_hf_repo=repo_id,
        language=_get_model_language(backend),
        condition_on_previous_text=False,
        temperature=0.0,
        without_timestamps=True,
    )


def load_model():
    """Lazy-load the active transcription model on first use."""
    global loaded_model_backend, loaded_model_repo, transcription_model
    repo_id = _get_model_repo()
    backend = _get_model_backend()
    with model_lock:
        if transcription_model is None or loaded_model_repo != repo_id or loaded_model_backend != backend:
            cached = _model_is_cached(repo_id)
            if cached:
                import huggingface_hub

                huggingface_hub.utils.disable_progress_bars()
                try:
                    with console.status("  Loading..."):
                        model = _create_transcription_model(repo_id, backend)
                        _warm_transcription_model(model, backend, repo_id)
                finally:
                    huggingface_hub.utils.enable_progress_bars()
            else:
                console.print(f"  [{C_ACCENT}]Downloading {_get_model_mode()} model (first run only)...[/{C_ACCENT}]")
                model = _create_transcription_model(repo_id, backend)
                _warm_transcription_model(model, backend, repo_id)
            transcription_model = model
            loaded_model_repo = repo_id
            loaded_model_backend = backend
            _play_sound("ready")
            console.print(f"  [{C_OK}]Ready.[/{C_OK}]")
            _start_keepalive()


# Keep-alive interval (seconds) — run a tiny inference to prevent macOS from paging out model weights
_KEEPALIVE_INTERVAL = 300  # 5 minutes
_keepalive_timer: threading.Timer | None = None


def _keepalive_loop():
    """Periodically run a dummy transcription to keep the model weights in memory."""
    global _keepalive_timer
    with model_lock:
        if transcription_model is not None and loaded_model_backend is not None and loaded_model_repo is not None:
            try:
                _warm_transcription_model(transcription_model, loaded_model_backend, loaded_model_repo)
            except Exception:
                pass
    _keepalive_timer = threading.Timer(_KEEPALIVE_INTERVAL, _keepalive_loop)
    _keepalive_timer.daemon = True
    _keepalive_timer.start()


def _start_keepalive():
    """Start the periodic model keep-alive after initial load."""
    global _keepalive_timer
    if _keepalive_timer is not None:
        _keepalive_timer.cancel()
    _keepalive_timer = threading.Timer(_KEEPALIVE_INTERVAL, _keepalive_loop)
    _keepalive_timer.daemon = True
    _keepalive_timer.start()


def _play_sound(name):
    """Play a pre-loaded sound via sounddevice (no subprocess fork)."""
    entry = _sound_cache.get(name)
    if entry is not None:
        samples, sr = entry
        try:
            sd.play(samples, samplerate=sr, device=sd.default.device[1])
        except Exception:
            pass
        return
    # Fallback if sounds weren't pre-loaded
    path = SOUNDS_DIR / f"{name}.mp3"
    if path.exists():
        subprocess.Popen(["afplay", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


_MR_PLAY = 0
_MR_PAUSE = 1


def _is_audio_active():
    """Check if any audio is currently playing on the default output device."""
    bin_path = BLURT_DIR / "is_audio_active"
    if not bin_path.exists():
        src_path = BLURT_DIR / "is_audio_active.swift"
        try:
            src_path.write_text(_IS_AUDIO_ACTIVE_SWIFT)
            subprocess.run(
                ["swiftc", "-O", "-o", str(bin_path), str(src_path)],
                capture_output=True,
                timeout=60,
                check=True,
            )
        except Exception:
            return True  # assume playing if we can't check
        finally:
            src_path.unlink(missing_ok=True)
    try:
        result = subprocess.run([str(bin_path)], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return True  # assume playing if we can't check


def _pause_media(session_id: int):
    """Pause media playback if pause_media setting is enabled and audio is active."""
    global _media_paused_session_id
    if not _load_config().get("pause_media", True):
        return
    if _media_paused_session_id is not None:
        _media_paused_session_id = session_id
        return
    if _mr_lib is None:
        return
    if not _is_audio_active():
        return
    try:
        _mr_lib.MRMediaRemoteSendCommand(_MR_PAUSE, None)
        _media_paused_session_id = session_id
    except Exception:
        pass


def _resume_media(session_id: int):
    """Resume media playback if we previously paused it."""
    global _media_paused_session_id
    if _media_paused_session_id != session_id:
        return
    try:
        _mr_lib.MRMediaRemoteSendCommand(_MR_PLAY, None)
    except Exception:
        pass
    _media_paused_session_id = None


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
    global recording, record_requested, start_pending, stream, audio_buffer, rec_status, recording_session_id
    with lock:
        if recording or not record_requested:
            start_pending = False
            return
        audio_buffer = []
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32",
                    latency="low",
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
                    start_pending = False
                    record_requested = False
                    console.print(f"  [{C_REC}]Audio device unavailable[/{C_REC}]")
                    console.print(f"  [{C_DIM}]try: sudo killall coreaudiod — or replug/switch input[/{C_DIM}]")
                    return
        if not record_requested:
            start_pending = False
            if stream:
                stream.stop()
                stream.close()
                stream = None
            return
        recording = True
        start_pending = False
        recording_session_id += 1
        session_id = recording_session_id
        # Pause media after stream is running — audio captures immediately, no start delay
        _pause_media(session_id)
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


_PROMPT_ECHO_THRESHOLD = 0.8  # fraction of transcribed words found in prompt → likely echo


def _is_prompt_echo(text: str, prompt: str | None) -> bool:
    """Check if transcription is just the initial_prompt (vocab/file words) echoed back."""
    if not prompt:
        return False

    def _words(s: str) -> set[str]:
        return set(s.lower().replace(",", " ").split())

    prompt_words = _words(prompt)
    text_words = _words(text)
    if not text_words:
        return False
    overlap = text_words & prompt_words
    return len(overlap) / len(text_words) >= _PROMPT_ECHO_THRESHOLD


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


def _filename_variants(name: str) -> list[str]:
    """Generate plausible filename spellings Whisper may emit for spoken file names."""
    variants = []
    seen = set()

    def add(value: str):
        value = re.sub(r"\s+", " ", value.strip())
        if value and value not in seen:
            seen.add(value)
            variants.append(value)

    for variant in (name, _normalize_filename(name)):
        add(variant)
        spoken = variant.replace(".", " dot ").replace("_", " ").replace("-", " ")
        add(spoken)
        stem, _, ext = variant.rpartition(".")
        if stem and ext:
            stem_words = stem.replace("_", " ").replace("-", " ")
            add(f"{stem_words} {ext}")

    return variants


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
        for variant in _filename_variants(name):
            if variant not in seen_patterns:
                seen_patterns.add(variant)
                variants.append((variant, p))

    result = text
    for match_name, full_path in sorted(variants, key=lambda x: -len(x[0])):
        pattern = re.compile(rf"(?<![@/\w]){re.escape(match_name)}(?![/\w])", re.IGNORECASE)
        result = pattern.sub(f"@{full_path}", result)

    return result.strip()


def _vad_trim(audio: np.ndarray, sr: int, frame_ms: int = 30, energy_threshold: float = 0.005) -> np.ndarray:
    """Trim leading and trailing silence using energy-based voice activity detection.

    Splits audio into frames, computes RMS energy per frame, and strips silent
    frames from the start and end. Keeps a small leading margin and a larger
    trailing margin so hotkey release doesn't clip the last syllable.
    """
    frame_len = int(sr * frame_ms / 1000)
    if len(audio) < frame_len:
        return audio

    n_frames = (len(audio) + frame_len - 1) // frame_len
    energies = np.array([np.sqrt(np.mean(audio[i * frame_len : (i + 1) * frame_len] ** 2)) for i in range(n_frames)])

    # Find first and last frames above threshold
    active = np.where(energies > energy_threshold)[0]
    if len(active) == 0:
        return audio  # all silence — let downstream handle it

    start = max(0, active[0] - VAD_LEADING_MARGIN_FRAMES) * frame_len
    end = min(len(audio), (active[-1] + 1 + VAD_TRAILING_MARGIN_FRAMES) * frame_len)
    return audio[start:end]


def _persist_blurt(wav_path: Path, audio_data: np.ndarray, entry: dict):
    """Persist audio and log entry outside the transcription hot path."""
    try:
        save_wav(wav_path, audio_data)
        with open(JSONL_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def stop_recording():
    global recording, record_requested, stream, rec_status
    stop_started_at = time.monotonic()
    with lock:
        if not recording:
            return
        recording = False
        record_requested = False
        session_id = recording_session_id
        if rec_status:
            rec_status.stop()
            rec_status = None
        if stream:
            stream.stop()
            stream.close()
            stream = None

    try:
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

        ts = datetime.now(timezone.utc)
        wav_path = AUDIO_DIR / f"{ts.strftime('%Y%m%d_%H%M%S')}.wav"

        transcription_started_at = time.monotonic()
        with console.status(f"  [{C_ACCENT}]Transcribing...[/{C_ACCENT}]"):
            load_model()
            prompt = _vocab_prompt()
            with model_lock:
                result = _transcribe(audio_data, prompt)

        transcription_ms = round((time.monotonic() - transcription_started_at) * 1000)

        text = result["text"].strip()
        segments = result.get("segments", [])

        if not text or _is_hallucination(segments) or _is_prompt_echo(text, prompt):
            return

        text = _resolve_file_refs(text)

        global total_words
        word_count = len(text.split())
        total_words += word_count
        paste_transcription(text)
        latency_ms = round((time.monotonic() - stop_started_at) * 1000)

        entry = {
            "ts": ts.isoformat(),
            "text": text,
            "audio": str(wav_path),
            "duration_s": duration_s,
            "words": word_count,
            "latency_ms": latency_ms,
            "transcription_ms": transcription_ms,
        }
        threading.Thread(target=_persist_blurt, args=(wav_path, audio_data, entry), daemon=True).start()
        preview = text[:60] + ("..." if len(text) > 60 else "")
        console.print(
            f'  [{C_OK}]\u2713[/{C_OK}] "{preview}" '
            f"[{C_DIM}]{latency_ms}ms total \u2022 {transcription_ms}ms transcribe[/{C_DIM}]"
        )
    finally:
        if _media_paused_session_id == session_id:
            time.sleep(MEDIA_RESUME_DELAY_S)
        _resume_media(session_id)


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


def _restore_clipboard_later(prev: bytes):
    """Restore the previous clipboard after the paste has landed."""
    time.sleep(CLIPBOARD_RESTORE_DELAY_S)
    _set_clipboard(prev)


def paste_transcription(text: str):
    """Copy text, paste it, then restore the previous clipboard."""
    prev = _get_clipboard()
    _set_clipboard(text.encode("utf-8"))
    time.sleep(CLIPBOARD_PASTE_SETTLE_S)
    if not _simulate_paste():
        # Retry once after a short delay (works around transient osascript failures on macOS Tahoe)
        time.sleep(PASTE_RETRY_DELAY_S)
        if not _simulate_paste():
            console.print(f"  [{C_REC}]Paste failed — text is in clipboard, use ⌘V manually[/{C_REC}]")
            return
    threading.Thread(target=_restore_clipboard_later, args=(prev,), daemon=True).start()


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
    global record_requested, start_pending
    shortcut_was_pressed = SHORTCUT.issubset(pressed_keys)
    pressed_keys.add(_normalize(key))
    if shortcut_was_pressed or not SHORTCUT.issubset(pressed_keys):
        return

    should_start = False
    should_stop = False
    with lock:
        if recording:
            record_requested = False
            should_stop = True
        elif start_pending:
            record_requested = False
        else:
            record_requested = True
            start_pending = True
            should_start = True

    if should_start:
        _play_sound("on")
        threading.Thread(target=start_recording, daemon=True).start()
    elif should_stop:
        threading.Thread(target=stop_recording, daemon=True).start()


def on_release(key):
    pressed_keys.discard(_normalize(key))


def _is_pipx_install() -> bool:
    return (Path(sys.prefix) / "pipx_metadata.json").is_file()


def _upgrade_command() -> tuple[list[str], dict[str, str] | None]:
    if _is_pipx_install() and shutil.which("pipx"):
        env = os.environ | {"PIPX_HOME_ALLOW_SPACE": "1", "PIP_NO_CACHE_DIR": "false"}
        return ["pipx", "upgrade", "blurt"], env
    return [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "blurt"], None


def _is_version_installed(version: str) -> bool:
    from importlib.metadata import PackageNotFoundError

    from packaging.version import InvalidVersion, Version

    try:
        return Version(_v("blurt")) >= Version(version)
    except (InvalidVersion, PackageNotFoundError):
        return False


def _release_artifact_url(version: str) -> str | None:
    try:
        resp = urlopen(f"https://pypi.org/pypi/blurt/{version}/json", timeout=10)
        artifacts = json.loads(resp.read())["urls"]
    except (URLError, OSError, json.JSONDecodeError, KeyError):
        return None

    if not isinstance(artifacts, list):
        return None

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        url = artifact.get("url")
        filename = artifact.get("filename", "")
        if artifact.get("packagetype") == "bdist_wheel" and filename.endswith("-py3-none-any.whl"):
            return url if isinstance(url, str) else None

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        url = artifact.get("url")
        if artifact.get("packagetype") == "sdist":
            return url if isinstance(url, str) else None

    return None


def _direct_upgrade_command(version: str) -> list[str] | None:
    artifact_url = _release_artifact_url(version)
    if artifact_url is None:
        return None
    return [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", artifact_url]


def _check_update_bg():
    """Auto-upgrade in the background when a newer version exists."""
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

        cmd, env = _upgrade_command()
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if not _is_version_installed(latest):
            direct_cmd = _direct_upgrade_command(latest)
            if direct_cmd is not None:
                result = subprocess.run(direct_cmd, capture_output=True, text=True)
                if result.returncode == 0 and cmd[0] == "pipx":
                    subprocess.run(cmd, capture_output=True, text=True, env=env)

        if _is_version_installed(latest):
            console.print(
                f"  [bold {C_ACCENT}]updated to v{latest}[/bold {C_ACCENT}]; restart blurt to use the new version"
            )
        elif result.returncode == 0:
            console.print(f"  [{C_DIM}]v{latest} was not installed; update will retry on next launch[/{C_DIM}]")
        else:
            console.print(f"  [{C_DIM}]auto-update failed; run `blurt upgrade` manually[/{C_DIM}]")
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

    cmd, env = _upgrade_command()
    console.print(f"  [{C_DIM}]{' '.join(cmd)}[/{C_DIM}]\n")
    returncode = subprocess.call(cmd, env=env)
    if not _is_version_installed(latest):
        direct_cmd = _direct_upgrade_command(latest)
        if direct_cmd is not None:
            console.print(f"\n  [{C_DIM}]installing v{latest} from its PyPI release artifact[/{C_DIM}]\n")
            returncode = subprocess.call(direct_cmd)
            if returncode == 0 and cmd[0] == "pipx":
                subprocess.call(cmd, env=env)

    if _is_version_installed(latest):
        returncode = 0
    elif returncode == 0:
        console.print(f"\n  [red]v{latest} was not installed; run `blurt upgrade` again.[/red]\n")
        returncode = 1
    sys.exit(returncode)


def cmd_mode():
    """Show or set the active model mode."""
    if len(sys.argv) >= 3 and sys.argv[2] in MODEL_MODES:
        mode = sys.argv[2]
        _set_mode(mode)
        repo = MODEL_MODES[mode]["repo"]
        console.print(f"  [{C_OK}]✓[/{C_OK}] Mode: {mode}")
        console.print(f"  [{C_DIM}]{repo.split('/')[-1]}[/{C_DIM}]")
        return

    if len(sys.argv) >= 3:
        console.print(f"  [red]unknown mode:[/red] {sys.argv[2]}")
        console.print(f"  [{C_DIM}]Usage: blurt mode fast|accurate|qwen[/{C_DIM}]")
        sys.exit(1)

    mode = _get_model_mode()
    repo = _get_model_repo()
    label = MODEL_MODES[mode]["label"]
    console.print(f"  Mode: [{C_ACCENT}]{mode}[/{C_ACCENT}]")
    console.print(f"  [{C_DIM}]{repo.split('/')[-1]} • {label}[/{C_DIM}]")
    console.print(f"  [{C_DIM}]Usage: blurt mode fast|accurate|qwen[/{C_DIM}]")


def _set_mode(mode: str):
    """Persist the selected model mode."""
    config = _load_config()
    config["model_mode"] = mode
    _save_config(config)


def _apply_mode_flag() -> bool:
    """Handle quick mode-setting flags and exit after writing config."""
    if "--fast" in sys.argv:
        _set_mode("fast")
        console.print(f"  [{C_OK}]✓[/{C_OK}] Mode: fast")
        return True
    if "--accurate" in sys.argv:
        _set_mode("accurate")
        console.print(f"  [{C_OK}]✓[/{C_OK}] Mode: accurate")
        return True
    if "--qwen" in sys.argv:
        _set_mode("qwen")
        console.print(f"  [{C_OK}]✓[/{C_OK}] Mode: qwen")
        return True
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 >= len(sys.argv) or sys.argv[idx + 1] not in MODEL_MODES:
            console.print("  [red]invalid --mode[/red]")
            console.print(f"  [{C_DIM}]Usage: blurt --mode fast|accurate|qwen[/{C_DIM}]")
            sys.exit(1)
        mode = sys.argv[idx + 1]
        _set_mode(mode)
        console.print(f"  [{C_OK}]✓[/{C_OK}] Mode: {mode}")
        return True
    return False


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
    repo_id = _get_model_repo()
    mode = _get_model_mode()

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

    # 5. Transcription model cached
    if _model_is_cached(repo_id):
        console.print(f"  [{C_OK}]✓[/{C_OK}] model cached ({repo_id.split('/')[-1]})")
    else:
        console.print(f"  [yellow]![/yellow] {mode} model not cached — will download on first use")

    # 6. Config / language
    config = _load_config()
    console.print(f"  [{C_OK}]✓[/{C_OK}] mode: {mode}")
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
    console.print("    blurt                      start listening (press shortcut to toggle recording)")
    console.print("    blurt add <word/phrase>     add word to vocab for better recognition")
    console.print("    blurt rm <word/phrase>      remove word from vocab")
    console.print("    blurt vocab                 list vocab words")
    console.print("    blurt mode [fast|accurate|qwen]  choose transcription model")
    console.print("    blurt --fast|--accurate|--qwen   quick-set mode in config.json")
    console.print("    blurt --mode fast|accurate|qwen  quick-set mode in config.json")
    console.print("    blurt pause [on|off]        toggle media pause during recording")
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

    if any(arg in ("help", "--help", "-h") for arg in sys.argv[1:]):
        show_help()
        return

    if _apply_mode_flag():
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

    if len(sys.argv) >= 2 and sys.argv[1] == "mode":
        cmd_mode()
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

    if len(sys.argv) >= 2 and sys.argv[1] == "pause":
        config = _load_config()
        if len(sys.argv) >= 3 and sys.argv[2] in ("on", "off"):
            config["pause_media"] = sys.argv[2] == "on"
            _save_config(config)
            state = "on" if config["pause_media"] else "off"
            console.print(f"  [{C_OK}]\u2713[/{C_OK}] Pause media: {state}")
        else:
            state = "on" if config.get("pause_media", False) else "off"
            console.print(f"  Pause media: [{C_ACCENT}]{state}[/{C_ACCENT}]")
            console.print(f"  [{C_DIM}]Usage: blurt pause on|off[/{C_DIM}]")
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
    mode = _get_model_mode()
    repo_id = _get_model_repo()
    info.add_row("mode", f"{mode} ({MODEL_MODES[mode]['label']})")
    info.add_row("model", repo_id.split("/")[-1])
    lang = _get_language()
    lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
    info.add_row("language", f"{lang_name} ({lang})")
    home = str(Path.home())
    info.add_row("log", str(JSONL_PATH).replace(home, "~"))
    info.add_row("audio", str(AUDIO_DIR).replace(home, "~"))
    info.add_row("config", str(CONFIG_PATH).replace(home, "~"))
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

    console.print(f"\n  [{C_DIM}]ctrl+c quit \u2022 press shortcut to start/stop \u2022 {mode} mode[/{C_DIM}]\n")

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
