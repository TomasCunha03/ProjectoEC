"""Unit tests for ChatService orchestration using stubs."""

import importlib
import sys
import types


def _make_pkg(name: str) -> types.ModuleType:
    pkg = types.ModuleType(name)
    pkg.__path__ = []
    return pkg


def load_chat_service(
    *,
    apply_rules=None,
    select_tool=None,
    rag_tool=None,
    sql_query=None,
    mongo_query=None,
    dashboard_tool=None,
):
    sys.modules["api"] = _make_pkg("api")
    rules_mod = types.ModuleType("api.rules")
    rules_mod.apply_rules = apply_rules or (lambda message: None)
    sys.modules["api.rules"] = rules_mod

    sys.modules["agents"] = _make_pkg("agents")
    select_mod = types.ModuleType("agents.tool_selection_agent")
    select_mod.select_tool = select_tool or (lambda message: {"tools": []})
    sys.modules["agents.tool_selection_agent"] = select_mod

    rag_mod = types.ModuleType("chat_saude.tools.rag_tool")
    rag_mod.rag_tool = rag_tool or (lambda message: "rag")
    sys.modules["chat_saude.tools.rag_tool"] = rag_mod

    sql_mod = types.ModuleType("chat_saude.tools.sql_tool")
    sql_mod.sql_query = sql_query or (lambda message: "sql")
    sys.modules["chat_saude.tools.sql_tool"] = sql_mod

    mongo_mod = types.ModuleType("chat_saude.tools.mongo_tool")
    mongo_mod.mongo_query = mongo_query or (lambda message: "mongo")
    sys.modules["chat_saude.tools.mongo_tool"] = mongo_mod

    dash_mod = types.ModuleType("chat_saude.tools.dashboard_tool")
    dash_mod.dashboard_tool = dashboard_tool or (lambda message: ("dashboard", {}))
    sys.modules["chat_saude.tools.dashboard_tool"] = dash_mod

    sys.modules.pop("chat_saude.services.chat_service", None)
    return importlib.import_module("chat_saude.services.chat_service")


def test_is_dashboard_request_detects_explicit_and_implicit():
    """Detects dashboard intent via explicit and implicit cues."""
    chat_service = load_chat_service()

    assert chat_service._is_dashboard_request("show dashboard please") is True
    assert chat_service._is_dashboard_request("show chronic data for Texas") is True
    assert chat_service._is_dashboard_request("dashboard status") is False


def test_execute_ordered_tools_resilient_reuses_rag_on_failure():
    """Uses existing RAG answer when a later tool fails."""
    chat_service = load_chat_service()

    def rag_ok(message: str) -> str:
        return "rag ok"

    def sql_fail(message: str) -> str:
        raise RuntimeError("sql down")

    replies, degraded = chat_service._execute_ordered_tools_resilient(
        "hello",
        ["rag_answer", "sql_query"],
        {"rag_answer": rag_ok, "sql_query": sql_fail},
        {"rag_answer": "rag", "sql_query": "sql"},
    )

    assert replies["rag_answer"] == "rag ok"
    assert replies["sql_query"] == "rag ok"
    assert degraded is True


def test_execute_ordered_tools_resilient_recovers_with_rag():
    """Calls recovery RAG when no prior RAG answer is available."""
    chat_service = load_chat_service()

    def sql_fail(message: str) -> str:
        raise RuntimeError("sql down")

    chat_service.rag_tool = lambda message: "recovered"

    replies, degraded = chat_service._execute_ordered_tools_resilient(
        "hello",
        ["sql_query"],
        {"sql_query": sql_fail},
        {"sql_query": "sql"},
    )

    assert replies["sql_query"] == "recovered"
    assert degraded is True


def test_handle_chat_short_circuits_on_rules():
    """Stops early when rules return a response."""

    def select_tool_fail(message: str):
        raise AssertionError("select_tool should not run")

    chat_service = load_chat_service(
        apply_rules=lambda message: "rule response",
        select_tool=select_tool_fail,
    )

    result = chat_service.ChatService().handle_chat("hello")

    assert result["response"] == "rule response"
    assert result["tool_used"] == "rules"


def test_handle_chat_combines_tool_outputs():
    """Formats combined responses when multiple tools are selected."""
    chat_service = load_chat_service(
        apply_rules=lambda message: None,
        select_tool=lambda message: {"tools": ["rag_answer", "sql_query"]},
        rag_tool=lambda message: "rag reply",
        sql_query=lambda message: "sql reply",
    )

    result = chat_service.ChatService().handle_chat("stats and explanation")

    assert result["response"] == "RAG answer:\nrag reply\n\nSQL answer:\nsql reply"
    assert result["tools_used"] == "rag_answer,sql_query"
    assert result["tool_used"] == "rag_answer"


def test_handle_chat_dashboard_fast_path():
    """Handles keyword-matched dashboard requests before rules."""

    def apply_rules_fail(message: str):
        raise AssertionError("apply_rules should not run")

    def select_tool_fail(message: str):
        raise AssertionError("select_tool should not run")

    chat_service = load_chat_service(
        apply_rules=apply_rules_fail,
        select_tool=select_tool_fail,
        dashboard_tool=lambda message: ("dash reply", {"country": "PT"}),
    )

    result = chat_service.ChatService().handle_chat("show dashboard for Portugal")

    assert result["response"] == "dash reply"
    assert result["tool_used"] == "dashboard_query"
    assert result["dashboard_filters"] == {"country": "PT"}


def test_handle_chat_dashboard_selected_by_agent():
    """Handles dashboard tool selection from the agent decision."""
    chat_service = load_chat_service(
        apply_rules=lambda message: None,
        select_tool=lambda message: {"tools": ["dashboard_query"]},
        dashboard_tool=lambda message: ("dash reply", {"region": "EU"}),
    )

    result = chat_service.ChatService().handle_chat("show regional breakdown")

    assert result["response"] == "dash reply"
    assert result["tool_used"] == "dashboard_query"
    assert result["dashboard_filters"] == {"region": "EU"}
