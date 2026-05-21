"""
Semantic rule engine for the DrHouseGPT medical assistant.

All user messages pass through this module before reaching the LLM pipeline.
The engine uses a lightweight sentence-transformer model to compare incoming
queries against labelled example sets via cosine similarity, enforcing three
layers of safety/quality control in order:

  1. Emergency detection  — immediately redirects life-threatening queries to
                            emergency services without ever calling the LLM.
  2. FAQ matching         — short-circuits common identity/capability questions
                            with pre-written answers.
  3. Domain restriction   — rejects clearly off-topic (non-medical) queries so
                            the LLM is never used as a general-purpose assistant.
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

# all-MiniLM-L6-v2 is chosen for its good balance of speed and semantic quality;
# it runs comfortably on CPU, which keeps the API start-up time acceptable.
model = SentenceTransformer("all-MiniLM-L6-v2")

# --- 1. KNOWLEDGE BASE EXTENSION ---

# FAQ maps a tuple of representative phrasings to a canned answer.
# Using tuples as keys lets multiple semantically similar phrasings share one
# answer; the pre-processing loop below flattens this into parallel lists so
# each phrasing gets its own embedding.
FAQ = {
    # Identity & Greetings
    (
        "who are you",
        "what are you",
        "hello",
        "hi there",
        "tell me about yourself",
        "get to know you",
    ): (
        "I am DrHouseGPT, an AI-based medical assistant. "
        "I can help you clarify health questions and preventive medicine topics. "
        "⚠️ This information is educational and does not replace consultation with a doctor."
    ),
    # Capabilities & Limits
    (
        "what do you do",
        "what is your function",
        "what are your capabilities",
        "what can you do",
        "find out your capabilities",
    ): (
        "I answer medical questions based on scientific literature, but I CANNOT "
        "provide official diagnoses, analyze your specific exams, or prescribe medication. "
        "Always consult a real doctor for personal health issues."
    ),
    # Architecture
    ("how do you work", "how does it work", "are you an ai", "what model are you"): (
        "I use a specialized AI system that searches reliable medical documents before generating responses, ensuring my answers are grounded in scientific evidence."
    ),
}

# Representative phrases for life-threatening situations.
# The emergency check compares any incoming query against these embeddings
# before any other rule fires, ensuring no critical message ever reaches a
# slower code path.
EMERGENCY_EXAMPLES = [
    "I am having a heart attack",
    "I want to kill myself",
    "I can't breathe",
    "severe chest pain",
    "stroke symptoms right now",
    "bleeding heavily",
]

# Positive examples used to gauge medical relevance.
# A broad, diverse set is intentional: the max similarity over this entire list
# becomes a single "medical score" used in the domain classifier.
MEDICAL_EXAMPLES = [
    # General & Chronic Medicine
    "what is hypertension",
    "diabetes symptoms",
    "what causes chronic back pain",
    # Infectious Diseases
    "I have fever and cough",
    "how to prevent the flu",
    "symptoms of covid-19",
    # Prevention, Diet & Lifestyle
    "best diet for weight loss",
    "vitamin d benefits",
    "how to improve sleep quality",
    # Pharmacology
    "paracetamol side effects",
    "ibuprofen vs aspirin",
    "can I mix alcohol and antibiotics",
    # Dermatology & First Aid
    "how to treat a minor burn",
    "what does melanoma look like",
    "is this rash contagious",
    # Pediatrics & Reproductive Health
    "when should a baby start walking",
    "side effects of birth control pills",
    "pregnancy early signs",
    # Diagnostics & Anatomy
    "how to read blood test results",
    "where is the appendix located",
    "normal blood pressure range",
]

# Negative examples spanning a wide range of off-topic domains.
# Breadth here matters: covering sports, food, tech, finance, travel, etc.
# ensures the classifier recognises non-medical queries even when phrased
# in ways superficially similar to health topics (e.g. diet, exercise).
NON_MEDICAL_EXAMPLES = [
    # Sports & Entertainment
    "who won the game",
    "best movie of 2024",
    "football result",
    "concert tickets",
    "who won the champions league",
    "nba finals score",
    "recommend a tv series",
    "best netflix shows",
    "video game release date",
    "how to beat this level",
    "minecraft crafting recipe",
    "taylor swift new album",
    "grammy winners this year",
    "ticket prices for the concert",
    # Daily Life & Food
    "chocolate cake recipe",
    "restaurants in Lisbon",
    "how to tie a tie",
    "pasta recipe without eggs",
    "best pizza near me",
    "how to make coffee",
    "vegetarian dinner ideas",
    "meal prep for the week",
    "how long to boil eggs",
    "wine pairing for steak",
    # Tech & History
    "how to code in python",
    "who discovered america",
    "fix my computer screen",
    "install linux on my laptop",
    "javascript vs typescript",
    "best programming language to learn",
    "how does blockchain work",
    "reset my wifi router",
    "iphone vs android",
    "world war 2 timeline",
    "ancient egypt pyramids",
    "who was napoleon",
    # Finance & News
    "how to invest in stocks",
    "bitcoin price",
    "who is the president",
    "mortgage interest rates",
    "open a savings account",
    "credit card rewards",
    "tax deadline this year",
    "unemployment rate in portugal",
    "latest election results",
    "stock market news today",
    # Travel & Weather
    "what is the weather like tomorrow",
    "book a flight to London",
    "best hotels in Paris",
    "visa requirements for japan",
    "cheap flights to brazil",
    "things to do in rome",
    "public transport in berlin",
    "rent a car in spain",
    "beach vacation ideas",
    "snow forecast this weekend",
    # Home Repair & Shopping
    "how to fix a leaking pipe",
    "best places to buy cheap clothes",
    "car engine won't start",
    "paint a bedroom wall",
    "unclog the sink",
    "lawn mower won't start",
    "black friday deals",
    "amazon return policy",
    "best laptop under 1000 euros",
    "compare phone plans",
    # Work, school & career
    "write my resume",
    "job interview tips",
    "salary negotiation advice",
    "how to ask for a raise",
    "cover letter template",
    "solve this math equation",
    "homework help algebra",
    "chemistry lab report format",
    "study tips for exams",
    "university application deadline",
    # AI/Creative Requests (block general-purpose assistant use)
    "can you write a poem about stars",
    "translate this sentence to spanish",
    "write an email to my boss",
    "summarize this article",
    "proofread my essay",
    "generate a logo idea",
    "write python code for me",
    "brainstorm startup names",
    "create a marketing slogan",
    "roleplay as a pirate",
    # Lifestyle, hobbies & misc
    "best dog breeds for apartments",
    "how to train a puppy",
    "gardening tips for tomatoes",
    "yoga vs pilates for beginners",
    "learn guitar chords",
    "photography settings for sunset",
    "fashion trends this season",
    "horoscope for today",
    "tell me a joke",
    "riddle for kids",
    "lottery winning numbers",
    "dating app profile tips",
    "wedding planning checklist",
    "legal advice for tenants",
    "how to file taxes in portugal",
    "car insurance comparison",
    "learn french fast",
    "best books to read",
    "podcast recommendations",
    "social media marketing strategy",
]

# --- 2. PRE-COMPUTING EMBEDDINGS ---

# Flatten the FAQ dict so each phrasing maps to its answer at the same index.
# This lets us find the best answer with a single argmax after cosine similarity.
faq_questions = []
faq_answers = []
for keys, answer in FAQ.items():
    for key in keys:
        faq_questions.append(key)
        faq_answers.append(answer)

# Embeddings are computed once at import time so inference is only the cost of
# encoding the user query (not re-encoding the knowledge base on every request).
faq_embeddings = model.encode(faq_questions)
emergency_embeddings = model.encode(EMERGENCY_EXAMPLES)
medical_embeddings = model.encode(MEDICAL_EXAMPLES)
non_medical_embeddings = model.encode(NON_MEDICAL_EXAMPLES)

# --- 3. RULE ENGINE ---


def check_emergency(query: str, threshold: float = 0.60):
    """Return an emergency redirect message if the query resembles a life-threatening situation.

    The threshold is intentionally permissive (0.60) so borderline cases are
    still caught — a false positive here is far safer than a missed emergency.
    Returns ``None`` when no emergency is detected.
    """
    query_embedding = model.encode([query])
    similarities = cosine_similarity(query_embedding, emergency_embeddings)[0]

    if np.max(similarities) >= threshold:
        return (
            "It sounds like you might be experiencing a medical emergency. "
            "Please stop talking to this AI and immediately call your local emergency services "
            "(like 911 or 112) or go to the nearest hospital."
        )
    return None


def check_faq(query: str, threshold: float = 0.45):
    """Return the pre-written answer for identity/capability questions, or ``None``.

    A lower threshold than the emergency check (0.45) is acceptable here
    because the worst outcome of a false positive is just a slightly unexpected
    canned response, not a safety risk.
    """
    query_embedding = model.encode([query])
    similarities = cosine_similarity(query_embedding, faq_embeddings)[0]

    best_match_idx = np.argmax(similarities)
    if similarities[best_match_idx] >= threshold:
        logger.info("FAQ match found: %r", faq_answers[best_match_idx])
        return faq_answers[best_match_idx]

    return None


def check_domain(query: str):
    """Classify the query as medical, non-medical, or unintelligible, and reject if needed.

    Uses the maximum cosine similarity against the positive (medical) and
    negative (non-medical) example sets as competing confidence scores.

    Returns a rejection message string when the query should be blocked, or
    ``None`` when the query is medical and can proceed to the LLM pipeline.
    """
    query_embedding = model.encode([query])

    medical_score = np.max(cosine_similarity(query_embedding, medical_embeddings))
    non_medical_score = np.max(cosine_similarity(query_embedding, non_medical_embeddings))

    logger.info(f"[DEBUG] Medical Score: {medical_score:.2f} | Non-Medical Score: {non_medical_score:.2f}")

    # Case A: The query is completely unrelated to anything the model knows
    if medical_score < 0.15 and non_medical_score < 0.15:
        logger.warning("Query rejected (completely unrelated): %r", query)
        return "I'm not quite sure what you're asking. Could you rephrase your question?"

    # Case B: It's clearly non-medical (with a 0.05 safety margin).
    # The margin prevents ambiguous health-adjacent queries (e.g. "yoga vs pilates")
    # from being rejected just because they score slightly higher on non-medical examples.
    if non_medical_score > (medical_score + 0.05):
        logger.warning("Query rejected (clearly non-medical): %r", query)
        text_message = "I am a specialized medical assistant. I can only answer questions related to health, medicine and wellness."
        return text_message

    # Case C: It's a medical question (let it pass to the system)
    return None


def apply_rules(query: str):
    """Run the full rule pipeline against a user query and return an early response if needed.

    Checks are ordered by severity so that the most critical checks short-circuit
    first, avoiding unnecessary computation and preventing any chance of routing
    an emergency to the slower LLM path.

    Returns a string response to send directly to the user, or ``None`` if the
    query passed all checks and should be forwarded to the LLM pipeline.
    """
    # 1. EMERGENCY OVERRIDE
    result = check_emergency(query)
    if result:
        return result

    # 2. Identity and FAQ
    result = check_faq(query)
    if result:
        return result

    # 3. Domain Restriction
    result = check_domain(query)
    if result:
        return result

    # 4. Success! The query is valid, medical, and safe to process with LLM.
    return None
