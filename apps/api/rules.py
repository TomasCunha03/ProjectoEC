import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load the model
model = SentenceTransformer("all-MiniLM-L6-v2")

# --- 1. KNOWLEDGE BASE EXTENSION ---

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
        "I use a specialized AI system that searches reliable medical documents "
        "before generating responses, ensuring my answers are grounded in scientific evidence."
    ),
}

# Critical safety protocol
EMERGENCY_EXAMPLES = [
    "I am having a heart attack",
    "I want to kill myself",
    "I can't breathe",
    "severe chest pain",
    "stroke symptoms right now",
    "bleeding heavily",
]

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

NON_MEDICAL_EXAMPLES = [
    # Sports & Entertainment
    "who won the game",
    "best movie of 2024",
    "football result",
    "concert tickets",
    # Daily Life & Food
    "chocolate cake recipe",
    "restaurants in Lisbon",
    "how to tie a tie",
    # Tech & History
    "how to code in python",
    "who discovered america",
    "fix my computer screen",
    # Finance & News
    "how to invest in stocks",
    "bitcoin price",
    "who is the president",
    # Travel & Weather
    "what is the weather like tomorrow",
    "book a flight to London",
    "best hotels in Paris",
    # Home Repair & Shopping
    "how to fix a leaking pipe",
    "best places to buy cheap clothes",
    "car engine won't start",
    # AI/Creative Requests (To block it from acting like ChatGPT)
    "can you write a poem about stars",
    "translate this sentence to spanish",
    "write an email to my boss",
]

# --- 2. PRE-COMPUTING EMBEDTINGS ---

# FAQ pre-processing
faq_questions = []
faq_answers = []
for keys, answer in FAQ.items():
    for key in keys:
        faq_questions.append(key)
        faq_answers.append(answer)

faq_embeddings = model.encode(faq_questions)
emergency_embeddings = model.encode(EMERGENCY_EXAMPLES)
medical_embeddings = model.encode(MEDICAL_EXAMPLES)
non_medical_embeddings = model.encode(NON_MEDICAL_EXAMPLES)

# --- 3. RULE ENGINE ---


def validate_query(query: str):
    if not query or len(query.strip()) < 3:
        return "Please enter a valid question with more detail."
    return None


def check_emergency(query: str, threshold: float = 0.60):
    """
    Safety First: Checks if the user is in a critical medical situation.
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
    """Checks for standard identity and capability questions."""
    query_embedding = model.encode([query])
    similarities = cosine_similarity(query_embedding, faq_embeddings)[0]

    best_match_idx = np.argmax(similarities)
    if similarities[best_match_idx] >= threshold:
        return faq_answers[best_match_idx]

    return None


def check_domain(query: str):
    """
    Classifies if the prompt is medical or non-medical using a confidence margin.
    """
    query_embedding = model.encode([query])

    medical_score = np.max(cosine_similarity(query_embedding, medical_embeddings))
    non_medical_score = np.max(cosine_similarity(query_embedding, non_medical_embeddings))

    # Debugging
    print(
        f"[DEBUG] Medical Score: {medical_score:.2f} | Non-Medical Score: {non_medical_score:.2f}"
    )

    # Case A: The query is completely unrelated to anything the model knows
    if medical_score < 0.25 and non_medical_score < 0.25:
        return "I'm not quite sure what you're asking. Could you rephrase your question?"

    # Case B: It's clearly non-medical (with a 0.05 safety margin)
    if non_medical_score > (medical_score + 0.05):
        return (
            "I am a specialized medical assistant. I can only answer questions related "
            "to health, medicine, and wellness."
        )

    # Case C: It's a medical question (let it pass to the system)
    return None


def apply_rules(query: str):

    # 1. Basic Validation
    result = validate_query(query)
    if result:
        return result

    # 2. EMERGENCY OVERRIDE
    result = check_emergency(query)
    if result:
        return result

    # 3. Identity and FAQ
    result = check_faq(query)
    if result:
        return result

    # 4. Domain Restriction
    result = check_domain(query)
    if result:
        return result

    # 5. Success! The query is valid, medical, and safe to process with LLM.
    return None
