#!/usr/bin/env python3
"""Issue-#113-Metriken aus Session-Transkripten (read-only, Workflow 06).

Wertet bounded geholte Transkript-JSONL (tools/diagnose/diagnose.py) aus:
- Input/Output-Tokens je Turn (model-run usage-Felder; DeepSeek- und
  OpenAI-Formate werden beide erkannt)
- Cache-Hit-Anteil (prompt_cache_hit_tokens / input_tokens_details.cacheReadTokens)
- Kontext-Groesse je Turn (Zeichen-Schaetzung der Text-Bloecke)
- Wiederholte Nachrichten-Bloecke (normalisierter Text-Hash, >= min_block_chars)
- Workspace-/Memory-Einblendungen (Marker AGENTS.md/MEMORY.md, mehrfach)
- Fehler/Latenz (Fehler-Records, duration-Felder)

Defensiv: kaputte JSON-Zeilen werden uebersprungen, unbekannte Feldnamen
ignoriert – das Tool meldet, WAS es messen konnte (Nicht-Messbares wird als
"not_found"/0 ausgewiesen, nie geraten). Keine Secrets in der Ausgabe.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Marker fuer wiederkehrende System-/Workspace-Einblendungen (Issue #113 H3/H4)
WORKSPACE_MARKERS = ("AGENTS.md", "MEMORY.md", "SOUL.md", "IDENTITY.md", "USER.md")
MIN_BLOCK_CHARS = 100  # kuerzere Bloecke werden nicht auf Duplikate geprueft


def iter_records(text: str) -> Iterator[Dict[str, Any]]:
    """Liefert je nicht-leerer Zeile ein JSON-Objekt (defensiv)."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            yield obj


def _first(d: Dict[str, Any], keys: Tuple[str, ...], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def find_usage(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Usage-Block eines model-run-Records (Top-Level oder usage-Subobjekt)."""
    if isinstance(record.get("usage"), dict):
        return record["usage"]
    for key in ("modelRun", "completion", "run"):
        sub = record.get(key)
        if isinstance(sub, dict) and isinstance(sub.get("usage"), dict):
            return sub["usage"]
    # flach: Record IST der Usage-Block
    if "input_tokens" in record or "output_tokens" in record:
        return record
    return None


def cache_tokens(usage: Dict[str, Any]) -> Tuple[int, int]:
    """(cache_hit, cache_miss) – DeepSeek- und OpenAI-Feldnamen."""
    details = usage.get("input_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}
    hit = usage.get("prompt_cache_hit_tokens", details.get("cacheReadTokens", 0)) or 0
    miss = usage.get("prompt_cache_miss_tokens", details.get("cacheWriteTokens", 0)) or 0
    try:
        return int(hit), int(miss)
    except (TypeError, ValueError):
        return 0, 0


def record_latency_ms(record: Dict[str, Any]) -> Optional[float]:
    """Latenz (ms) aus gaengigen duration-Feldern."""
    val = _first(record, ("latencyMs", "durationMs", "elapsedMs", "timingMs"))
    if val is None:
        for key in ("timing", "meta"):
            sub = record.get(key)
            if isinstance(sub, dict):
                val = _first(sub, ("latencyMs", "durationMs", "elapsedMs", "totalMs"))
                if val is not None:
                    break
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def record_is_error(record: Dict[str, Any]) -> bool:
    if record.get("type") == "error" or record.get("kind") == "error":
        return True
    status = record.get("status") or record.get("error")
    return isinstance(status, str) and status.lower() in ("error", "failed")


def text_blocks(record: Dict[str, Any]) -> List[str]:
    """Text-Bloecke eines Records (Nachrichten-/Tool-Text)."""
    blocks: List[str] = []
    for key in ("text", "content", "result", "output", "transcript"):
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            blocks.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    blocks.append(item)
                elif isinstance(item, dict):
                    t = item.get("text") or item.get("content")
                    if isinstance(t, str) and t.strip():
                        blocks.append(t)
    msg = record.get("message")
    if isinstance(msg, dict):
        for key in ("content", "text"):
            val = msg.get(key)
            if isinstance(val, str) and val.strip():
                blocks.append(val)
    return blocks


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compute_metrics(
    transcript_text: str, min_block_chars: int = MIN_BLOCK_CHARS
) -> Dict[str, Any]:
    """Aggregiert #113-Metriken aus Transkript-JSONL (bounded, read-only)."""
    records = list(iter_records(transcript_text))
    turns = 0
    input_tokens = 0
    output_tokens = 0
    cache_hit = 0
    cache_miss = 0
    latencies: List[float] = []
    errors = 0
    block_hashes: Dict[str, int] = {}
    block_sizes: Dict[str, int] = {}
    context_chars_per_turn: List[int] = []
    workspace_blocks = 0

    for rec in records:
        usage = find_usage(rec)
        if usage:
            turns += 1
            input_tokens += int(usage.get("input_tokens", 0) or 0)
            output_tokens += int(usage.get("output_tokens", 0) or 0)
            hit, miss = cache_tokens(usage)
            cache_hit += hit
            cache_miss += miss
        lat = record_latency_ms(rec)
        if lat is not None:
            latencies.append(lat)
        if record_is_error(rec):
            errors += 1
        blocks = text_blocks(rec)
        turn_chars = 0
        for b in blocks:
            norm = _norm(b)
            if not norm:
                continue
            turn_chars += len(norm)
            if len(norm) >= min_block_chars:
                block_hashes[norm] = block_hashes.get(norm, 0) + 1
                block_sizes[norm] = len(norm)
            if any(marker in norm for marker in WORKSPACE_MARKERS):
                workspace_blocks += 1
        if blocks:
            context_chars_per_turn.append(turn_chars)

    repeated_blocks = {h: c for h, c in block_hashes.items() if c > 1}
    repeated_bytes = sum(block_sizes[h] * (c - 1) for h, c in repeated_blocks.items())
    total_blocks = sum(block_hashes.values())
    total_bytes = sum(block_sizes.values())

    cache_total = cache_hit + cache_miss
    metrics: Dict[str, Any] = {
        "records_parsed": len(records),
        "turns_with_usage": turns,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_hit_tokens": cache_hit,
        "cache_miss_tokens": cache_miss,
        "cache_hit_ratio": round(cache_hit / cache_total, 4) if cache_total else None,
        "context_chars_per_turn": {
            "turns_sampled": len(context_chars_per_turn),
            "first_turn_chars": context_chars_per_turn[0] if context_chars_per_turn else None,
            "last_turn_chars": context_chars_per_turn[-1] if context_chars_per_turn else None,
            "avg_turn_chars": round(sum(context_chars_per_turn) / len(context_chars_per_turn), 1)
            if context_chars_per_turn else None,
        },
        "repeated_blocks": {
            "distinct_repeated": len(repeated_blocks),
            "repeated_occurrences_extra": repeated_bytes,
            "repeated_bytes_wasted": repeated_bytes,
            "block_total_bytes": total_bytes,
        },
        "workspace_marker_blocks": workspace_blocks,
        "errors": errors,
        "latency_ms": {
            "samples": len(latencies),
            "avg_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "max_ms": round(max(latencies), 1) if latencies else None,
        },
    }
    return metrics
