"""
Deterministic routing hints before the LLM router.

Keeps obvious medical questions off canned_key 'unclear' when small models misclassify.
See conversation_router.route_conversation for ordering with LLM + fallbacks.
"""

from __future__ import annotations

import re
def try_heuristic_route(user_message: str):
    """
    Return a RouteDecision when the message matches high-confidence patterns; else None.

    Order matters: more specific rules before broad ones (e.g. drugs before generic 'what is').
    """
    # Late import avoids circular import at module load
    from agents.conversation_router import RouteDecision

    q = user_message.strip()
    if len(q) < 2:
        return None

    ql = q.lower()

    # Meta / assistant identity (avoid stealing tool routes)
    if re.search(r"\b(who\s+are\s+you|what\s+are\s+you|introduce\s+yourself|your\s+name)\b", ql):
        return RouteDecision(mode="direct", canned_key="identity", tools=[])

    # Thanks / closure (short gratitude without a health question)
    if _is_mostly_thanks(ql):
        return RouteDecision(mode="direct", canned_key="thanks", tools=[])

    # Emergency phrasing
    if re.search(
        r"\b(suicide|kill\s+myself|heart\s+attack|can'?t\s+breathe|can't\s+breathe|overdose|"
        r"unconscious|severe\s+bleeding|stroke\s+right\s+now)\b",
        ql,
    ):
        return RouteDecision(mode="direct", canned_key="emergency", tools=[])

    # WHO / statistics / numeric epidemiology → SQL
    if re.search(
        r"\b(prevalence|incidence|mortality|how\s+many\s+people|percentage\s+of|rate\s+in|"
        r"per\s+100|statistics|compared\s+to|by\s+country|by\s+year|brfss|who\s+indicator)\b",
        ql,
    ):
        return RouteDecision(mode="tools", canned_key=None, tools=["sql_query"])

    # Medications: side effects, dosing, named common drugs, "taking X" + what/why/help
    if _matches_drug_or_medication_route(ql):
        tools = ["sql_query"]
        if re.search(r"\b(understand|explain|help\s+me|tell\s+me\s+more|why\s+(would|does|do))\b", ql):
            tools = ["rag_answer", "sql_query"]
        return RouteDecision(mode="tools", canned_key=None, tools=tools)

    # Self-care / what to do (symptom relief), not definitional "what is X disease"
    if re.search(
        r"\b(what\s+can\s+i\s+do|what\s+should\s+i\s+do|how\s+can\s+i\s+(ease|relieve|stop|reduce)|"
        r"how\s+do\s+i\s+(ease|relieve))\b",
        ql,
    ):
        return RouteDecision(mode="tools", canned_key=None, tools=["rag_answer"])

    # Disease / condition education: "tell me about", "what is …", etc. (excluding stats-only)
    if _matches_disease_overview(ql):
        return RouteDecision(mode="tools", canned_key=None, tools=["rag_answer", "mongo_query"])

    return None


def _is_mostly_thanks(ql: str) -> bool:
    if len(ql) > 220:
        return False
    return bool(
        re.search(r"\b(thanks?|thank\s+you|appreciate\s+it)\b", ql)
        and not re.search(r"\b(what|how|why|tell\s+me|explain|symptom|cancer|drug|disease)\b", ql)
    )


def _matches_drug_or_medication_route(ql: str) -> bool:
    if re.search(
        r"\b(side\s+effects?|adverse\s+effects?|drug\s+interaction|dosage|doses?|milligrams?)\b",
        ql,
    ):
        return True

    # Common medications (extend as needed)
    if re.search(
        r"\b(loratadine|cetirizine|fexofenadine|diphenhydramine|ibuprofen|acetaminophen|paracetamol|aspirin|"
        r"metformin|omeprazole|lisinopril|atorvastatin|amlodipine|prednisone|azithromycin|amoxicillin|"
        r"warfarin|levothyroxine|sertraline|fluoxetine)\b",
        ql,
    ):
        return True

    if re.search(r"\b(i\s*'?m\s+taking|i\s+am\s+taking|taking\s+\w+)\b", ql) and re.search(
        r"\b(what\s+for|what\s+is\s+it\s+used|used\s+for|why\s+am\s+i|help\s+me\s+understand)\b",
        ql,
    ):
        return True

    if re.search(r"\b(medication|prescription|over\s*[- ]the\s*[- ]counter|otc\s+drug)\b", ql) and re.search(
        r"\b(what\s+is|used\s+for|side\s+effects?|dosage)\b",
        ql,
    ):
        return True

    return False


def _matches_disease_overview(ql: str) -> bool:
    if not re.search(
        r"\b(tell\s+me\s+about|what\s+(is|are)|could\s+you\s+(explain|tell|help)|"
        r"i\s+want\s+to\s+know\s+(about|more)|explain\s+|overview\s+of|describe)\b",
        ql,
    ):
        return False
    # Exclude patterns already handled elsewhere
    if _matches_drug_or_medication_route(ql):
        return False
    if re.search(
        r"\b(prevalence|incidence|rate\s+in|how\s+many|percentage|statistics)\b",
        ql,
    ):
        return False
    if re.search(r"\bwhat\s+is\s+your\b", ql):
        return False
    if re.search(
        r"\b(homework|weather|recipe|football|basketball|stock\s+market|python|javascript|"
        r"video\s+game|movie)\b",
        ql,
    ):
        return False
    return True


def looks_like_health_question_for_fallback(user_message: str) -> bool:
    """
    When the LLM yields 'unclear' or bad JSON, route to tools instead if this returns True.

    Conservative: enough signal that the user is asking health/medicine something substantive.
    """
    ql = user_message.strip().lower()
    if len(ql) < 8:
        return False

    if len(ql) > 600:
        return True

    return bool(
        re.search(
            r"\b(cancer|tumor|diabetes|hypertension|asthma|covid|flu|stroke|symptom|pain|fever|nausea|"
            r"vaccine|heart|lung|kidney|liver|drug|medication|pill|tablet|prescription|side\s+effects?|"
            r"disease|syndrome|disorder|treatment|diagnosis|rash|allergy|loratadine|ibuprofen|health|"
            r"doctor|clinic|patient|who|cdc)\b",
            ql,
        )
    )
