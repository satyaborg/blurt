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


# --- _levenshtein ---


def test_levenshtein_identical():
    assert blurt._levenshtein("hello", "hello") == 0


def test_levenshtein_empty():
    assert blurt._levenshtein("", "abc") == 3
    assert blurt._levenshtein("abc", "") == 3


def test_levenshtein_substitution():
    assert blurt._levenshtein("blur", "blurt") == 1


def test_levenshtein_case():
    assert blurt._levenshtein("Blurt", "blurt") == 1


def test_levenshtein_completely_different():
    assert blurt._levenshtein("abc", "xyz") == 3


# --- _extract_corrections ---


def test_extract_corrections_single_word():
    corrections = blurt._extract_corrections(
        "lets talk about the blur project",
        "lets talk about the Blurt project",
    )
    assert corrections == [("blur", "Blurt")]


def test_extract_corrections_no_change():
    corrections = blurt._extract_corrections(
        "hello world",
        "hello world",
    )
    assert corrections == []


def test_extract_corrections_with_surrounding_text():
    corrections = blurt._extract_corrections(
        "talk about blur",
        "Previously typed text talk about Blurt more text after",
    )
    assert corrections == [("blur", "Blurt")]


def test_extract_corrections_rejects_large_edits():
    """Words that are too different should not be treated as corrections."""
    corrections = blurt._extract_corrections(
        "talk about blur",
        "talk about Kubernetes",
    )
    assert corrections == []


def test_extract_corrections_multiple():
    corrections = blurt._extract_corrections(
        "the pyton langauge is great",
        "the Python language is great",
    )
    assert ("pyton", "Python") in corrections
    assert ("langauge", "language") in corrections


# --- _load_vocabulary / _save_corrections ---


def test_load_vocabulary_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "vocab.txt")
    assert blurt._load_vocabulary() == {}


def test_load_vocabulary_with_entries(tmp_path, monkeypatch):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("blur -> Blurt\npyton -> Python\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab_file)

    vocab = blurt._load_vocabulary()
    assert vocab == {"blur": "Blurt", "pyton": "Python"}


def test_load_vocabulary_skips_comments(tmp_path, monkeypatch):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("# my corrections\nblur -> Blurt\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab_file)

    vocab = blurt._load_vocabulary()
    assert vocab == {"blur": "Blurt"}


def test_save_corrections_appends(tmp_path, monkeypatch):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("blur -> Blurt\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab_file)

    blurt._save_corrections([("pyton", "Python")])
    content = vocab_file.read_text()
    assert "blur -> Blurt" in content
    assert "pyton -> Python" in content


def test_save_corrections_no_duplicates(tmp_path, monkeypatch):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("blur -> Blurt\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab_file)

    blurt._save_corrections([("blur", "Blurt")])
    content = vocab_file.read_text()
    assert content.count("blur") == 1


# --- _vocabulary_prompt ---


def test_vocabulary_prompt_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "vocab.txt")
    assert blurt._vocabulary_prompt() == ""


def test_vocabulary_prompt_builds_string(tmp_path, monkeypatch):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("blur -> Blurt\npyton -> Python\n")
    monkeypatch.setattr(blurt, "VOCAB_PATH", vocab_file)

    prompt = blurt._vocabulary_prompt()
    assert "Blurt" in prompt
    assert "Python" in prompt


# --- _check_corrections ---


def test_check_corrections_learns(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "vocab.txt")
    monkeypatch.setattr(blurt, "last_pasted_text", "talk about blur")
    monkeypatch.setattr(blurt, "_read_focused_text", lambda: "talk about Blurt")

    blurt._check_corrections()

    vocab = blurt._load_vocabulary()
    assert vocab == {"blur": "Blurt"}
    assert blurt.last_pasted_text is None


def test_check_corrections_noop_when_no_paste(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "vocab.txt")
    monkeypatch.setattr(blurt, "last_pasted_text", None)

    blurt._check_corrections()
    assert blurt._load_vocabulary() == {}


def test_check_corrections_noop_when_field_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "vocab.txt")
    monkeypatch.setattr(blurt, "last_pasted_text", "hello world")
    monkeypatch.setattr(blurt, "_read_focused_text", lambda: None)

    blurt._check_corrections()
    assert blurt._load_vocabulary() == {}


# --- vocab CLI ---


def test_vocab_subcommand(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(blurt, "VOCAB_PATH", tmp_path / "vocab.txt")
    with patch.object(sys, "argv", ["blurt", "vocab"]):
        blurt.main()
    captured = capsys.readouterr()
    assert "No vocabulary learned yet" in captured.out
