"""
Hybrid router: deterministic hints first, then LLM structured routing, then health fallback.

Canned wording lives in api/canned.py — the model only chooses keys for the LLM path.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import ollama
import yaml

from agents.router_heuristics import looks_like_health_question_for_fallback, try_heuristic_route
from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

VALID_CANNED_KEYS = frozenset(
    {
        "emergency",
        "identity",
        "capabilities",
        "architecture",
        "bot_feelings",
        "thanks",
        "vague_symptom",
        "off_topic",
        "unclear",
    }
)
VALID_TOOL_TOKENS = ("RAG", "SQL", "MONGO")
TOOL_MAP = {"RAG": "rag_answer", "SQL": "sql_query", "MONGO": "mongo_query"}

_FALLBACK_HEALTH_TOOLS = [TOOL_MAP["RAG"], TOOL_MAP["MONGO"]]


@dataclass
class RouteDecision:
    """mode=direct: use canned_key from api/canned. mode=tools: run ordered tools."""

    mode: str  # "direct" | "tools"
    canned_key: str | None
    tools: list[str]  # internal names: rag_answer, sql_query, mongo_query


def _load_router_prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "prompts.yaml")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return (data.get("router_prompt") or "").strip()


def _parse_router_json(raw: str) -> dict | None:
    raw = raw.strip()
    # Models often wrap JSON in markdown fences or add a preamble.
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE | re.MULTILINE)
    raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
    raw = raw.strip()

    def _try_json(s: str) -> dict | None:
        try:
            val = json.loads(s)
            return val if isinstance(val, dict) else None
        except json.JSONDecodeError:
            return None

    if parsed := _try_json(raw):
        return parsed

    start = raw.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    if parsed := _try_json(raw[start : i + 1]):
                        return parsed
                    break

    m = re.search(r"\{[\s\S]*\}", raw)
    if m and (parsed := _try_json(m.group(0))):
        return parsed

    return None


def _decision_from_llm_parsed(parsed: dict, raw_answer: str) -> RouteDecision:
    reason = parsed.get("reason")
    if isinstance(reason, str) and reason.strip():
        logger.info("Router reason: %s", reason.strip()[:500])

    route = str(parsed.get("route", "")).strip().lower()
    if route == "tool":
        route = "tools"

    canned_key = parsed.get("canned_key")
    if isinstance(canned_key, str):
        canned_key = canned_key.strip().lower()
    else:
        canned_key = None

    tools_raw = parsed.get("tools")
    selected: list[str] = []
    if isinstance(tools_raw, list):
        seen: set[str] = set()
        for t in tools_raw:
            if not isinstance(t, str):
                continue
            key = t.strip().upper()
            if key in TOOL_MAP and key not in seen:
                seen.add(key)
                selected.append(TOOL_MAP[key])

    if route == "direct":
        if canned_key not in VALID_CANNED_KEYS:
            logger.warning("Router: invalid canned_key %r, using unclear", canned_key)
            canned_key = "unclear"
        return RouteDecision(mode="direct", canned_key=canned_key, tools=[])

    if route == "tools":
        if not selected:
            logger.warning(
                "Router: route=tools but no valid tools in list; defaulting to RAG. Raw tools=%r",
                tools_raw,
            )
            selected = [TOOL_MAP["RAG"]]
        return RouteDecision(mode="tools", canned_key=None, tools=selected)

    logger.warning("Router: unknown route %r, using unclear. Raw=%s", route, raw_answer[:200])
    return RouteDecision(mode="direct", canned_key="unclear", tools=[])


def _route_via_llm(user_message: str) -> RouteDecision:
    system_prompt = _load_router_prompt()
    client = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        options={"temperature": 0.0},
    )
    answer = response["message"]["content"].strip()
    parsed = _parse_router_json(answer)

    if not isinstance(parsed, dict):
        logger.warning("Router: failed to parse JSON, defaulting to unclear. Raw=%s", answer[:300])
        return RouteDecision(mode="direct", canned_key="unclear", tools=[])

    return _decision_from_llm_parsed(parsed, answer)


def _maybe_health_fallback(user_message: str, decision: RouteDecision) -> RouteDecision:
    if (
        decision.mode == "direct"
        and decision.canned_key == "unclear"
        and looks_like_health_question_for_fallback(user_message)
    ):
        logger.warning("Router: overriding unclear with health fallback -> RAG+MONGO")
        return RouteDecision(mode="tools", canned_key=None, tools=list(_FALLBACK_HEALTH_TOOLS))
    return decision


def route_conversation(user_message: str) -> RouteDecision:
    """Heuristic layer → LLM JSON router → unclear fallback for health-like questions."""

    heuristic = try_heuristic_route(user_message)
    if heuristic is not None:
        logger.info(
            "Router heuristic: mode=%s canned_key=%s tools=%s",
            heuristic.mode,
            heuristic.canned_key,
            heuristic.tools,
        )
        return heuristic

    llm_decision = _route_via_llm(user_message)
    return _maybe_health_fallback(user_message, llm_decision)
