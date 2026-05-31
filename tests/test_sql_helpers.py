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


def test_sanitize_generated_sql_removes_treat_activity_filter():
    """Strips hallucinated activity = 'Treat' filters."""
    sql_tool = load_sql_tool()

    raw = "SELECT drug_name FROM drugs_side_effects dsd WHERE dsd.medical_condition ILIKE '%AIDS%' AND dsd.activity = 'Treat' LIMIT 10"
    assert sql_tool._sanitize_generated_sql(raw) == ("SELECT drug_name FROM drugs_side_effects dsd WHERE dsd.medical_condition ILIKE '%AIDS%' LIMIT 10")


def test_try_deterministic_sql_disease_count_and_names():
    """Builds scalar-subquery SQL for count plus sample disease names."""
    sql_tool = load_sql_tool()

    question = "Using your SQL health database, how many distinct diseases are recorded, and list three disease names from the diseases table."
    sql = sql_tool._try_deterministic_sql(question)
    assert sql is not None
    assert "COUNT(DISTINCT name)" in sql
    assert "LIMIT 3" in sql


def test_try_deterministic_sql_drugs_for_condition():
    """Builds direct drugs_side_effects lookup for treatment questions."""
    sql_tool = load_sql_tool()

    sql = sql_tool._try_deterministic_sql("Show me 10 drugs to treat aids")
    assert sql is not None
    assert "drugs_side_effects" in sql
    assert "ILIKE '%aids%'" in sql
    assert "LIMIT 10" in sql
    assert "activity" not in sql


def test_try_deterministic_sql_side_effects_of_drug():
    """Builds drug_name lookup for side-effect questions."""
    sql_tool = load_sql_tool()

    sql = sql_tool._try_deterministic_sql("What are the side effects of doxycycline")
    assert sql is not None
    assert "side_effects" in sql
    assert "ILIKE '%doxycycline%'" in sql
    assert "generic_name" in sql
