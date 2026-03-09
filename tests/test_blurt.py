import json
import sys
from unittest.mock import patch

import numpy as np
import pytest

import blurt

# --- _is_hallucination ---


def test_hallucination_empty_segments():
    assert blurt._is_hallucination([]) is False


def test_hallucination_high_no_speech():
    segments = [{"no_speech_prob": 0.9}, {"no_speech_prob": 0.8}]
    assert blurt._is_hallucination(segments) is True


def test_hallucination_low_confidence_high_compression():
    segments = [{"avg_logprob": -1.5, "compression_ratio": 3.0}]
    assert blurt._is_hallucination(segments) is True


def test_hallucination_normal_speech():
    segments = [{"no_speech_prob": 0.1, "avg_logprob": -0.3, "compression_ratio": 1.2}]
    assert blurt._is_hallucination(segments) is False


def test_hallucination_mixed_no_speech():
    segments = [{"no_speech_prob": 0.9}, {"no_speech_prob": 0.2}]
    assert blurt._is_hallucination(segments) is False


# --- load_stats ---


def test_load_stats_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "JSONL_PATH", tmp_path / "missing.jsonl")
    words, wpm, count = blurt.load_stats()
    assert words == 0
    assert wpm == 0
    assert count == 0


def test_load_stats_with_entries(tmp_path, monkeypatch):
    jsonl = tmp_path / "blurts.jsonl"
    entries = [
        {"words": 10, "duration_s": 3.0},
        {"words": 20, "duration_s": 6.0},
    ]
    jsonl.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    monkeypatch.setattr(blurt, "JSONL_PATH", jsonl)

    words, wpm, count = blurt.load_stats()
    assert words == 30
    assert count == 2
    assert wpm == pytest.approx(30 / (9.0 / 60))


def test_load_stats_skips_bad_json(tmp_path, monkeypatch):
    jsonl = tmp_path / "blurts.jsonl"
    jsonl.write_text('{"words": 5, "duration_s": 2.0}\nnot json\n')
    monkeypatch.setattr(blurt, "JSONL_PATH", jsonl)

    words, wpm, count = blurt.load_stats()
    assert words == 5
    assert count == 1


# --- show_log ---


def test_show_log_no_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(blurt, "JSONL_PATH", tmp_path / "missing.jsonl")
    blurt.show_log()
    captured = capsys.readouterr()
    assert "No blurts yet" in captured.out


def test_show_log_empty_file(tmp_path, monkeypatch, capsys):
    jsonl = tmp_path / "blurts.jsonl"
    jsonl.write_text("")
    monkeypatch.setattr(blurt, "JSONL_PATH", jsonl)
    blurt.show_log()
    captured = capsys.readouterr()
    assert "No blurts yet" in captured.out


def test_show_log_respects_n(tmp_path, monkeypatch, capsys):
    jsonl = tmp_path / "blurts.jsonl"
    entries = [
        {"ts": f"2025-01-01T00:00:0{i}+00:00", "text": f"entry {i}", "duration_s": 1.0, "words": 2} for i in range(5)
    ]
    jsonl.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    monkeypatch.setattr(blurt, "JSONL_PATH", jsonl)

    blurt.show_log(n=2)
    captured = capsys.readouterr()
    assert "entry 3" in captured.out
    assert "entry 4" in captured.out
    assert "entry 0" not in captured.out


# --- CLI arg parsing ---


def test_version_flag(capsys):
    with patch.object(sys, "argv", ["blurt", "--version"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "blurt" in captured.out


def test_log_subcommand(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(blurt, "JSONL_PATH", tmp_path / "missing.jsonl")
    with patch.object(sys, "argv", ["blurt", "log"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "No blurts yet" in captured.out


def test_log_n_flag(tmp_path, monkeypatch, capsys):
    jsonl = tmp_path / "blurts.jsonl"
    entries = [
        {"ts": f"2025-01-01T00:00:0{i}+00:00", "text": f"msg {i}", "duration_s": 1.0, "words": 1} for i in range(5)
    ]
    jsonl.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    monkeypatch.setattr(blurt, "JSONL_PATH", jsonl)

    with patch.object(sys, "argv", ["blurt", "log", "-n", "2"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "msg 3" in captured.out
    assert "msg 4" in captured.out


# --- _normalize ---


def test_normalize_cmd_l():
    from pynput import keyboard

    assert blurt._normalize(keyboard.Key.cmd_l) == keyboard.Key.cmd


def test_normalize_passthrough():
    from pynput import keyboard

    assert blurt._normalize(keyboard.Key.space) == keyboard.Key.space


# --- Vocab ---


def test_load_vocab_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "missing.txt")
    assert blurt._load_vocab() == []


def test_load_vocab_with_words(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("Blurt\nMLX Whisper\n\n  spaced  \n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    assert blurt._load_vocab() == ["Blurt", "MLX Whisper", "spaced"]


def test_save_vocab(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    blurt._save_vocab(["hello", "world"])
    assert vocab.read_text() == "hello\nworld\n"


def test_save_vocab_empty(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    blurt._save_vocab([])
    assert vocab.read_text() == ""


def test_vocab_prompt_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "missing.txt")
    monkeypatch.setattr(blurt, "_file_index", [])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    assert blurt._vocab_prompt() is None


def test_vocab_prompt_with_words(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("Blurt\nMLX\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    monkeypatch.setattr(blurt, "_file_index", [])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    assert blurt._vocab_prompt() == "Blurt, MLX"


def test_add_vocab(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    blurt.add_vocab("Kubernetes")
    assert "Kubernetes" in blurt._load_vocab()


def test_add_vocab_duplicate(tmp_path, monkeypatch, capsys):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("Kubernetes\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    blurt.add_vocab("Kubernetes")
    assert blurt._load_vocab() == ["Kubernetes"]
    captured = capsys.readouterr()
    assert "Already" in captured.out


def test_rm_vocab(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("Blurt\nKubernetes\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    blurt.rm_vocab("Kubernetes")
    assert blurt._load_vocab() == ["Blurt"]


def test_rm_vocab_missing(tmp_path, monkeypatch, capsys):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("Blurt\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    blurt.rm_vocab("nope")
    captured = capsys.readouterr()
    assert "Not in vocab" in captured.out


def test_vocab_cli_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "missing.txt")
    with patch.object(sys, "argv", ["blurt", "vocab"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "No vocab words yet" in captured.out


def test_vocab_cli_add(tmp_path, monkeypatch, capsys):
    vocab = tmp_path / "vocab.txt"
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "add", "MLX", "Whisper"]):
        blurt.main()
    assert "MLX Whisper" in blurt._load_vocab()


def test_vocab_cli_rm(tmp_path, monkeypatch, capsys):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("MLX Whisper\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    with patch.object(sys, "argv", ["blurt", "rm", "MLX", "Whisper"]):
        blurt.main()
    assert blurt._load_vocab() == []


# --- File reference injection into initial_prompt ---


def test_file_basenames_returns_unique_names(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["blurt/__init__.py", "tests/test_blurt.py", "README.md"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    result = blurt._file_basenames()
    assert result == ["__init__.py", "test_blurt.py", "README.md"]


def test_file_basenames_empty_index(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", [])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    assert blurt._file_basenames() == []


def test_vocab_prompt_includes_file_basenames(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("MLX\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
    monkeypatch.setattr(blurt, "_file_index", ["cliff.toml", "blurt/__init__.py"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    prompt = blurt._vocab_prompt()
    assert "MLX" in prompt
    assert "cliff.toml" in prompt
    assert "__init__.py" in prompt


def test_vocab_prompt_file_only_no_vocab(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "missing.txt")
    monkeypatch.setattr(blurt, "_file_index", ["README.md"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    prompt = blurt._vocab_prompt()
    assert prompt == "README.md"


def test_vocab_prompt_no_vocab_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "missing.txt")
    monkeypatch.setattr(blurt, "_file_index", [])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    assert blurt._vocab_prompt() is None


# --- File reference resolution ---


def test_resolve_replaces_basename_with_full_path(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["blurt/__init__.py", "tests/test_blurt.py", "cliff.toml"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    result = blurt._resolve_file_refs("check cliff.toml for the config")
    assert "@cliff.toml" in result


def test_resolve_uses_full_path_for_nested_files(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["blurt/__init__.py", "tests/test_blurt.py"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    result = blurt._resolve_file_refs("look at __init__.py")
    assert "@blurt/__init__.py" in result


def test_resolve_case_insensitive(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["README.md"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    result = blurt._resolve_file_refs("check readme.md please")
    assert "@README.md" in result


def test_resolve_no_match_passthrough(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["blurt/__init__.py"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    original = "just some normal text"
    assert blurt._resolve_file_refs(original) == original


def test_resolve_empty_index(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", [])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    original = "check cliff.toml"
    assert blurt._resolve_file_refs(original) == original


def test_resolve_preserves_surrounding_text(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["CLAUDE.md"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    result = blurt._resolve_file_refs("what about CLAUDE.md and the config")
    assert result == "what about @CLAUDE.md and the config"


# --- paste_transcription ---


def test_paste_retries_on_osascript_failure(monkeypatch):
    """paste_transcription retries once when osascript fails, then succeeds."""
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0 if len(calls) > 1 else 1
            stdout = b""
            stderr = ""

        return Result()

    monkeypatch.setattr(blurt.subprocess, "run", mock_run)
    monkeypatch.setattr(blurt, "_get_clipboard", lambda: b"prev")
    set_calls = []
    monkeypatch.setattr(blurt, "_set_clipboard", lambda data: set_calls.append(data))
    monkeypatch.setattr(blurt.time, "sleep", lambda _: None)

    blurt.paste_transcription("hello")
    # Should have called osascript twice (first fail, second succeed)
    osascript_calls = [c for c in calls if c[0] == "osascript"]
    assert len(osascript_calls) == 2


def test_paste_gives_up_after_two_failures(monkeypatch, capsys):
    """paste_transcription gives up after 2 osascript failures and prints a message."""
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 1
            stdout = b""
            stderr = ""

        return Result()

    monkeypatch.setattr(blurt.subprocess, "run", mock_run)
    monkeypatch.setattr(blurt, "_get_clipboard", lambda: b"prev")
    set_calls = []
    monkeypatch.setattr(blurt, "_set_clipboard", lambda data: set_calls.append(data))
    monkeypatch.setattr(blurt.time, "sleep", lambda _: None)

    blurt.paste_transcription("hello")
    captured = capsys.readouterr()
    assert "Paste failed" in captured.out
    # Should NOT restore clipboard on failure (text stays available for manual paste)
    assert len(set_calls) == 1  # only the initial set, no restore


# --- _check_accessibility ---


def test_check_accessibility_warns_on_failure(monkeypatch, capsys):
    """_check_accessibility prints a warning when osascript returns non-zero."""

    class FailResult:
        returncode = 1
        stdout = ""
        stderr = "not allowed"

    monkeypatch.setattr(blurt.subprocess, "run", lambda *a, **kw: FailResult())
    blurt._check_accessibility()
    captured = capsys.readouterr()
    assert "Accessibility permission" in captured.out


def test_check_accessibility_silent_on_success(monkeypatch, capsys):
    """_check_accessibility prints nothing when permissions are granted."""

    class OkResult:
        returncode = 0
        stdout = "Finder"
        stderr = ""

    monkeypatch.setattr(blurt.subprocess, "run", lambda *a, **kw: OkResult())
    blurt._check_accessibility()
    captured = capsys.readouterr()
    assert captured.out == ""


# --- Config / language ---


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "CONFIG_PATH", tmp_path / "missing.toml")
    assert blurt._load_config() == {}


def test_load_config_simple_keyval(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text('language = "es"\n')
    monkeypatch.setattr(blurt, "CONFIG_PATH", cfg)
    config = blurt._load_config()
    assert config["language"] == "es"


def test_get_language_default(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "CONFIG_PATH", tmp_path / "missing.toml")
    assert blurt._get_language() == "en"


def test_get_language_configured(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text('language = "ja"\n')
    monkeypatch.setattr(blurt, "CONFIG_PATH", cfg)
    assert blurt._get_language() == "ja"


def test_get_language_invalid_falls_back(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    cfg.write_text('language = "zz"\n')
    monkeypatch.setattr(blurt, "CONFIG_PATH", cfg)
    assert blurt._get_language() == "en"
    captured = capsys.readouterr()
    assert "Unknown language" in captured.out


# --- VAD trimming ---


def test_vad_trim_removes_leading_silence():
    sr = 16000
    silence = np.zeros(sr, dtype=np.float32)  # 1 second silence
    speech = np.random.randn(sr).astype(np.float32) * 0.1  # 1 second speech
    audio = np.concatenate([silence, speech])
    trimmed = blurt._vad_trim(audio, sr)
    assert len(trimmed) < len(audio)
    assert len(trimmed) > 0


def test_vad_trim_removes_trailing_silence():
    sr = 16000
    speech = np.random.randn(sr).astype(np.float32) * 0.1
    silence = np.zeros(sr, dtype=np.float32)
    audio = np.concatenate([speech, silence])
    trimmed = blurt._vad_trim(audio, sr)
    assert len(trimmed) < len(audio)


def test_vad_trim_preserves_speech_only():
    sr = 16000
    speech = np.random.randn(sr).astype(np.float32) * 0.1
    trimmed = blurt._vad_trim(speech, sr)
    # Should not lose significant data (margins may add/remove a frame or two)
    assert len(trimmed) >= len(speech) * 0.8


def test_vad_trim_all_silence_returns_original():
    sr = 16000
    silence = np.zeros(sr, dtype=np.float32)
    trimmed = blurt._vad_trim(silence, sr)
    assert len(trimmed) == len(silence)


def test_vad_trim_short_audio_returns_original():
    sr = 16000
    short = np.array([0.1, 0.2], dtype=np.float32)
    trimmed = blurt._vad_trim(short, sr)
    assert len(trimmed) == len(short)


# --- doctor CLI ---


def test_doctor_subcommand(monkeypatch, capsys):
    """blurt doctor should run without crashing."""
    monkeypatch.setattr(blurt, "_model_is_cached", lambda _: True)
    monkeypatch.setattr(blurt, "_file_index", ["test.py"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())

    class FakeStream:
        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(blurt.sd, "InputStream", lambda **kw: FakeStream())
    monkeypatch.setattr(blurt.sd, "query_devices", lambda *a: [{"name": "Mic", "max_input_channels": 1}])
    monkeypatch.setattr(blurt.sd.default, "device", (0, 1))

    class OkResult:
        returncode = 0
        stdout = "Finder"
        stderr = ""

    monkeypatch.setattr(blurt.subprocess, "run", lambda *a, **kw: OkResult())

    with patch.object(sys, "argv", ["blurt", "doctor"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "blurt doctor" in captured.out
