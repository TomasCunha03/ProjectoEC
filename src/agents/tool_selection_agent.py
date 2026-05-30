"""
Tool-selection agent for the chat_saude system.

Responsibility: given a natural-language user question, decide which backend
tool(s) should handle it.  The decision is made by prompting a small local LLM
(served via Ollama) and parsing its JSON response into an ordered list of
internal tool identifiers.

The agent is intentionally stateless — every call to select_tool() is a fresh
request to the LLM.  No conversation history is maintained here; that is the
responsibility of the orchestration layer.

Available tools (LLM label -> internal name):
  RAG       -> rag_answer       (vector-similarity retrieval over documents)
  SQL       -> sql_query        (structured query against PostgreSQL)
  MONGO     -> mongo_query      (document query against MongoDB)
  DASHBOARD -> dashboard_query  (pre-built analytics / dashboard queries)
"""

import json
import os
import re

import ollama
import yaml

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

# The model name and Ollama host are read from the environment so that
# different deployments (dev, staging, prod) can swap models without code changes.
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

logger.info("Tool selection agent using model: %s", LLM_MODEL)

# Maps the uppercase labels the LLM is instructed to emit to the internal
# function/tool names used by the orchestration layer.
TOOL_MAP = {
    "RAG": "rag_answer",
    "SQL": "sql_query",
    "MONGO": "mongo_query",
    "DASHBOARD": "dashboard_query",
}


def _map_tool_name(raw: str) -> str | None:
    """Translate a raw LLM-emitted label to its internal tool name, or None if unknown."""
    key = raw.strip().upper()
    return TOOL_MAP.get(key)


def _consume_tool_value(value, out: list[str]) -> None:
    """Recursively collect tool names from strings, lists, or tool/tools dict keys.

    Small LLMs produce inconsistent JSON shapes — sometimes a bare string
    ("RAG"), sometimes a list (["RAG", "SQL"]), and sometimes a dict with a
    "tool" or "tools" key.  This function handles all three shapes so that
    the caller does not need to branch on the structure.

    Args:
        value: The parsed JSON value to inspect (str, list, or dict).
        out:   Accumulator list; recognized tool names are appended in place.
    """
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
            # Only recurse into keys that are semantically "the tool field".
            # Other dict keys (e.g. "explanation") are intentionally ignored.
            if key.strip().lower() in ("tool", "tools", "name"):
                _consume_tool_value(val, out)


def extract_selected_tools(parsed) -> list[str]:
    """Normalize LLM JSON into internal tool names (deduplicated, order preserved).

    Walks the parsed JSON structure via _consume_tool_value, then removes any
    duplicate tool names while preserving the order in which they first appear.
    Preserving order matters because the orchestration layer may execute tools
    sequentially and the LLM's ordering encodes priority.

    Args:
        parsed: The Python object produced by json.loads() on the LLM response,
                or None if parsing failed.

    Returns:
        A deduplicated list of internal tool name strings (e.g. ["rag_answer"]).
        Returns an empty list if parsed is None or contains no recognized tools.
    """
    if parsed is None:
        return []

    raw_names: list[str] = []
    _consume_tool_value(parsed, raw_names)

    # Deduplicate while maintaining the original order using a seen set as a
    # fast membership test alongside an ordered output list.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in raw_names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def parse_tool_selection_response(answer: str):
    """Parse JSON from LLM output; tolerate markdown fences and embedded blobs.

    LLMs — especially small ones — often wrap JSON in markdown code fences
    (```json ... ```) or embed it inside a longer natural-language reply.
    This function attempts three strategies in order:

    1. Strip markdown fences and parse the whole remaining text as JSON.
    2. Extract the first {...} JSON object blob and parse it.
    3. Extract the first [...] JSON array blob and parse it.

    Args:
        answer: The raw string content returned by the LLM.

    Returns:
        The parsed Python object (dict or list) if any strategy succeeds,
        or None if the response contains no recognizable JSON.
    """
    text = answer.strip()
    if text.startswith("```"):
        # Strip opening fence (optionally with a language tag like ```json)
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        # Strip closing fence
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back to scanning for a JSON object or array embedded in prose.
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
    return None


def load_prompt(file_path="prompts.yaml", key="system_prompt") -> str:
    """Load the YAML file and extract the prompt for the given key.

    Relative paths are resolved relative to the directory that contains this
    module, not the current working directory, so the agent works regardless
    of where the process is launched from.

    Args:
        file_path: Path to the YAML prompts file.  Relative paths are anchored
                   to this module's directory.
        key:       Top-level key in the YAML file whose value is the prompt string.

    Returns:
        The prompt string, or an empty string if the file is missing or the
        key does not exist.
    """
    # Anchor relative paths to this file's directory so the agent can be
    # invoked from any working directory.
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
    """Select appropriate backend tools for a user question using the configured LLM.

    Sends the question to the Ollama-hosted LLM with a system prompt that
    instructs it to reply with a JSON list of tool labels.  The raw LLM
    output is then parsed and mapped to internal tool names.

    Temperature is fixed at 0.0 so that repeated calls for the same question
    produce deterministic results — tool selection is a classification task,
    not a creative one.

    Fallback behaviour: if the LLM returns no recognizable tools (empty JSON,
    unparseable output, etc.) the function defaults to "rag_answer" rather
    than failing, because RAG is the most general-purpose retrieval backend
    and small models frequently produce malformed JSON.

    Args:
        user_question: The raw natural-language question from the user.

    Returns:
        A dict with two keys:
          - "tools": ordered list of internal tool name strings.
          - "query": the original user_question, passed through unchanged so
                     the caller does not need to carry it separately.
    """
    logger.info("Using LLM for tool selection: %s", user_question[:80])
    system_prompt = load_prompt("prompts.yaml", "system_prompt")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    client = ollama.Client(host=OLLAMA_HOST)
    # temperature=0.0 makes the output deterministic for the same input.
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
