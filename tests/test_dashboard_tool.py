"""Unit tests for dashboard tool filter extraction with stubs."""

import importlib
import sys
import types


def load_dashboard_tool(*, chat_content=None, client_init_raises=False):
    class DummyClient:
        def __init__(self, host=None):
            if client_init_raises:
                raise AssertionError("Client should not be created")
            self.host = host

        def chat(self, model, messages, options):
            return {"message": {"content": chat_content or "{}"}}

    ollama_mod = types.ModuleType("ollama")
    ollama_mod.Client = DummyClient
    sys.modules["ollama"] = ollama_mod

    sys.modules.pop("chat_saude.tools.dashboard_tool", None)
    return importlib.import_module("chat_saude.tools.dashboard_tool")


def test_dashboard_tool_reset_short_circuits():
    """Clears filters immediately on reset requests."""
    dashboard_tool = load_dashboard_tool(client_init_raises=True)

    response, filters = dashboard_tool.dashboard_tool("reset dashboard")

    assert response == dashboard_tool.FIXED_RESPONSE
    assert filters == {}


def test_dashboard_tool_regex_fallback_when_llm_invalid():
    """Uses regex fallback when the LLM response is not JSON."""
    dashboard_tool = load_dashboard_tool(chat_content="nonsense")

    response, filters = dashboard_tool.dashboard_tool("BCG 2012 to 2021, top 20")

    assert response == dashboard_tool.FIXED_RESPONSE
    assert filters["vaccine_code"] == "BCG"
    assert filters["immunization_start_year"] == 2012
    assert filters["immunization_end_year"] == 2021
    assert filters["top_n"] == 20


def test_dashboard_tool_parses_llm_json_and_coerces_types():
    """Coerces types, applies aliases, and drops unknown fields."""
    raw = """
    {"top_n": 1000, "vaccine_code": "bcg", "bcg_start_year": "2012", "bcg_end_year": "2019", "unknown": 1}
    """
    dashboard_tool = load_dashboard_tool(chat_content=raw)

    response, filters = dashboard_tool.dashboard_tool("show vaccine data")

    assert response == dashboard_tool.FIXED_RESPONSE
    assert filters["top_n"] == 100
    assert filters["vaccine_code"] == "BCG"
    assert filters["immunization_start_year"] == 2012
    assert filters["immunization_end_year"] == 2019
