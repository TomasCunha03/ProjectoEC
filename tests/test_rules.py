"""Unit tests for the rule engine checks with stubbed embeddings."""

import importlib
import importlib.util
import os
import sys
import types


def load_rules():
    st_mod = types.ModuleType("sentence_transformers")

    class DummySentenceTransformer:
        def __init__(self, *args, **kwargs):
            return None

        def encode(self, inputs):
            if isinstance(inputs, list):
                return [0.0 for _ in inputs]
            return [0.0]

    st_mod.SentenceTransformer = DummySentenceTransformer
    sys.modules["sentence_transformers"] = st_mod

    np_mod = types.ModuleType("numpy")

    def np_max(values):
        if isinstance(values, list) and values and isinstance(values[0], list):
            return max(values[0])
        return max(values)

    def np_argmax(values):
        return values.index(max(values))

    np_mod.max = np_max
    np_mod.argmax = np_argmax
    sys.modules["numpy"] = np_mod

    pairwise_mod = types.ModuleType("sklearn.metrics.pairwise")
    pairwise_mod.cosine_similarity = lambda a, b: [[0.0]]
    metrics_mod = types.ModuleType("sklearn.metrics")
    metrics_mod.pairwise = pairwise_mod
    sklearn_mod = types.ModuleType("sklearn")

    sys.modules["sklearn"] = sklearn_mod
    sys.modules["sklearn.metrics"] = metrics_mod
    sys.modules["sklearn.metrics.pairwise"] = pairwise_mod

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    rules_path = os.path.join(project_root, "apps", "api", "rules.py")
    module_name = "rules_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, rules_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_check_emergency_triggers_message():
    """Returns emergency message when similarity is above threshold."""
    rules = load_rules()
    rules.cosine_similarity = lambda a, b: [[0.7]]

    result = rules.check_emergency("help")

    assert "medical emergency" in result


def test_check_emergency_below_threshold_returns_none():
    """Returns None when similarity is below threshold."""
    rules = load_rules()
    rules.cosine_similarity = lambda a, b: [[0.1]]

    assert rules.check_emergency("hello") is None


def test_check_faq_returns_best_match():
    """Selects the closest FAQ answer by similarity."""
    rules = load_rules()
    rules.cosine_similarity = lambda a, b: [[0.1, 0.9, 0.2]]

    result = rules.check_faq("who are you")

    assert result == rules.faq_answers[1]


def test_check_domain_rejects_unrelated_query():
    """Rejects queries that are unrelated to medical or non-medical examples."""
    rules = load_rules()
    rules.medical_embeddings = "MED"
    rules.non_medical_embeddings = "NON"

    def cos(a, b):
        if b == "MED":
            return [[0.1]]
        if b == "NON":
            return [[0.1]]
        return [[0.0]]

    rules.cosine_similarity = cos

    result = rules.check_domain("blabla")

    assert "rephrase your question" in result


def test_check_domain_rejects_non_medical_query():
    """Rejects queries that are confidently non-medical."""
    rules = load_rules()
    rules.medical_embeddings = "MED"
    rules.non_medical_embeddings = "NON"

    def cos(a, b):
        if b == "MED":
            return [[0.2]]
        if b == "NON":
            return [[0.6]]
        return [[0.0]]

    rules.cosine_similarity = cos

    result = rules.check_domain("movie")

    assert "specialized medical assistant" in result


def test_apply_rules_returns_domain_message():
    """Returns the first applicable rule response."""
    rules = load_rules()
    rules.check_emergency = lambda query: None
    rules.check_faq = lambda query: None
    rules.check_domain = lambda query: "domain message"

    assert rules.apply_rules("hello") == "domain message"
