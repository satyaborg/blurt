import json
import sys
from unittest.mock import patch

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
    assert blurt._vocab_prompt() is None


def test_vocab_prompt_with_words(tmp_path, monkeypatch):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("Blurt\nMLX\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab)
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
