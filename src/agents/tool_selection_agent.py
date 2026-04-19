"""
Standalone tool selection via LLM (used by CLI/scripts).

The main API chat path uses ``conversation_router.route_conversation`` instead, which merges
routing + tool choice in one structured call.
"""

import json
import os
import re

import ollama
import yaml

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

logger.info("Tool selection agent using model: %s", LLM_MODEL)


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
    """Select appropriate tool based on user question."""
    system_prompt = load_prompt("prompts.yaml", "system_prompt")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    client = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(model=LLM_MODEL, messages=messages, options={"temperature": 0.0})
    answer = response["message"]["content"].strip()

    # Parse response as JSON: { "tools": ["RAG", "SQL", ...] }
    parsed = None
    try:
        parsed = json.loads(answer)
    except Exception:
        match = re.search(r"\{.*\}", answer, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                logger.warning("Tool selection: failed to parse LLM response: %s", answer[:200])
                parsed = None

    tool_map = {
        "RAG": "rag_answer",
        "SQL": "sql_query",
        "MONGO": "mongo_query",
    }

    selected_tools: list[str] = []
    tools_list = None
    if isinstance(parsed, dict):
        for k, v in parsed.items():
            if isinstance(k, str) and k.strip().lower() == "tools":
                tools_list = v
                break

    if isinstance(tools_list, list):
        for t in tools_list:
            if not isinstance(t, str):
                continue
            key = t.strip().upper()
            if key in tool_map:
                selected_tools.append(tool_map[key])

    # De-duplicate while preserving order
    seen = set()
    ordered_tools: list[str] = []
    for t in selected_tools:
        if t not in seen:
            seen.add(t)
            ordered_tools.append(t)

    logger.info("Tool selection result: tools=%s query=%s", ordered_tools, user_question[:80])
    return {"tools": ordered_tools, "query": user_question}
