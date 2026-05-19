import json
import os
import re

import ollama
import yaml

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

logger.info("Tool selection agent using model: %s", LLM_MODEL)

TOOL_MAP = {
    "RAG": "rag_answer",
    "SQL": "sql_query",
    "MONGO": "mongo_query",
    "DASHBOARD": "dashboard_query",
}


def _map_tool_name(raw: str) -> str | None:
    key = raw.strip().upper()
    return TOOL_MAP.get(key)


def _consume_tool_value(value, out: list[str]) -> None:
    """Recursively collect tool names from strings, lists, or tool/tools dict keys."""
    if isinstance(value, str):
        mapped = _map_tool_name(value)
        if mapped:
            out.append(mapped)
        return
    if isinstance(value, list):
        for item in value:
            _consume_tool_value(item, out)
        return
    if isinstance(value, dict):
        for key, val in value.items():
            if not isinstance(key, str):
                continue
            if key.strip().lower() in ("tool", "tools", "name"):
                _consume_tool_value(val, out)


def extract_selected_tools(parsed) -> list[str]:
    """Normalize LLM JSON into internal tool names (deduplicated, order preserved)."""
    if parsed is None:
        return []

    raw_names: list[str] = []
    _consume_tool_value(parsed, raw_names)

    seen: set[str] = set()
    ordered: list[str] = []
    for name in raw_names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def parse_tool_selection_response(answer: str):
    """Parse JSON from LLM output; tolerate markdown fences and embedded blobs."""
    text = answer.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
    return None


def load_prompt(file_path="prompts.yaml", key="system_prompt") -> str:
    """Load the YAML file and extract the prompt for the given key."""

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.path.dirname(__file__), file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            prompts = yaml.safe_load(file)
            return prompts.get(key, "")
    except FileNotFoundError:
        print(f"Error: File {file_path} not found!")
        return ""
    except Exception as e:
        print(f"Error reading YAML: {e}")
        return ""


def select_tool(user_question: str) -> dict:
    """Select appropriate tools using the configured LLM (Ollama)."""
    logger.info("Using LLM for tool selection: %s", user_question[:80])
    system_prompt = load_prompt("prompts.yaml", "system_prompt")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    client = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(model=LLM_MODEL, messages=messages, options={"temperature": 0.0})
    answer = response["message"]["content"].strip()

    parsed = parse_tool_selection_response(answer)
    if parsed is None:
        logger.warning("Tool selection: failed to parse LLM response: %s", answer[:200])

    ordered_tools = extract_selected_tools(parsed)

    if not ordered_tools:
        logger.warning(
            "Tool selection returned no tools (model=%s). Raw LLM output (truncated): %r",
            LLM_MODEL,
            answer[:800],
        )
        # Small models often break JSON or return []. Domain rules already accepted the query.
        ordered_tools = ["rag_answer"]
        logger.info("Falling back to rag_answer after empty tool list")

    logger.info("Tool selection result: tools=%s query=%s", ordered_tools, user_question[:80])
    return {"tools": ordered_tools, "query": user_question}
