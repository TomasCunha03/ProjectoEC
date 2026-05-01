from __future__ import annotations

import json
import os
import re

import ollama

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "mistral:7b-instruct-q4_K_M")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

_INT_FIELDS = frozenset(
    {
        "global_start_year",
        "global_end_year",
        "immunization_start_year",
        "immunization_end_year",
        "top_n",
        "chronic_start_year",
        "chronic_end_year",
    }
)
_STR_FIELDS = frozenset(
    {
        "global_country",
        "global_disease_name",
        "global_disease_category",
        "vaccine_code",
        "chronic_location",
        "chronic_topic",
    }
)
_ALLOWED_FIELDS = _INT_FIELDS | _STR_FIELDS

_FIELD_ALIASES = {
    "bcg_start_year": "immunization_start_year",
    "bcg_end_year": "immunization_end_year",
}

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

IMMUNIZATION/Display controls:
- vaccine_code (string): vaccine code, e.g. "BCG", "DTP3", "MCV1"
- immunization_start_year (integer): start year for immunization charts window, e.g. 2010
- immunization_end_year (integer): end year for immunization charts window, e.g. 2020
- top_n (integer): number of items for top charts, e.g. 10, 20

Rules:
- Extract ONLY filters explicitly mentioned in the request.
- Country names go to global_country. US states go to chronic_location.
- Disease/condition names go to global_disease_name.
- If a specific vaccine is mentioned, set vaccine_code in uppercase.
- If user asks for all vaccines or says not to focus only on BCG, set vaccine_code to null.
- Immunization year windows go to immunization_start_year and immunization_end_year.
- Requests like "top 20" should set top_n to 20.
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
- "set BCG window to 2010-2020" → {"vaccine_code": "BCG", "immunization_start_year": 2010, \
    "immunization_end_year": 2020}
- "show top 20 conditions" → {"top_n": 20}
- "BCG 2012 to 2021, top 20" → {"vaccine_code": "BCG", "immunization_start_year": 2012, \
    "immunization_end_year": 2021, "top_n": 20}
- "show immunization trend for DTP3" → {"vaccine_code": "DTP3"}
- "show all vaccines" → {"vaccine_code": null}
- "do not focus only on BCG" → {"vaccine_code": null}
- "Portugal data from 2015 to 2020"
  → {"global_country": "Portugal", "global_start_year": 2015, "global_end_year": 2020}
- "reset the dashboard" → {}
- "clear all filters" → {}

User request: {user_message}
"""

# Regex fallbacks — used when the LLM returns nothing useful
_RESET_RE = re.compile(r"\b(reset|clear)\b", re.IGNORECASE)
_YEAR_RANGE_RE = re.compile(r"\b(\d{4})\s*(?:[-–]|to|a)\s*(\d{4})\b", re.IGNORECASE)
_SINGLE_YEAR_RE = re.compile(r"\b(from|since|after|year|de|desde|ano)\s+(\d{4})\b", re.IGNORECASE)
_TOP_N_RE = re.compile(r"\btop\s+(\d{1,3})\b", re.IGNORECASE)
_IMMUNIZATION_RE = re.compile(
    r"\b(bcg|vaccine|vaccination|immunization|vacina|imuniza)\b", re.IGNORECASE
)
_VACCINE_CODE_INLINE_RE = re.compile(
    r"\b(BCG|DTP1|DTP3|MCV1|MCV2|POL3|HEPB3|HIB3|PCV3|ROTAC|RCV1|YFV)\b",
    re.IGNORECASE,
)
_VACCINE_AFTER_KEYWORD_RE = re.compile(
    r"\b(?:vaccine|vaccination|immunization|vacina|imunizacao|imunização)\s+([a-z0-9]{2,8})\b",
    re.IGNORECASE,
)
_ALL_VACCINES_INTENT_RE = re.compile(
    r"(all\s+vaccines|todas\s+as\s+vacinas|outras\s+vacinas|"
    r"not\s+(?:only|just)\s+bcg|nao\s+.*apenas\s+.*bcg|não\s+.*apenas\s+.*bcg|"
    r"alem\s+da\s+bcg|além\s+da\s+bcg)",
    re.IGNORECASE,
)

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

_VACCINE_CAPTURE_STOP_WORDS = {
    "coverage",
    "trend",
    "chart",
    "data",
    "window",
    "top",
    "all",
    "global",
}


def _extract_vaccine_code(message: str) -> str | None:
    inline_match = _VACCINE_CODE_INLINE_RE.search(message)
    if inline_match:
        return inline_match.group(1).upper()

    keyword_match = _VACCINE_AFTER_KEYWORD_RE.search(message)
    if not keyword_match:
        return None

    candidate = keyword_match.group(1).strip().upper()
    if not candidate or candidate.lower() in _VACCINE_CAPTURE_STOP_WORDS:
        return None
    return candidate


def _wants_all_vaccines(message: str) -> bool:
    return bool(_ALL_VACCINES_INTENT_RE.search(message))


def dashboard_tool(user_message: str) -> tuple[str, dict]:
    """
    Extract dashboard filter values from a natural-language request.

    Returns:
        (response_text, filters_dict) where filters_dict contains only the
        fields the user explicitly mentioned.
    """
    if _RESET_RE.search(user_message):
        logger.info("Dashboard reset detected; clearing all dashboard filters")
        return FIXED_RESPONSE, {}

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
    for raw_key, value in filters.items():
        key = _FIELD_ALIASES.get(raw_key, raw_key)
        if key not in _ALLOWED_FIELDS:
            continue
        if key in _INT_FIELDS:
            try:
                parsed_int = int(value)
                if key == "top_n":
                    parsed_int = max(1, min(parsed_int, 100))
                clean_filters[key] = parsed_int
            except (ValueError, TypeError):
                logger.warning("Dashboard tool: invalid int for %s: %r", key, value)
        elif value:
            parsed_text = str(value).strip()
            if not parsed_text:
                continue
            if key == "vaccine_code":
                clean_filters[key] = parsed_text.upper()
            else:
                clean_filters[key] = parsed_text

    # Support intent like "not only BCG" by explicitly clearing vaccine scope.
    if _wants_all_vaccines(user_message):
        clean_filters["vaccine_code"] = None

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
    wants_all_vaccines = _wants_all_vaccines(message)
    vaccine_code: str | None = None
    if wants_all_vaccines:
        result["vaccine_code"] = None
    else:
        vaccine_code = _extract_vaccine_code(message)
        if vaccine_code:
            result["vaccine_code"] = vaccine_code

    is_immunization_request = bool(
        _IMMUNIZATION_RE.search(message) or vaccine_code or wants_all_vaccines
    )

    # Year range: "2015-2020", "2010 to 2022"
    year_match = _YEAR_RANGE_RE.search(message)
    if year_match:
        year_start = int(year_match.group(1))
        year_end = int(year_match.group(2))
        if is_immunization_request:
            result["immunization_start_year"] = year_start
            result["immunization_end_year"] = year_end
        else:
            result["global_start_year"] = year_start
            result["global_end_year"] = year_end
    else:
        # Single year: "from 2015", "since 2010"
        single_match = _SINGLE_YEAR_RE.search(message)
        if single_match:
            single_year = int(single_match.group(2))
            if is_immunization_request:
                result["immunization_start_year"] = single_year
                result["immunization_end_year"] = single_year
            else:
                result["global_start_year"] = single_year

    top_n_match = _TOP_N_RE.search(message)
    if top_n_match:
        result["top_n"] = max(1, min(int(top_n_match.group(1)), 100))

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
