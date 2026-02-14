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
