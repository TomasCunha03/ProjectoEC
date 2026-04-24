from __future__ import annotations

import json
import os
import re

import ollama

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

_INT_FIELDS = frozenset(
    {"global_start_year", "global_end_year", "chronic_start_year", "chronic_end_year"}
)
_STR_FIELDS = frozenset(
    {
        "global_country",
        "global_disease_name",
        "global_disease_category",
        "chronic_location",
        "chronic_topic",
    }
)
_ALLOWED_FIELDS = _INT_FIELDS | _STR_FIELDS

FIXED_RESPONSE = "Dashboard updated as requested! Feel free to ask if you want any other changes."

_EXTRACTION_PROMPT = """\
You are a dashboard filter extractor for a medical data dashboard.

The dashboard has two sections with separate filters:

GLOBAL HEALTH section filters:
- global_country (string): country name, e.g. "Portugal", "Brazil", "United States"
- global_start_year (integer): start year, e.g. 2015
- global_end_year (integer): end year, e.g. 2020
- global_disease_name (string): disease or medical condition, e.g. "diabetes", "cancer"
- global_disease_category (string): category, e.g. "Infectious", "Chronic"

CHRONIC DISEASE section filters (US data):
- chronic_location (string): US state or location, e.g. "California", "Texas", "New York"
- chronic_start_year (integer): start year for chronic data
- chronic_end_year (integer): end year for chronic data
- chronic_topic (string): chronic disease topic, e.g. "Diabetes", "Cancer", "Cardiovascular"

Rules:
- Extract ONLY filters explicitly mentioned in the request.
- Country names go to global_country. US states go to chronic_location.
- Disease/condition names go to global_disease_name.
- If the user says "reset" or "clear", return empty: {}
- IMPORTANT: Output ONLY raw JSON. No markdown, no explanation.

Examples:
- "show me data for Portugal on the dashboard" → {"global_country": "Portugal"}
- "filter dashboard to Brazil" → {"global_country": "Brazil"}
- "show United States data" → {"global_country": "United States"}
- "filter to 2015-2020" → {"global_start_year": 2015, "global_end_year": 2020}
- "show data from 2010 to 2018" → {"global_start_year": 2010, "global_end_year": 2018}
- "show me diabetes data on the dashboard" → {"global_disease_name": "diabetes"}
- "change dashboard to show cancer" → {"global_disease_name": "cancer"}
- "show anxiety data" → {"global_disease_name": "anxiety"}
- "show depression data on the dashboard" → {"global_disease_name": "depression"}
- "filter chronic diseases to California" → {"chronic_location": "California"}
- "show chronic data for Texas" → {"chronic_location": "Texas"}
- "show diabetes topic in chronic section" → {"chronic_topic": "Diabetes"}
- "Portugal data from 2015 to 2020"
  → {"global_country": "Portugal", "global_start_year": 2015, "global_end_year": 2020}
- "reset the dashboard" → {}
- "clear all filters" → {}

User request: {user_message}
"""

# Regex fallbacks — used when the LLM returns nothing useful
_RESET_RE = re.compile(r"\b(reset|clear)\b", re.IGNORECASE)
_YEAR_RANGE_RE = re.compile(r"\b(\d{4})\s*(?:[-–]|to)\s*(\d{4})\b")
_SINGLE_YEAR_RE = re.compile(r"\b(from|since|after|year)\s+(\d{4})\b", re.IGNORECASE)

# "show me X data" / "show X on the dashboard" / "change to show X"
_DISEASE_FALLBACK_RE = re.compile(
    r"(?:show(?:\s+me)?|display|view|change\s+to\s+show)\s+(\w[\w\s]*?)"
    r"(?:\s+data|\s+on\s+the\s+dashboard|$)",
    re.IGNORECASE,
)
# "data for Portugal" / "filter to Brazil" / "filter dashboard to X"
_COUNTRY_FALLBACK_RE = re.compile(
    r"(?:for|to|in|filter\s+to|filter\s+dashboard\s+to)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)"
    r"(?:\s+(?:data|on|in|the)|$)",
    re.IGNORECASE,
)
# "for the state of Florida" / "state of New York"
_STATE_OF_RE = re.compile(
    r"\bstate\s+of\s+([A-Za-z][a-zA-Z\s]+?)(?:\s+(?:data|from|in|on|the)|[,.]|$)",
    re.IGNORECASE,
)
# US states for chronic section
_US_STATES = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
}


def dashboard_tool(user_message: str) -> tuple[str, dict]:
    """
    Extract dashboard filter values from a natural-language request.

    Returns:
        (response_text, filters_dict) where filters_dict contains only the
        fields the user explicitly mentioned.
    """
    prompt = _EXTRACTION_PROMPT.replace("{user_message}", user_message)

    client = ollama.Client(host=OLLAMA_HOST)
    raw_response = client.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.0},
    )
    raw = raw_response["message"]["content"].strip()

    # Strip markdown fences if the model wraps output in them
    raw = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

    filters: dict = {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            filters = parsed
    except Exception:
        # Try to find a JSON object anywhere in the response
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    filters = parsed
            except Exception:
                pass
        logger.warning("Dashboard tool: failed to parse LLM response: %s", raw[:200])

    # Validate and coerce types; drop unknown/invalid fields
    clean_filters: dict = {}
    for key, value in filters.items():
        if key not in _ALLOWED_FIELDS:
            continue
        if key in _INT_FIELDS:
            try:
                clean_filters[key] = int(value)
            except (ValueError, TypeError):
                logger.warning("Dashboard tool: invalid int for %s: %r", key, value)
        elif value:
            clean_filters[key] = str(value)

    # Regex fallback: if LLM returned nothing useful, try to extract from the message directly
    if not clean_filters:
        clean_filters = _regex_fallback(user_message)
        if clean_filters:
            logger.info("Dashboard filters from regex fallback: %s", clean_filters)

    logger.info("Dashboard filters extracted: %s", clean_filters)
    return FIXED_RESPONSE, clean_filters


def _regex_fallback(message: str) -> dict:
    """Best-effort filter extraction without LLM, for when the model returns nothing."""
    _STOP_WORDS = {
        "me",
        "the",
        "some",
        "all",
        "any",
        "more",
        "this",
        "that",
        "data",
        "dashboard",
        "filters",
        "filter",
        "chronic",  # "show chronic data for X" — "chronic" is not a disease name
        "global",
        "state",
    }

    # Reset request → empty dict (clears all filters)
    if _RESET_RE.search(message):
        return {}

    result: dict = {}

    # Year range: "2015-2020", "2010 to 2022"
    year_match = _YEAR_RANGE_RE.search(message)
    if year_match:
        result["global_start_year"] = int(year_match.group(1))
        result["global_end_year"] = int(year_match.group(2))
    else:
        # Single year: "from 2015", "since 2010"
        single_match = _SINGLE_YEAR_RE.search(message)
        if single_match:
            result["global_start_year"] = int(single_match.group(2))

    # "state of Florida" / "for the state of New York" — check before disease/country
    state_of_match = _STATE_OF_RE.search(message)
    if state_of_match:
        candidate = state_of_match.group(1).strip().lower()
        if candidate in _US_STATES:
            result["chronic_location"] = candidate.title()

    # Disease name: "show me anxiety data", "show anxiety on the dashboard"
    if "chronic_location" not in result:
        disease_match = _DISEASE_FALLBACK_RE.search(message)
        if disease_match:
            candidate = disease_match.group(1).strip().lower()
            if candidate and candidate not in _STOP_WORDS:
                # Check if it's a US state → goes to chronic_location instead
                if candidate in _US_STATES:
                    result["chronic_location"] = candidate.title()
                else:
                    result["global_disease_name"] = candidate

    # Country / location: "for Portugal", "filter to California"
    if "global_disease_name" not in result and "chronic_location" not in result:
        country_match = _COUNTRY_FALLBACK_RE.search(message)
        if country_match:
            candidate = country_match.group(1).strip()
            if candidate.lower() not in _STOP_WORDS:
                if candidate.lower() in _US_STATES:
                    result["chronic_location"] = candidate.title()
                else:
                    result["global_country"] = candidate

    return result
