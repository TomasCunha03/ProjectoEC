import os
import re

import ollama
import yaml
from pymongo import MongoClient

from chat_saude.observability.langfuse_client import end_span, start_span
from chat_saude.observability.logger import get_logger

LLM_MODEL = "gemma3:4b"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
logger = get_logger(__name__)
AGENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents"))
MONGO_CATALOG_PATH = os.path.join(AGENTS_DIR, "mongo_catalog.yaml")


def _get_mongo_db():
    client = MongoClient(
        host=os.getenv("MONGO_HOST", "localhost"),
        port=int(os.getenv("MONGO_PORT", "27017")),
        username=os.getenv("MONGO_USER"),
        password=os.getenv("MONGO_PASSWORD"),
        serverSelectionTimeoutMS=5000,
    )
    return client[os.getenv("MONGO_DB", "db_saude_nosql")]


def _load_catalog_text() -> str:
    try:
        with open(MONGO_CATALOG_PATH, encoding="utf-8") as file:
            catalog = yaml.safe_load(file) or {}
    except FileNotFoundError:
        logger.warning("Mongo catalog not found: %s", MONGO_CATALOG_PATH)
        return ""
    except Exception as exc:
        logger.warning("Failed to read Mongo catalog %s: %s", MONGO_CATALOG_PATH, exc)
        return ""

    lines = []
    summary = catalog.get("summary")
    if summary:
        lines.append(f"Mongo catalog summary: {summary}")

    collections = catalog.get("collections", [])
    if collections:
        lines.append("Mongo catalog collections:")
        for collection in collections:
            name = collection.get("name", "unknown")
            purpose = collection.get("purpose", "")
            grain = collection.get("grain", "")
            searchable_fields = collection.get("searchable_fields", [])
            lines.append(f"  - {name}: {purpose} Grain: {grain}.")
            if searchable_fields:
                lines.append(f"    Searchable fields: {', '.join(searchable_fields)}.")

    return "\n".join(lines)


def _search_indicators(db, keyword: str, limit: int = 10) -> list[dict]:
    collection = db["gho_indicators"]
    return list(
        collection.find(
            {
                "$or": [
                    {"IndicatorName": {"$regex": keyword, "$options": "i"}},
                    {"IndicatorCode": {"$regex": keyword, "$options": "i"}},
                ]
            },
            {"_id": 0, "IndicatorCode": 1, "IndicatorName": 1},
        ).limit(limit)
    )


def _get_dimension_values(db, dimension_code: str, limit: int = 30) -> list[dict]:
    safe_code = dimension_code.strip().lower().replace(" ", "_")
    collection_name = f"gho_{safe_code}_dimension_values"
    return list(db[collection_name].find({}, {"_id": 0, "Code": 1, "Title": 1}).limit(limit))


def _list_collections(db) -> list[str]:
    return sorted(db.list_collection_names())


def _search_disease_info(db, keyword: str) -> dict | None:
    collection = db["medlineplus_health_topics"]
    return collection.find_one(
        {"disease_name": {"$regex": keyword, "$options": "i"}},
        {"_id": 0, "disease_name": 1, "title": 1, "full_summary": 1, "url": 1},
    )


def _build_context(action: str, plan: dict, db) -> str:
    if action == "search_indicators":
        keyword = plan.get("keyword", "")
        results = _search_indicators(db, keyword)
        if not results:
            return f"No WHO indicators found for '{keyword}'."
        lines = [f"WHO indicators related to '{keyword}' ({len(results)} found):"]
        for r in results:
            lines.append(f"  - [{r.get('IndicatorCode', 'N/A')}] {r.get('IndicatorName', 'N/A')}")
        return "\n".join(lines)

    elif action == "get_dimension_values":
        dim_code = plan.get("dimension_code", "").upper()
        results = _get_dimension_values(db, dim_code)
        if not results:
            return f"No values found for dimension '{dim_code}'."
        lines = [f"Available values for dimension '{dim_code}' ({len(results)} shown):"]
        for r in results:
            lines.append(f"  - [{r.get('Code', 'N/A')}] {r.get('Title', 'N/A')}")
        return "\n".join(lines)

    elif action == "list_collections":
        collections = _list_collections(db)
        lines = [f"Available MongoDB collections ({len(collections)} total):"]
        for c in collections:
            lines.append(f"  - {c}")
        return "\n".join(lines)

    elif action == "search_disease_info":
        keyword = plan.get("keyword", "")
        result = _search_disease_info(db, keyword)
        if not result:
            return f"No MedlinePlus information found for '{keyword}'."
        # Remove HTML tags from the summary
        summary = re.sub(r"<[^>]+>", " ", result.get("full_summary", ""))
        summary = re.sub(r"\s+", " ", summary).strip()
        lines = [
            f"**{result.get('title', result.get('disease_name', keyword))}**"
            " (Source: MedlinePlus/NIH)",
            "",
            summary,
        ]
        if result.get("url"):
            lines.append(f"\nMore information: {result['url']}")
        return "\n".join(lines)

    return "Action not recognized."


# Patterns to detect questions about dimensions (countries, age groups, etc.)
_DIMENSION_PATTERNS = {
    "COUNTRY": re.compile(r"\b(countr|nation|where|location)\w*\b", re.I),
    "AGEGROUP": re.compile(r"\b(age\s*group|age\s*range|ages?)\b", re.I),
    "SEX": re.compile(r"\b(sex|gender)\b", re.I),
    "YEAR": re.compile(r"\b(year|period|time)\b", re.I),
    "REGION": re.compile(r"\b(region|continent|area)\b", re.I),
}

_SKIP_WORDS = {
    "what",
    "which",
    "where",
    "does",
    "exist",
    "about",
    "available",
    "indicators",
    "indicator",
    "list",
    "show",
    "give",
    "find",
    "related",
    "mental",
    "health",
    "who",
    "data",
    "collect",
    "collected",
    "there",
    "topic",
    "topics",
    "disease",
    "diseases",
    "tell",
    "more",
    "information",
    "details",
    "describe",
    "explain",
    "summary",
    "info",
}

_DISEASE_INFO_PATTERN = re.compile(
    r"\b(details?|summary|info|information|describe|explain|tell\s+me\s+about|what\s+is|overview)\b",
    re.I,
)

_KNOWN_DISEASES = [
    "acne",
    "adhd",
    "aids",
    "hiv",
    "allergies",
    "alzheimer",
    "angina",
    "anxiety",
    "asthma",
    "bipolar",
    "bronchitis",
    "cancer",
    "cholesterol",
    "cold",
    "flu",
    "constipation",
    "copd",
    "covid",
    "depression",
    "diabetes",
    "diarrhea",
    "eczema",
    "erectile dysfunction",
    "gastrointestinal",
    "gerd",
    "heartburn",
    "gout",
    "hair loss",
    "hayfever",
    "herpes",
    "hypertension",
    "hypothyroidism",
    "ibd",
    "incontinence",
    "insomnia",
    "menopause",
    "migraine",
    "osteoarthritis",
    "osteoporosis",
    "pain",
    "pneumonia",
    "psoriasis",
    "rheumatoid arthritis",
    "schizophrenia",
    "seizures",
    "stroke",
    "swine flu",
    "uti",
    "weight loss",
]


def _plan_query(user_question: str) -> tuple[str, dict]:
    """Determine the MongoDB action and parameters from the question (no LLM used)."""
    q = user_question.lower()

    if re.search(r"\b(collections?|what data|what is available|available data)\b", q):
        return "list_collections", {}

    if _DISEASE_INFO_PATTERN.search(q):
        for disease in _KNOWN_DISEASES:
            if disease in q:
                return "search_disease_info", {"keyword": disease}

    for dim_code, pattern in _DIMENSION_PATTERNS.items():
        if pattern.search(q):
            return "get_dimension_values", {"dimension_code": dim_code}

    for disease in _KNOWN_DISEASES:
        if re.search(rf"\b{re.escape(disease)}\b", q):
            if re.search(r"\b(indicators?|who\s+indicators?|gho)\b", q):
                return "search_indicators", {"keyword": disease}
            return "search_disease_info", {"keyword": disease}

    words = [w for w in re.findall(r"[a-z]+", q) if len(w) > 3 and w not in _SKIP_WORDS]
    keyword = " ".join(words[:2]) if words else user_question[:30]
    return "search_indicators", {"keyword": keyword}


def mongo_query(user_question: str) -> str:
    """
    Query MongoDB based on the user's question.
    Uses regex/heuristics to determine the action, then uses the LLM to generate the final response.
    """
    logger.info("Mongo tool input: %s", user_question)
    span = start_span(name="mongo_tool", input_payload={"question": user_question})

    try:
        db = _get_mongo_db()
        catalog_context = _load_catalog_text()
        action, plan = _plan_query(user_question)
        logger.info("Mongo tool plan: action=%s plan=%s", action, plan)
        data_context = _build_context(action, plan, db)

        context_parts = []
        if catalog_context:
            context_parts.append(catalog_context)
        context_parts.append(data_context)
        context = "\n\n".join(context_parts)

        client = ollama.Client(host=OLLAMA_HOST)
        prompt = (
            "Based on the data below from the health MongoDB database, answer "
            "in English clearly and helpfully.\n\n"
            f"Data:\n{context}\n\n"
            f"Question: {user_question}\n\n"
            "Respond concisely and informatively, presenting "
            "the retrieved data in an organized way."
        )

        response = client.generate(model=LLM_MODEL, prompt=prompt)
        final_response = response["response"]
        end_span(
            span,
            output_payload={
                "action": action,
                "plan": plan,
                "context_preview": context[:1000],
                "response": final_response,
            },
        )
        return final_response
    except Exception as exc:
        logger.exception("Mongo tool failed")
        end_span(
            span,
            output_payload={"error": str(exc)},
            level="ERROR",
            status_message="mongo_tool_error",
        )
        raise
