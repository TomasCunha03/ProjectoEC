"""Unit tests for SQL helper parsing and safety checks."""

import importlib
import sys
import types


def load_sql_tool():
    torch_mod = types.ModuleType("torch")

    def topk(scores, k):
        return types.SimpleNamespace(indices=list(range(k)))

    torch_mod.topk = topk
    sys.modules["torch"] = torch_mod

    st_mod = types.ModuleType("sentence_transformers")

    class DummySentenceTransformer:
        def __init__(self, *args, **kwargs):
            return None

        def encode(self, *args, **kwargs):
            return []

    st_mod.SentenceTransformer = DummySentenceTransformer
    st_mod.util = types.SimpleNamespace(cos_sim=lambda a, b: [[0]])
    sys.modules["sentence_transformers"] = st_mod

    yaml_mod = types.ModuleType("yaml")
    yaml_mod.safe_load = lambda *args, **kwargs: {}
    sys.modules["yaml"] = yaml_mod

    lc_mod = types.ModuleType("langchain_community")
    lc_utils = types.ModuleType("langchain_community.utilities")

    class DummySQLDatabase:
        @classmethod
        def from_uri(cls, uri):
            return cls()

    lc_utils.SQLDatabase = DummySQLDatabase
    sys.modules["langchain_community"] = lc_mod
    sys.modules["langchain_community.utilities"] = lc_utils

    lc_ollama = types.ModuleType("langchain_ollama")

    class DummyChatOllama:
        def __init__(self, *args, **kwargs):
            return None

        def invoke(self, prompt):
            return types.SimpleNamespace(content="SELECT 1")

    lc_ollama.ChatOllama = DummyChatOllama
    sys.modules["langchain_ollama"] = lc_ollama

    sys.modules.pop("chat_saude.tools.sql_tool", None)
    return importlib.import_module("chat_saude.tools.sql_tool")


def test_extract_sql_from_code_block():
    """Extracts raw SQL from a fenced code block."""
    sql_tool = load_sql_tool()

    raw = """
    ```sql
    SELECT * FROM table_name;
    ```
    """
    assert sql_tool._extract_sql(raw) == "SELECT * FROM table_name;"


def test_extract_sql_from_labelled_output():
    """Extracts SQL from labeled LLM output and normalizes whitespace."""
    sql_tool = load_sql_tool()

    raw = "SQLQuery: SELECT name FROM people\nWHERE id = 1;"
    assert sql_tool._extract_sql(raw) == "SELECT name FROM people WHERE id = 1"


def test_is_safe_query_allows_select_only():
    """Allows only SELECT and blocks unsafe statements."""
    sql_tool = load_sql_tool()

    assert sql_tool._is_safe_query("SELECT * FROM people") is True
    assert sql_tool._is_safe_query("DELETE FROM people") is False
    assert sql_tool._is_safe_query("SELECT * FROM people; DROP TABLE people") is False
