import json
import sys
from types import ModuleType, SimpleNamespace
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


def test_prompt_echo_exact_vocab(tmp_path, monkeypatch):
    """Transcription that's just vocab words echoed back should be detected."""
    prompt = "Kubernetes, pydantic, FastAPI"
    assert blurt._is_prompt_echo("Kubernetes, pydantic, FastAPI", prompt) is True


def test_prompt_echo_partial(tmp_path, monkeypatch):
    """Mostly vocab words should still be detected."""
    prompt = "Kubernetes, pydantic, FastAPI, Blurt"
    assert blurt._is_prompt_echo("Kubernetes pydantic Blurt the FastAPI", prompt) is True


def test_prompt_echo_real_speech():
    """Real speech that happens to contain some vocab words should NOT be flagged."""
    prompt = "Kubernetes, pydantic"
    text = "deploy the Kubernetes cluster and add pydantic validation to the API endpoints"
    assert blurt._is_prompt_echo(text, prompt) is False


def test_prompt_echo_file_names():
    """File basenames echoed back should also be caught."""
    prompt = "__init__.py, README.md, cliff.toml"
    assert blurt._is_prompt_echo("__init__.py, README.md, cliff.toml", prompt) is True


def test_prompt_echo_no_prompt():
    """No prompt means no echo possible."""
    assert blurt._is_prompt_echo("some text", None) is False


def test_prompt_echo_example_sentence():
    prompt = "open __init__.py and update the function. add a test in test_app.py and run pytest."
    text = "open __init__.py and update the function add a test in test_app.py and run pytest"
    assert blurt._is_prompt_echo(text, prompt) is True


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


def test_version_flag_takes_priority_over_mode_flag(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "--fast", "--version"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "blurt" in captured.out
    assert not (tmp_path / "config.json").exists()


def test_help_takes_priority_over_mode_flag(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "--accurate", "help"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert not (tmp_path / "config.json").exists()


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


# --- Upgrades ---


class _UpgradeResponse:
    def read(self):
        return json.dumps(
            {
                "info": {"version": "9999.0.0"},
                "urls": [
                    {
                        "filename": "blurt-9999.0.0-py3-none-any.whl",
                        "packagetype": "bdist_wheel",
                        "url": "https://files.pythonhosted.org/blurt-9999.0.0.whl",
                    }
                ],
            }
        ).encode()


def test_upgrade_silences_pipx_home_space_warning(monkeypatch):
    call = {}
    monkeypatch.setattr(blurt, "urlopen", lambda *args, **kwargs: _UpgradeResponse())
    monkeypatch.setattr(blurt, "_v", lambda name: "9999.0.0")
    monkeypatch.setattr(blurt, "_is_pipx_install", lambda: True)
    monkeypatch.setattr(blurt.shutil, "which", lambda name: "/opt/homebrew/bin/pipx")
    monkeypatch.setattr(blurt.subprocess, "call", lambda cmd, **kwargs: call.update(cmd=cmd, **kwargs) or 0)

    with pytest.raises(SystemExit, match="0"):
        blurt.cmd_upgrade()

    assert call["cmd"] == ["pipx", "upgrade", "blurt"]
    assert call["env"]["PIPX_HOME_ALLOW_SPACE"] == "1"
    assert call["env"]["PIP_NO_CACHE_DIR"] == "false"


def test_background_upgrade_silences_pipx_home_space_warning(monkeypatch):
    call = {}

    class Result:
        returncode = 0

    monkeypatch.setattr(blurt, "__version__", "0.0.0")
    monkeypatch.setattr(blurt, "_v", lambda name: "9999.0.0")
    monkeypatch.setattr(blurt, "urlopen", lambda *args, **kwargs: _UpgradeResponse())
    monkeypatch.setattr(blurt, "_is_pipx_install", lambda: True)
    monkeypatch.setattr(blurt.shutil, "which", lambda name: "/opt/homebrew/bin/pipx")
    monkeypatch.setattr(blurt.subprocess, "run", lambda cmd, **kwargs: call.update(cmd=cmd, **kwargs) or Result())

    blurt._check_update_bg()

    assert call["cmd"] == ["pipx", "upgrade", "blurt"]
    assert call["env"]["PIPX_HOME_ALLOW_SPACE"] == "1"
    assert call["env"]["PIP_NO_CACHE_DIR"] == "false"


def test_upgrade_command_falls_back_to_pip(monkeypatch):
    monkeypatch.setattr(blurt.shutil, "which", lambda name: None)

    cmd, env = blurt._upgrade_command()

    assert cmd == [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "blurt"]
    assert env is None


def test_upgrade_command_uses_pip_outside_pipx(monkeypatch):
    monkeypatch.setattr(blurt, "_is_pipx_install", lambda: False)
    monkeypatch.setattr(blurt.shutil, "which", lambda name: "/opt/homebrew/bin/pipx")

    cmd, env = blurt._upgrade_command()

    assert cmd[0] == sys.executable
    assert env is None


def test_background_upgrade_does_not_claim_uninstalled_version(monkeypatch, capsys):
    commands = []

    class Result:
        returncode = 0

    monkeypatch.setattr(blurt, "__version__", "0.0.0")
    monkeypatch.setattr(blurt, "_v", lambda name: "0.0.0")
    monkeypatch.setattr(blurt, "urlopen", lambda *args, **kwargs: _UpgradeResponse())
    monkeypatch.setattr(blurt, "_is_pipx_install", lambda: True)
    monkeypatch.setattr(blurt.shutil, "which", lambda name: "/opt/homebrew/bin/pipx")
    monkeypatch.setattr(blurt.subprocess, "run", lambda cmd, **kwargs: commands.append(cmd) or Result())

    blurt._check_update_bg()

    output = capsys.readouterr().out
    assert "updated to" not in output
    assert "v9999.0.0 was not installed" in output
    assert commands[1] == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--no-cache-dir",
        "https://files.pythonhosted.org/blurt-9999.0.0.whl",
    ]


def test_background_upgrade_uses_release_artifact_when_index_lags(monkeypatch, capsys):
    commands = []
    installed_versions = iter(["0.0.0", "9999.0.0", "9999.0.0"])

    class Result:
        returncode = 0

    monkeypatch.setattr(blurt, "__version__", "0.0.0")
    monkeypatch.setattr(blurt, "_v", lambda name: next(installed_versions))
    monkeypatch.setattr(blurt, "urlopen", lambda *args, **kwargs: _UpgradeResponse())
    monkeypatch.setattr(blurt, "_is_pipx_install", lambda: True)
    monkeypatch.setattr(blurt.shutil, "which", lambda name: "/opt/homebrew/bin/pipx")
    monkeypatch.setattr(blurt.subprocess, "run", lambda cmd, **kwargs: commands.append(cmd) or Result())

    blurt._check_update_bg()

    assert commands[1][-1] == "https://files.pythonhosted.org/blurt-9999.0.0.whl"
    assert commands[2] == ["pipx", "upgrade", "blurt"]
    assert "updated to v9999.0.0" in capsys.readouterr().out


def test_upgrade_fails_when_new_version_was_not_installed(monkeypatch, capsys):
    commands = []
    monkeypatch.setattr(blurt, "__version__", "0.0.0")
    monkeypatch.setattr(blurt, "_v", lambda name: "0.0.0")
    monkeypatch.setattr(blurt, "urlopen", lambda *args, **kwargs: _UpgradeResponse())
    monkeypatch.setattr(blurt, "_is_pipx_install", lambda: True)
    monkeypatch.setattr(blurt.shutil, "which", lambda name: "/opt/homebrew/bin/pipx")
    monkeypatch.setattr(blurt.subprocess, "call", lambda cmd, **kwargs: commands.append(cmd) or 0)

    with pytest.raises(SystemExit, match="1"):
        blurt.cmd_upgrade()

    assert "v9999.0.0 was not installed" in capsys.readouterr().out
    assert commands[1][-1] == "https://files.pythonhosted.org/blurt-9999.0.0.whl"
    assert commands[2] == ["pipx", "upgrade", "blurt"]


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
    assert "pytest" in prompt


def test_vocab_prompt_file_only_no_vocab(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "missing.txt")
    monkeypatch.setattr(blurt, "_file_index", ["README.md"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    prompt = blurt._vocab_prompt()
    assert "README.md" in prompt
    assert "pytest" in prompt


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


def test_resolve_spoken_dot_form(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["tests/test_blurt.py"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    result = blurt._resolve_file_refs("check test blurt dot py please")
    assert "@tests/test_blurt.py" in result


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


def test_resolve_does_not_rewrite_existing_full_path(monkeypatch):
    monkeypatch.setattr(blurt, "_file_index", ["tests/test_blurt.py"])
    monkeypatch.setattr(blurt, "_file_index_time", __import__("time").monotonic())
    result = blurt._resolve_file_refs("check tests/test_blurt.py")
    assert result == "check tests/test_blurt.py"


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


def test_paste_restores_clipboard_in_background(monkeypatch):
    thread_targets = []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            self.target = target
            self.args = args
            thread_targets.append(self)

        def start(self):
            self.target(*self.args)

    class OkResult:
        returncode = 0
        stdout = b""
        stderr = ""

    monkeypatch.setattr(blurt.subprocess, "run", lambda *a, **kw: OkResult())
    monkeypatch.setattr(blurt.threading, "Thread", FakeThread)
    monkeypatch.setattr(blurt, "_get_clipboard", lambda: b"prev")
    set_calls = []
    monkeypatch.setattr(blurt, "_set_clipboard", lambda data: set_calls.append(data))
    monkeypatch.setattr(blurt.time, "sleep", lambda _: None)

    blurt.paste_transcription("hello")

    assert len(thread_targets) == 1
    assert set_calls == [b"hello", b"prev"]


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


def _set_config_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(blurt, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(blurt, "LEGACY_CONFIG_PATH", tmp_path / "config.toml")


def test_load_config_missing_file(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    config = blurt._load_config()
    assert config["model_mode"] == "fast"
    assert config["language"] == "en"
    assert config["pause_media"] is True
    assert (tmp_path / "config.json").exists()


def test_load_config_json(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"language": "es"}\n')
    config = blurt._load_config()
    assert config["language"] == "es"


def test_load_config_legacy_toml_fallback(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    cfg = tmp_path / "config.toml"
    cfg.write_text('language = "es"\n')
    config = blurt._load_config()
    assert config["language"] == "es"
    assert config["model_mode"] == "accurate"
    assert json.loads((tmp_path / "config.json").read_text()) == {
        "language": "es",
        "model_mode": "accurate",
        "pause_media": True,
    }


def test_get_language_default(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    assert blurt._get_language() == "en"


def test_get_language_configured(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"language": "ja"}\n')
    assert blurt._get_language() == "ja"


def test_get_language_invalid_falls_back(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"language": "zz"}\n')
    assert blurt._get_language() == "en"
    captured = capsys.readouterr()
    assert "Unknown language" in captured.out


def test_get_model_mode_default(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    assert blurt._get_model_mode() == "fast"


def test_get_model_mode_configured(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"model_mode": "accurate"}\n')
    assert blurt._get_model_mode() == "accurate"
    assert blurt._get_model_repo() == blurt.MODEL_MODES["accurate"]["repo"]


def test_get_qwen_model_config(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"model_mode": "qwen"}\n')
    assert blurt._get_model_mode() == "qwen"
    assert blurt._get_model_repo() == "mlx-community/Qwen3-ASR-1.7B-8bit"
    assert blurt._get_model_backend() == "qwen"


def test_get_model_language_for_whisper(monkeypatch):
    monkeypatch.setattr(blurt, "_get_language", lambda: "en")
    assert blurt._get_model_language("whisper") == "en"


def test_get_model_language_for_qwen(monkeypatch):
    monkeypatch.setattr(blurt, "_get_language", lambda: "en")
    assert blurt._get_model_language("qwen") == "English"


def test_get_model_mode_invalid_falls_back(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"model_mode": "turbo"}\n')
    assert blurt._get_model_mode() == "fast"
    captured = capsys.readouterr()
    assert "Unknown model_mode" in captured.out


def test_save_config(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    blurt._save_config({"pause_media": True})
    assert json.loads(cfg.read_text()) == {"pause_media": True}


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


def test_vad_trim_keeps_low_energy_trailing_speech():
    sr = 16000
    frame_len = int(sr * 30 / 1000)
    speech = np.full(frame_len * 10, 0.1, dtype=np.float32)
    soft_tail = np.full(frame_len * 8, 0.004, dtype=np.float32)
    silence = np.zeros(frame_len * 10, dtype=np.float32)
    audio = np.concatenate([speech, soft_tail, silence])

    trimmed = blurt._vad_trim(audio, sr)

    assert len(trimmed) >= len(speech) + len(soft_tail)


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


# --- Media pause/resume ---


def test_pause_media_sends_command_when_enabled(monkeypatch):
    """When pause_media is enabled and audio is active, should call MRMediaRemoteSendCommand with PAUSE."""
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()
    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "_media_paused_session_id", None)
    monkeypatch.setattr(blurt, "_load_config", lambda: {"pause_media": True})
    monkeypatch.setattr(blurt, "_is_audio_active", lambda: True)
    blurt._pause_media(7)
    assert calls == [blurt._MR_PAUSE]
    assert blurt._media_paused_session_id == 7


def test_pause_media_noop_when_disabled(monkeypatch):
    """When pause_media is disabled, should do nothing."""
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()
    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "_media_paused_session_id", None)
    monkeypatch.setattr(blurt, "_load_config", lambda: {"pause_media": False})
    blurt._pause_media(7)
    assert calls == []
    assert blurt._media_paused_session_id is None


def test_pause_media_does_not_transfer_existing_session_when_disabled(monkeypatch):
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()
    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "_media_paused_session_id", 5)
    monkeypatch.setattr(blurt, "_load_config", lambda: {"pause_media": False})

    blurt._pause_media(6)

    assert calls == []
    assert blurt._media_paused_session_id == 5


def test_pause_media_noop_when_no_framework(monkeypatch):
    """Should silently handle missing MediaRemote framework."""
    monkeypatch.setattr(blurt, "_mr_lib", None)
    monkeypatch.setattr(blurt, "_media_paused_session_id", None)
    monkeypatch.setattr(blurt, "_load_config", lambda: {"pause_media": True})
    blurt._pause_media(7)  # Should not raise
    assert blurt._media_paused_session_id is None


def test_resume_media_sends_play_when_paused(monkeypatch):
    """Should call MRMediaRemoteSendCommand with PLAY when we previously paused."""
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()
    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "_media_paused_session_id", 7)
    blurt._resume_media(7)
    assert calls == [blurt._MR_PLAY]
    assert blurt._media_paused_session_id is None


def test_resume_media_noop_when_not_paused(monkeypatch):
    """Should do nothing if we didn't pause anything."""
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()
    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "_media_paused_session_id", None)
    blurt._resume_media(7)
    assert calls == []


def test_resume_media_noop_for_different_session(monkeypatch):
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()
    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "_media_paused_session_id", 8)

    blurt._resume_media(7)

    assert calls == []
    assert blurt._media_paused_session_id == 8


# --- CLI: blurt pause ---


def test_pause_on(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "pause", "on"]):
        blurt.main()
    assert blurt._load_config().get("pause_media") is True
    captured = capsys.readouterr()
    assert "on" in captured.out.lower()


def test_pause_off(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"pause_media": true}\n')
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "pause", "off"]):
        blurt.main()
    assert blurt._load_config().get("pause_media") is False
    captured = capsys.readouterr()
    assert "off" in captured.out.lower()


def test_pause_status(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"pause_media": true}\n')
    with patch.object(sys, "argv", ["blurt", "pause"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "on" in captured.out.lower()


def test_mode_fast(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "mode", "fast"]):
        blurt.main()
    assert blurt._load_config().get("model_mode") == "fast"
    captured = capsys.readouterr()
    assert "Mode: fast" in captured.out


def test_mode_status(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text('{"model_mode": "fast"}\n')
    with patch.object(sys, "argv", ["blurt", "mode"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "Mode:" in captured.out
    assert "fast" in captured.out


def test_mode_invalid_exits(tmp_path, monkeypatch):
    _set_config_paths(monkeypatch, tmp_path)
    with patch.object(sys, "argv", ["blurt", "mode", "turbo"]):
        with pytest.raises(SystemExit, match="1"):
            blurt.main()


def test_fast_flag_writes_config(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "--fast"]):
        blurt.main()
    assert blurt._load_config().get("model_mode") == "fast"
    captured = capsys.readouterr()
    assert "Mode: fast" in captured.out


def test_accurate_flag_writes_config(tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", "--accurate"]):
        blurt.main()
    assert blurt._load_config().get("model_mode") == "accurate"
    captured = capsys.readouterr()
    assert "Mode: accurate" in captured.out


@pytest.mark.parametrize("args", [["mode", "qwen"], ["--qwen"], ["--mode", "qwen"]])
def test_qwen_mode(args, tmp_path, monkeypatch, capsys):
    _set_config_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(blurt, "BLURT_DIR", tmp_path)
    monkeypatch.setattr(blurt, "AUDIO_DIR", tmp_path / "audio")
    with patch.object(sys, "argv", ["blurt", *args]):
        blurt.main()
    assert blurt._load_config().get("model_mode") == "qwen"
    assert "Mode: qwen" in capsys.readouterr().out


def test_invalid_mode_flag_exits(capsys):
    with patch.object(sys, "argv", ["blurt", "--mode", "nope"]):
        with pytest.raises(SystemExit, match="1"):
            blurt.main()
    assert "fast|accurate|qwen" in capsys.readouterr().out


# --- Transcription backends ---


@pytest.mark.parametrize(
    ("files", "expected"),
    [(["config.json"], False), (["config.json", "weights.npz"], True), (["model.safetensors"], True)],
)
def test_model_is_cached_requires_weights(files, expected, monkeypatch):
    import huggingface_hub

    cached_files = [SimpleNamespace(file_name=name) for name in files]
    repo = SimpleNamespace(
        repo_id="test/repo",
        revisions=[SimpleNamespace(files=cached_files)],
    )
    monkeypatch.setattr(huggingface_hub, "scan_cache_dir", lambda: SimpleNamespace(repos=[repo]))
    assert blurt._model_is_cached("test/repo") is expected


def test_model_is_cached_handles_scan_failure(monkeypatch):
    import huggingface_hub

    def fail():
        raise OSError("failed")

    monkeypatch.setattr(huggingface_hub, "scan_cache_dir", fail)
    assert blurt._model_is_cached("test/repo") is False


@pytest.mark.parametrize("backend", ["whisper", "qwen"])
def test_create_transcription_model(backend, monkeypatch):
    expected = object()
    if backend == "whisper":
        module = ModuleType("mlx_whisper")
        monkeypatch.setitem(sys.modules, "mlx_whisper", module)
        assert blurt._create_transcription_model("test/repo", backend) is module
        return

    package = ModuleType("mlx_audio")
    module = ModuleType("mlx_audio.stt")
    module.load = lambda repo_id: expected
    monkeypatch.setitem(sys.modules, "mlx_audio", package)
    monkeypatch.setitem(sys.modules, "mlx_audio.stt", module)
    assert blurt._create_transcription_model("test/repo", backend) is expected


@pytest.mark.parametrize("prompt", [None, "Blurt, MLX"])
def test_transcribe_with_whisper(prompt, monkeypatch):
    calls = []
    model = SimpleNamespace(
        transcribe=lambda audio, **kwargs: (
            calls.append((audio, kwargs)) or {"text": "hello", "segments": [{"no_speech_prob": 0.1}]}
        )
    )
    audio = np.ones(16, dtype=np.float32)
    monkeypatch.setattr(blurt, "_get_model_language", lambda backend: "en")

    result = blurt._transcribe_with_model(model, "whisper", "test/repo", audio, prompt)

    assert result["text"] == "hello"
    assert calls[0][0] is audio
    assert calls[0][1]["path_or_hf_repo"] == "test/repo"
    if prompt:
        assert calls[0][1]["initial_prompt"] == prompt
    else:
        assert "initial_prompt" not in calls[0][1]


@pytest.mark.parametrize("prompt", [None, "Blurt, MLX"])
def test_transcribe_with_qwen(prompt, monkeypatch):
    calls = []
    model = SimpleNamespace(
        generate=lambda audio, **kwargs: (
            calls.append((audio, kwargs)) or SimpleNamespace(text="hello", segments=[{"text": "hello"}])
        )
    )
    audio = np.ones(16, dtype=np.float32)
    monkeypatch.setattr(blurt, "_get_model_language", lambda backend: "English")

    result = blurt._transcribe_with_model(model, "qwen", "test/repo", audio, prompt)

    assert result == {"text": "hello", "segments": [{"text": "hello"}]}
    assert calls[0][0] is audio
    assert calls[0][1]["language"] == "English"
    if prompt:
        assert prompt in calls[0][1]["system_prompt"]
    else:
        assert "system_prompt" not in calls[0][1]


def test_transcribe_uses_loaded_model(monkeypatch):
    model = object()
    monkeypatch.setattr(blurt, "transcription_model", model)
    monkeypatch.setattr(blurt, "loaded_model_repo", "test/repo")
    monkeypatch.setattr(blurt, "loaded_model_backend", "qwen")
    monkeypatch.setattr(
        blurt,
        "_transcribe_with_model",
        lambda *args: {"text": args[4], "segments": []},
    )
    result = blurt._transcribe(np.ones(16, dtype=np.float32), "Blurt")
    assert result["text"] == "Blurt"


def test_transcribe_requires_loaded_model(monkeypatch):
    monkeypatch.setattr(blurt, "transcription_model", None)
    with pytest.raises(RuntimeError, match="not loaded"):
        blurt._transcribe(np.ones(16, dtype=np.float32))


@pytest.mark.parametrize("backend", ["whisper", "qwen"])
def test_warm_transcription_model(backend, monkeypatch):
    calls = []
    method = "generate" if backend == "qwen" else "transcribe"
    model = SimpleNamespace(**{method: lambda audio, **kwargs: calls.append((audio, kwargs))})
    monkeypatch.setattr(blurt, "_get_model_language", lambda selected: "English" if selected == "qwen" else "en")

    blurt._warm_transcription_model(model, backend, "test/repo")

    assert len(calls[0][0]) == blurt.SAMPLE_RATE
    if backend == "qwen":
        assert calls[0][1]["max_tokens"] == 1
    else:
        assert calls[0][1]["path_or_hf_repo"] == "test/repo"


@pytest.mark.parametrize("cached", [False, True])
def test_load_model(cached, monkeypatch):
    events = []
    model = object()
    huggingface_hub = ModuleType("huggingface_hub")
    huggingface_hub.utils = SimpleNamespace(
        disable_progress_bars=lambda: events.append("disable"),
        enable_progress_bars=lambda: events.append("enable"),
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub", huggingface_hub)
    monkeypatch.setattr(blurt, "transcription_model", None)
    monkeypatch.setattr(blurt, "loaded_model_repo", None)
    monkeypatch.setattr(blurt, "loaded_model_backend", None)
    monkeypatch.setattr(blurt, "_get_model_repo", lambda: "test/repo")
    monkeypatch.setattr(blurt, "_get_model_backend", lambda: "qwen")
    monkeypatch.setattr(blurt, "_model_is_cached", lambda repo: cached)
    monkeypatch.setattr(blurt, "_create_transcription_model", lambda repo, backend: model)
    monkeypatch.setattr(blurt, "_warm_transcription_model", lambda *args: events.append("warm"))
    monkeypatch.setattr(blurt, "_play_sound", lambda name: events.append(name))
    monkeypatch.setattr(blurt, "_start_keepalive", lambda: events.append("keepalive"))

    blurt.load_model()
    blurt.load_model()

    assert blurt.transcription_model is model
    assert blurt.loaded_model_repo == "test/repo"
    assert blurt.loaded_model_backend == "qwen"
    assert events.count("warm") == 1
    assert events[-2:] == ["ready", "keepalive"]
    if cached:
        assert events[:2] == ["disable", "warm"]
        assert "enable" in events


@pytest.mark.parametrize("state", ["loaded", "missing", "error"])
def test_keepalive_warms_loaded_backend(state, monkeypatch):
    events = []

    class FakeTimer:
        daemon = False

        def __init__(self, interval, target):
            events.append((interval, target))

        def start(self):
            events.append("start")

    model = None if state == "missing" else object()
    monkeypatch.setattr(blurt, "transcription_model", model)
    monkeypatch.setattr(blurt, "loaded_model_repo", None if state == "missing" else "test/repo")
    monkeypatch.setattr(blurt, "loaded_model_backend", None if state == "missing" else "qwen")
    monkeypatch.setattr(blurt, "_keepalive_timer", None)

    def warm(*args):
        events.append(args)
        if state == "error":
            raise RuntimeError("failed")

    monkeypatch.setattr(blurt, "_warm_transcription_model", warm)
    monkeypatch.setattr(blurt.threading, "Timer", FakeTimer)

    blurt._keepalive_loop()

    if state == "missing":
        assert events[0][0] == blurt._KEEPALIVE_INTERVAL
    else:
        assert events[0] == (model, "qwen", "test/repo")
    assert events[-1] == "start"


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


# --- Recording + media integration ---


def test_start_recording_pauses_media(monkeypatch):
    """start_recording should call _pause_media."""
    paused = []
    stream_kwargs = {}
    monkeypatch.setattr(blurt, "_pause_media", lambda session_id: paused.append(session_id))
    monkeypatch.setattr(blurt, "recording", False)
    monkeypatch.setattr(blurt, "record_requested", True)
    monkeypatch.setattr(blurt, "start_pending", True)
    monkeypatch.setattr(blurt, "audio_buffer", [])
    monkeypatch.setattr(blurt, "rec_status", None)
    monkeypatch.setattr(blurt, "recording_session_id", 0)

    class FakeStream:
        def start(self):
            pass

    def fake_input_stream(**kwargs):
        stream_kwargs.update(kwargs)
        return FakeStream()

    monkeypatch.setattr(blurt.sd, "InputStream", fake_input_stream)
    monkeypatch.setattr(
        blurt,
        "console",
        type("C", (), {"status": lambda self, x: type("S", (), {"start": lambda s: None})()})(),
    )

    blurt.start_recording()
    assert paused == [1]
    assert stream_kwargs["latency"] == "low"

    # Cleanup
    monkeypatch.setattr(blurt, "recording", False)


def test_stop_recording_resumes_media(monkeypatch):
    """stop_recording should call _resume_media after closing stream."""
    resumed = []
    monkeypatch.setattr(blurt, "_resume_media", lambda session_id: resumed.append(session_id))
    monkeypatch.setattr(blurt, "recording", True)
    monkeypatch.setattr(blurt, "recording_session_id", 3)
    monkeypatch.setattr(blurt, "stream", type("S", (), {"stop": lambda s: None, "close": lambda s: None})())
    monkeypatch.setattr(blurt, "rec_status", type("R", (), {"stop": lambda s: None})())
    monkeypatch.setattr(blurt, "audio_buffer", [])
    monkeypatch.setattr(blurt, "_media_paused_session_id", None)

    blurt.stop_recording()
    assert resumed == [3]


def test_stop_recording_stops_stream_without_delay(monkeypatch):
    sleeps = []
    stopped = []
    closed = []

    monkeypatch.setattr(blurt.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(blurt, "_resume_media", lambda session_id: None)
    monkeypatch.setattr(blurt, "recording", True)
    monkeypatch.setattr(blurt, "recording_session_id", 5)
    monkeypatch.setattr(
        blurt,
        "stream",
        type("S", (), {"stop": lambda s: stopped.append(True), "close": lambda s: closed.append(True)})(),
    )
    monkeypatch.setattr(blurt, "rec_status", type("R", (), {"stop": lambda s: None})())
    monkeypatch.setattr(blurt, "audio_buffer", [])
    monkeypatch.setattr(blurt, "_media_paused_session_id", None)

    blurt.stop_recording()

    assert sleeps == []
    assert stopped == [True]
    assert closed == [True]


def test_stop_recording_reports_end_to_end_latency(monkeypatch, capsys):
    times = iter([10.0, 10.1, 10.4, 10.6])
    events = []
    persisted = []
    pasted = []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            self.target = target
            self.args = args

        def start(self):
            if self.target is blurt._persist_blurt:
                persisted.append(self.args[2])

    def fake_paste(text):
        pasted.append(text)
        events.append(("paste", text))

    monkeypatch.setattr(blurt.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(blurt.time, "sleep", lambda seconds: events.append(("sleep", seconds)))
    monkeypatch.setattr(blurt, "_resume_media", lambda session_id: events.append(("resume", session_id)))
    monkeypatch.setattr(blurt, "recording", True)
    monkeypatch.setattr(blurt, "recording_session_id", 5)
    monkeypatch.setattr(blurt, "stream", type("S", (), {"stop": lambda s: None, "close": lambda s: None})())
    monkeypatch.setattr(blurt, "rec_status", type("R", (), {"stop": lambda s: None})())
    monkeypatch.setattr(blurt, "audio_buffer", [np.full((16000, 1), 0.1, dtype=np.float32)])
    monkeypatch.setattr(blurt, "_media_paused_session_id", 5)
    monkeypatch.setattr(blurt, "load_model", lambda: None)
    monkeypatch.setattr(
        blurt,
        "_transcribe",
        lambda audio_data, prompt: {
            "text": "hello world",
            "segments": [{"no_speech_prob": 0.1, "avg_logprob": -0.2, "compression_ratio": 1.0}],
        },
    )
    monkeypatch.setattr(blurt, "_vocab_prompt", lambda: None)
    monkeypatch.setattr(blurt, "_resolve_file_refs", lambda text: text)
    monkeypatch.setattr(blurt, "paste_transcription", fake_paste)
    monkeypatch.setattr(blurt.threading, "Thread", FakeThread)

    blurt.stop_recording()

    captured = capsys.readouterr()
    assert pasted == ["hello world"]
    assert persisted[0]["latency_ms"] == 600
    assert persisted[0]["transcription_ms"] == 300
    assert "600ms total" in captured.out
    assert "300ms transcribe" in captured.out
    assert events == [
        ("paste", "hello world"),
        ("sleep", blurt.MEDIA_RESUME_DELAY_S),
        ("resume", 5),
    ]


def test_stop_recording_does_not_resume_newer_media_session(monkeypatch):
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()
    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "recording", True)
    monkeypatch.setattr(blurt, "recording_session_id", 5)
    monkeypatch.setattr(blurt, "stream", type("S", (), {"stop": lambda s: None, "close": lambda s: None})())
    monkeypatch.setattr(blurt, "rec_status", type("R", (), {"stop": lambda s: None})())
    monkeypatch.setattr(blurt, "audio_buffer", [])
    monkeypatch.setattr(blurt, "_media_paused_session_id", 6)

    blurt.stop_recording()

    assert calls == []
    assert blurt._media_paused_session_id == 6


def test_rapid_restart_transfers_paused_media_to_new_session(monkeypatch):
    calls = []
    fake_lib = type("Lib", (), {"MRMediaRemoteSendCommand": lambda self, cmd, info: calls.append(cmd) or True})()

    class FakeStream:
        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    class FakeStatus:
        def start(self):
            pass

        def stop(self):
            pass

    def restart_during_media_delay(seconds):
        assert seconds == blurt.MEDIA_RESUME_DELAY_S
        blurt.record_requested = True
        blurt.start_pending = True
        blurt.start_recording()

    monkeypatch.setattr(blurt, "_mr_lib", fake_lib)
    monkeypatch.setattr(blurt, "_load_config", lambda: {"pause_media": True})
    monkeypatch.setattr(blurt, "_is_audio_active", lambda: False)
    monkeypatch.setattr(blurt, "recording", True)
    monkeypatch.setattr(blurt, "record_requested", False)
    monkeypatch.setattr(blurt, "start_pending", False)
    monkeypatch.setattr(blurt, "recording_session_id", 5)
    monkeypatch.setattr(blurt, "stream", FakeStream())
    monkeypatch.setattr(blurt, "rec_status", FakeStatus())
    monkeypatch.setattr(blurt, "audio_buffer", [])
    monkeypatch.setattr(blurt, "_media_paused_session_id", 5)
    monkeypatch.setattr(blurt.sd, "InputStream", lambda **kwargs: FakeStream())
    monkeypatch.setattr(blurt, "console", type("C", (), {"status": lambda self, message: FakeStatus()})())
    monkeypatch.setattr(blurt.time, "sleep", restart_during_media_delay)

    blurt.stop_recording()

    assert calls == []
    assert blurt.recording is True
    assert blurt.recording_session_id == 6
    assert blurt._media_paused_session_id == 6


def test_shortcut_release_keeps_pending_start(monkeypatch):
    spawned = []
    monkeypatch.setattr(blurt, "pressed_keys", set())
    monkeypatch.setattr(blurt, "recording", False)
    monkeypatch.setattr(blurt, "record_requested", False)
    monkeypatch.setattr(blurt, "start_pending", False)
    monkeypatch.setattr(blurt, "_play_sound", lambda name: None)

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target
            spawned.append(self)

        def start(self):
            pass

    monkeypatch.setattr(blurt.threading, "Thread", FakeThread)

    blurt.on_press(blurt.keyboard.Key.cmd_r)
    blurt.on_release(blurt.keyboard.Key.cmd_r)

    assert len(spawned) == 1
    assert spawned[0].target is blurt.start_recording
    assert blurt.recording is False
    assert blurt.record_requested is True
    assert blurt.start_pending is True


def test_second_shortcut_press_cancels_pending_start(monkeypatch):
    spawned = []
    monkeypatch.setattr(blurt, "pressed_keys", set())
    monkeypatch.setattr(blurt, "recording", False)
    monkeypatch.setattr(blurt, "record_requested", False)
    monkeypatch.setattr(blurt, "start_pending", False)
    monkeypatch.setattr(blurt, "_play_sound", lambda name: None)

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target
            spawned.append(self)

        def start(self):
            pass

    monkeypatch.setattr(blurt.threading, "Thread", FakeThread)

    blurt.on_press(blurt.keyboard.Key.cmd_r)
    blurt.on_release(blurt.keyboard.Key.cmd_r)
    blurt.on_press(blurt.keyboard.Key.cmd_r)

    assert len(spawned) == 1
    assert blurt.record_requested is False
    assert blurt.start_pending is True


def test_second_shortcut_press_stops_recording(monkeypatch):
    spawned = []
    monkeypatch.setattr(blurt, "pressed_keys", set())
    monkeypatch.setattr(blurt, "recording", True)
    monkeypatch.setattr(blurt, "record_requested", True)
    monkeypatch.setattr(blurt, "start_pending", False)

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target
            spawned.append(self)

        def start(self):
            pass

    monkeypatch.setattr(blurt.threading, "Thread", FakeThread)

    blurt.on_press(blurt.keyboard.Key.cmd_r)

    assert len(spawned) == 1
    assert spawned[0].target is blurt.stop_recording
    assert blurt.record_requested is False


def test_shortcut_key_repeat_does_not_toggle_recording(monkeypatch):
    spawned = []
    monkeypatch.setattr(blurt, "pressed_keys", {blurt.keyboard.Key.cmd_r})
    monkeypatch.setattr(blurt, "recording", True)
    monkeypatch.setattr(blurt, "record_requested", True)
    monkeypatch.setattr(blurt, "start_pending", False)

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            spawned.append(self)

        def start(self):
            pass

    monkeypatch.setattr(blurt.threading, "Thread", FakeThread)

    blurt.on_press(blurt.keyboard.Key.cmd_r)

    assert spawned == []
    assert blurt.record_requested is True


def test_vad_trim_preserves_partial_tail_frame():
    sr = 16000
    frame_len = int(sr * 30 / 1000)
    speech = np.full(frame_len * 2 + 123, 0.1, dtype=np.float32)

    trimmed = blurt._vad_trim(speech, sr)

    assert len(trimmed) == len(speech)
