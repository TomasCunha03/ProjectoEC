"""Deterministic heuristic routing to avoid LLM for simple patterns."""
import re
from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)


def route_question(query: str) -> dict:
    """Route based on keywords. Returns {"tools": [...]} or empty if LLM fallback needed."""
    
    q = query.lower().strip()
    
    # Greetings
    if re.match(r"^(hi|hello|hey|thanks|thank you|bye|goodbye)\b", q):
        logger.info("Heuristic: greeting detected")
        return {"tools": []}
    
    # "What is X?" → MONGO (disease definition)
    if re.search(r"\b(what\s+is|tell\s+me\s+about|describe|definition\s+of)\b", q):
        logger.info("Heuristic: disease definition pattern detected")
        return {"tools": ["mongo_query"]}
    
    # "How does X work?" or "Explain X" → RAG (mechanisms)
    if re.search(r"\b(how\s+does|how\s+can|explain|mechanism|work|process)\b", q):
        logger.info("Heuristic: mechanism/how pattern detected")
        return {"tools": ["rag_answer"]}
    
    # Numbers/stats: "how many", "prevalence", "percentage", "rate", etc. → SQL
    if re.search(r"\b(how\s+many|prevalence|percentage|rate|statistics|cases|incidence|mortality)\b", q):
        logger.info("Heuristic: statistics pattern detected")
        return {"tools": ["sql_query"]}
    
    # Drug side effects, dosage, etc. → SQL
    if re.search(r"\b(side\s+effects?|adverse|dosage|dose|interaction|drug|medication)\b", q):
        logger.info("Heuristic: drug/medication pattern detected")
        return {"tools": ["sql_query"]}
    
    # Symptoms → could be SQL or RAG depending on context
    if re.search(r"\b(symptoms?|signs?|caused\s+by)\b", q):
        if re.search(r"\b(symptom.*prevalence|how.*common|rate|percentage)\b", q):
            logger.info("Heuristic: symptoms with stats pattern detected")
            return {"tools": ["sql_query"]}
        logger.info("Heuristic: symptom definition pattern detected")
        return {"tools": ["rag_answer"]}
    
    # No heuristic match - let LLM decide
    logger.info("Heuristic: no pattern matched, using LLM for tool selection")
    return None
