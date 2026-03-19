import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer("all-MiniLM-L6-v2")


FAQ = {
    ("who are you", "who are you?", "what are you"): (
        "I am DrHouseGPT, an AI-based medical assistant. "
        "I can help you clarify health questions and preventive medicine topics. "
        "⚠️ This information is educational and does not replace "
        "consultation with a healthcare professional."
    ),
    ("what do you do", "what is your function", "what can you do"): (
        "I answer medical questions based on scientific literature, "
        "clinical guidelines, and structured data."
    ),
    ("how do you work", "how does it work", "how do you function"): (
        "I use a RAG system that searches reliable medical documents "
        "and consults databases before generating responses. "
        "Answers are provided based on scientific evidence "
        "and structured information."
    ),
}


MEDICAL_EXAMPLES = [
    "what is hypertension",
    "diabetes symptoms",
    "I have fever and cough",
    "how to prevent the flu",
    "paracetamol effects",
]

NON_MEDICAL_EXAMPLES = [
    "who won the game",
    "best movie of 2024",
    "cake recipe",
    "restaurants in Lisbon",
    "football result",
]


medical_embeddings = model.encode(MEDICAL_EXAMPLES)
non_medical_embeddings = model.encode(NON_MEDICAL_EXAMPLES)


def validate_query(query: str):

    if not query or len(query.strip()) < 3:
        return "Please enter a valid question."

    return None


def check_faq(query: str):
    q = query.lower()
    for keys, answer in FAQ.items():
        if any(k in q for k in keys):
            return answer
    return None


def check_domain(query: str):

    query_embedding = model.encode([query])

    sim_medical = cosine_similarity(query_embedding, medical_embeddings)
    sim_non_medical = cosine_similarity(query_embedding, non_medical_embeddings)

    medical_score = np.max(sim_medical)
    non_medical_score = np.max(sim_non_medical)

    if non_medical_score > medical_score:
        return "This assistant answers only health and medicine questions."

    return None


def apply_rules(query: str):

    result = validate_query(query)
    if result:
        return result

    result = check_faq(query)
    if result:
        return result

    result = check_domain(query)
    if result:
        return result

    return None
