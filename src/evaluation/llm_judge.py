"""
AyurKosha — LLM-as-Judge Evaluation
Uses Claude to score a generated answer against the gold answer.

This is the ONLY part of the evaluation suite that costs Anthropic credits.
It's optional: the eval runner only calls it when explicitly enabled
(--judge), so retrieval and deterministic generation metrics run for free.
Fails safe: on any API error (including an exhausted credit balance) it
returns a result with ``ok=False`` and the error string, so one judging
failure never aborts a whole eval run.

Build this in: Phase 6
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None

_JUDGE_SYSTEM = (
    "You are a strict evaluator of Ayurvedic question-answering systems. "
    "You score a candidate answer against a gold reference answer. Respond "
    "with ONLY a JSON object, no prose."
)

_JUDGE_TEMPLATE = """Score the candidate answer on three axes, each an integer 0-10:
- faithfulness: are the claims consistent with the gold answer and not fabricated?
- relevance: does it actually address the question asked?
- completeness: does it cover the key points present in the gold answer?

Question:
{question}

Gold answer:
{gold_answer}

Candidate answer:
{candidate_answer}

Respond with ONLY this JSON shape:
{{"faithfulness": <int>, "relevance": <int>, "completeness": <int>, "reasoning": "<one sentence>"}}"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _get_client():
    """Lazily construct and cache the Anthropic client."""
    global _client
    if _client is not None:
        return _client
    import anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def judge_answer(
    question: str,
    candidate_answer: str,
    gold_answer: str,
) -> dict[str, Any]:
    """Score a candidate answer against the gold answer with Claude.

    Returns:
        On success: {"ok": True, "faithfulness": int, "relevance": int,
        "completeness": int, "reasoning": str}. On any failure:
        {"ok": False, "error": str} — never raises.
    """
    prompt = _JUDGE_TEMPLATE.format(
        question=question,
        gold_answer=gold_answer,
        candidate_answer=candidate_answer,
    )
    try:
        client = _get_client()
        resp = client.messages.create(
            model=settings.generation_model,
            max_tokens=300,
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        scores = _parse_scores(text)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully (e.g. no credits)
        logger.warning("LLM judge failed (%s).", exc)
        return {"ok": False, "error": str(exc)}

    if scores is None:
        return {"ok": False, "error": f"Unparseable judge response: {text[:200]!r}"}
    scores["ok"] = True
    return scores


def _parse_scores(text: str) -> dict[str, Any] | None:
    """Extract the JSON score object from the judge's response text."""
    match = _JSON_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    out: dict[str, Any] = {}
    for key in ("faithfulness", "relevance", "completeness"):
        try:
            out[key] = int(data.get(key))
        except (TypeError, ValueError):
            return None
    out["reasoning"] = str(data.get("reasoning", ""))
    return out
