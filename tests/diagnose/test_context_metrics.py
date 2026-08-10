"""Tests für tools/diagnose/context_metrics.py (Issue #113, read-only)."""
import json
import os
import sys

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "diagnose")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))
from context_metrics import (  # noqa: E402
    MIN_BLOCK_CHARS,
    cache_tokens,
    compute_metrics,
    find_usage,
    iter_records,
    record_is_error,
    record_latency_ms,
)


def _deepseek_usage(hit, miss, inp, out):
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "prompt_cache_hit_tokens": hit,
        "prompt_cache_miss_tokens": miss,
    }


def _openai_usage(inp, out):
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "input_tokens_details": {"cacheReadTokens": inp - 10, "cacheWriteTokens": 10},
    }


def test_iter_records_skips_invalid_lines():
    text = '{"type": "a"}\nkaputt\n\n{"type": "b"}\n[1,2]\n'
    recs = list(iter_records(text))
    assert len(recs) == 2
    assert recs[0]["type"] == "a"
    assert recs[1]["type"] == "b"


def test_iter_records_empty():
    assert list(iter_records("")) == []
    assert list(iter_records("\n\n")) == []


def test_find_usage_variants():
    assert find_usage({"usage": {"input_tokens": 1}}) == {"input_tokens": 1}
    assert find_usage({"modelRun": {"usage": {"output_tokens": 2}}}) == {"output_tokens": 2}
    assert find_usage({"input_tokens": 3}) == {"input_tokens": 3}
    assert find_usage({"type": "text"}) is None


def test_find_usage_openclaw_trajectory():
    """Regression: realer OpenClaw-Trajectory-Record (v2026.7.1) traegt den
    Usage-Block unter data.usage (input/output/cacheRead/reasoningTokens).
    Vor dem Fix: None -> alle Token-Metriken 0 trotz echter Daten."""
    rec = {
        "type": "model.completed",
        "data": {"usage": {"input": 10, "output": 5, "cacheRead": 8,
                             "reasoningTokens": 2, "total": 23}},
    }
    assert find_usage(rec) == {"input": 10, "output": 5, "cacheRead": 8,
                               "reasoningTokens": 2, "total": 23}
    assert find_usage({"type": "model.completed", "data": {}}) is None


def test_cache_tokens_openclaw_trajectory():
    usage = {"input": 1000, "output": 50, "cacheRead": 900, "cacheWrite": 100}
    assert cache_tokens(usage) == (900, 100)


def test_compute_metrics_openclaw_trajectory():
    """Regression: Trajectory-Format (data.usage + data.assistantTexts) wird
    vollstaendig ausgewertet – Token-, Cache-, Reasoning- und H1/H2-Werte."""
    block = "K" * 200  # >= MIN_BLOCK_CHARS, 2x wiederholt -> H1/H2 sichtbar
    lines = [
        json.dumps({"type": "model.completed", "data": {
            "usage": {"input": 1000, "output": 200, "cacheRead": 800,
                       "reasoningTokens": 50, "total": 2000},
            "assistantTexts": [block],
            "finalPromptText": "Frage 1",
        }}),
        json.dumps({"type": "model.completed", "data": {
            "usage": {"input": 1200, "output": 250, "cacheRead": 950,
                       "reasoningTokens": 60, "total": 2400},
            "assistantTexts": [block],
            "finalPromptText": "Frage 2",
        }}),
        json.dumps({"type": "prompt.submitted", "data": {"prompt": "Hallo"}}),
    ]
    m = compute_metrics("\n".join(lines))
    assert m["turns_with_usage"] == 2
    assert m["input_tokens"] == 2200
    assert m["output_tokens"] == 450
    assert m["reasoning_tokens"] == 110
    assert m["cache_hit_tokens"] == 1750
    assert m["cache_miss_tokens"] == 0
    assert m["cache_hit_ratio"] == 1.0
    # 200er-Block 2x -> 1 distinct repeated, 200 Bytes extra (H1/H2)
    assert m["repeated_blocks"]["distinct_repeated"] == 1
    assert m["repeated_blocks"]["repeated_bytes_wasted"] == 200
    # Text-Turns: 2x model.completed (assistantTexts + finalPromptText je
    # ein Block-Sample) + 1x prompt.submitted (data.prompt)
    assert m["context_chars_per_turn"]["turns_sampled"] == 3


def test_context_metrics_trajectory_no_double_count_snapshot():
    """messagesSnapshot (akkumulierter Kontext) wird NICHT als Turn-Text
    gezaehlt – nur assistantTexts/finalPromptText/prompt."""
    rec = json.dumps({"type": "model.completed", "data": {
        "usage": {"input": 1, "output": 1, "cacheRead": 1, "total": 3},
        "assistantTexts": ["kurz"],
        "messagesSnapshot": [{"role": "user", "content": "X" * 500}],
    }})
    m = compute_metrics(rec)
    curve = m["context_chars_per_turn"]
    assert curve["turns_sampled"] == 1
    assert curve["last_turn_chars"] < 100  # nur "kurz" (4 Zeichen), nicht 500


def test_cache_tokens_deepseek():
    usage = _deepseek_usage(hit=900, miss=100, inp=1000, out=50)
    hit, miss = cache_tokens(usage)
    assert (hit, miss) == (900, 100)


def test_cache_tokens_openai():
    usage = _openai_usage(inp=1000, out=50)
    hit, miss = cache_tokens(usage)
    assert (hit, miss) == (990, 10)


def test_cache_tokens_missing():
    assert cache_tokens({"input_tokens": 5}) == (0, 0)
    assert cache_tokens({}) == (0, 0)


def test_record_latency_ms_variants():
    assert record_latency_ms({"latencyMs": 123}) == 123.0
    assert record_latency_ms({"timing": {"totalMs": 42}}) == 42.0
    assert record_latency_ms({"type": "text"}) is None


def test_record_is_error():
    assert record_is_error({"type": "error"})
    assert record_is_error({"status": "failed"})
    assert not record_is_error({"type": "model", "status": "ok"})
    assert not record_is_error({"type": "text"})


def _transcript(n_turns=3, repeated_times=2):
    """Synthetisches Transkript: n Turns, je Turn wachsender Kontext; der
    200-Zeichen-Block wird in den ersten `repeated_times` Turns wiederholt
    (Issue-#113-Muster: wiederholte Tool-Bloecke = Kontext-Bloat)."""
    block = "X" * 200
    lines = []
    for i in range(n_turns):
        rec = {
            "type": "model",
            "usage": _deepseek_usage(hit=800, miss=200, inp=1000, out=100 + i),
            "latencyMs": 1000 + i * 100,
        }
        lines.append(json.dumps(rec))
        msg = {"type": "assistant", "text": f"Antwort {i}"}
        lines.append(json.dumps(msg))
        # Letzter Turn traegt den groessten Block (Kontext-Kurve steigt);
        # die ersten `repeated_times` Turns wiederholen den 200er-Block.
        tool = {
            "type": "tool",
            "result": block if i < repeated_times else "einzig" + "W" * 500,
        }
        lines.append(json.dumps(tool))
    return "\n".join(lines)


def test_compute_metrics_basic():
    m = compute_metrics(_transcript())
    assert m["records_parsed"] == 3 * 3
    assert m["turns_with_usage"] == 3
    assert m["input_tokens"] == 3000
    assert m["output_tokens"] == 100 + 101 + 102
    assert m["cache_hit_tokens"] == 2400
    assert m["cache_miss_tokens"] == 600
    assert m["cache_hit_ratio"] == 0.8
    # 200er-Block 2x -> 1 distinct repeated, 200 Bytes extra
    assert m["repeated_blocks"]["distinct_repeated"] == 1
    assert m["repeated_blocks"]["repeated_bytes_wasted"] == 200
    assert m["errors"] == 0
    assert m["latency_ms"]["samples"] == 3
    assert m["latency_ms"]["max_ms"] == 1200.0


def test_compute_metrics_context_curve():
    m = compute_metrics(_transcript(n_turns=3))
    curve = m["context_chars_per_turn"]
    # Sammlung pro Record mit Text-Bloecken: assistant + tool je Turn
    # (3 Turns × 2 Records) – kein Text, nur Groessen-Samples.
    assert curve["turns_sampled"] == 6
    assert curve["first_turn_chars"] is not None
    assert curve["last_turn_chars"] >= curve["first_turn_chars"]


def test_compute_metrics_workspace_markers():
    lines = [
        json.dumps({"type": "system", "text": "# AGENTS.md\nRolle: Engineer\n" + "y" * 200}),
        json.dumps({"type": "system", "text": "# AGENTS.md\nRolle: Engineer\n" + "y" * 200}),
        json.dumps({"type": "system", "text": "# MEMORY.md\nKontext\n" + "z" * 200}),
        json.dumps({"type": "user", "text": "normal"}),
    ]
    m = compute_metrics("\n".join(lines))
    assert m["workspace_marker_blocks"] >= 3
    assert m["repeated_blocks"]["distinct_repeated"] >= 1


def test_compute_metrics_errors():
    lines = [
        json.dumps({"type": "model", "usage": _deepseek_usage(1, 1, 2, 1)}),
        json.dumps({"type": "error", "status": "failed"}),
    ]
    m = compute_metrics("\n".join(lines))
    assert m["errors"] == 1


def test_compute_metrics_empty():
    m = compute_metrics("")
    assert m["turns_with_usage"] == 0
    assert m["input_tokens"] == 0
    assert m["cache_hit_ratio"] is None
    assert m["repeated_blocks"]["distinct_repeated"] == 0


def test_min_block_chars_respected():
    small = "a" * (MIN_BLOCK_CHARS - 1)
    lines = [
        json.dumps({"type": "tool", "result": small}),
        json.dumps({"type": "tool", "result": small}),
    ]
    m = compute_metrics("\n".join(lines))
    assert m["repeated_blocks"]["distinct_repeated"] == 0


def test_no_secrets_in_output():
    """Metriken enthalten nie Transkript-Text (nur Aggregate/Hashes)."""
    m = compute_metrics(_transcript())
    dump = json.dumps(m)
    assert "X" * 50 not in dump
    assert "Antwort" not in dump
