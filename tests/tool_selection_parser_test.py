import json

from agents.tool_selection_agent import extract_selected_tools, parse_tool_selection_response


def test_canonical_tools_object():
    parsed = json.loads('{ "tools": ["MONGO", "SQL"] }')
    assert extract_selected_tools(parsed) == ["mongo_query", "sql_query"]


def test_singular_tool_object():
    parsed = json.loads('{ "tool": "MONGO" }')
    assert extract_selected_tools(parsed) == ["mongo_query"]


def test_bare_tool_list():
    parsed = json.loads('["MONGO", "RAG"]')
    assert extract_selected_tools(parsed) == ["mongo_query", "rag_answer"]


def test_list_of_tool_objects():
    parsed = json.loads('[{"tool": "MONGO"}]')
    assert extract_selected_tools(parsed) == ["mongo_query"]


def test_parse_embedded_array():
    answer = 'Here is the result:\n[{"tool": "MONGO"}]\n'
    assert extract_selected_tools(parse_tool_selection_response(answer)) == ["mongo_query"]


def test_parse_markdown_fence():
    answer = '```json\n{"tools": ["SQL"]}\n```'
    assert extract_selected_tools(parse_tool_selection_response(answer)) == ["sql_query"]


def test_unknown_tools_ignored():
    parsed = json.loads('{"tools": ["MONGO", "FAKE"]}')
    assert extract_selected_tools(parsed) == ["mongo_query"]
