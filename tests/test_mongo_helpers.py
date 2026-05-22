"""Unit tests for Mongo context helpers with stubbed access."""

import importlib
import sys
import types


def load_mongo_tool():
    sys.modules.setdefault("ollama", types.ModuleType("ollama"))

    pymongo_mod = types.ModuleType("pymongo")

    class DummyMongoClient:
        def __init__(self, *args, **kwargs):
            return None

    pymongo_mod.MongoClient = DummyMongoClient
    sys.modules["pymongo"] = pymongo_mod

    sys.modules.pop("chat_saude.tools.mongo_tool", None)
    return importlib.import_module("chat_saude.tools.mongo_tool")


def test_build_context_search_indicators():
    """Formats indicator search results into context text."""
    mongo_tool = load_mongo_tool()

    mongo_tool._search_indicators = lambda db, keyword: [{"IndicatorCode": "A1", "IndicatorName": "Alpha"}]

    result = mongo_tool._build_context("search_indicators", {"keyword": "alpha"}, db={})

    assert "A1" in result
    assert "Alpha" in result


def test_build_context_get_dimension_values():
    """Formats dimension values into context text."""
    mongo_tool = load_mongo_tool()

    mongo_tool._get_dimension_values = lambda db, code: [{"Code": "PT", "Title": "Portugal"}]

    result = mongo_tool._build_context("get_dimension_values", {"dimension_code": "country"}, db={})

    assert "[PT]" in result
    assert "Portugal" in result


def test_build_context_list_collections():
    """Formats available collection names."""
    mongo_tool = load_mongo_tool()

    mongo_tool._list_collections = lambda db: ["collection_a", "collection_b"]

    result = mongo_tool._build_context("list_collections", {}, db={})

    assert "collection_a" in result
    assert "collection_b" in result


def test_build_context_search_disease_info_strips_html():
    """Strips HTML tags from disease summary context."""
    mongo_tool = load_mongo_tool()

    mongo_tool._search_disease_info = lambda db, keyword: {
        "title": "Flu",
        "full_summary": "<p>short <b>summary</b></p>",
        "url": "http://example.com",
    }

    result = mongo_tool._build_context("search_disease_info", {"keyword": "flu"}, db={})

    assert "short summary" in result
    assert "<p>" not in result


def test_build_context_action_not_recognized():
    """Returns a fallback message for unknown actions."""
    mongo_tool = load_mongo_tool()

    result = mongo_tool._build_context("unknown_action", {}, db={})

    assert result == "Action not recognized."
