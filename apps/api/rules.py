import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer("all-MiniLM-L6-v2")


FAQ = {
    ("quem és", "quem és tu", "quem é você"): (
        "Sou o DrHouseGPT, um assistente médico baseado em IA. "
        "Posso ajudá-lo a esclarecer dúvidas de saúde e medicina preventiva. "
        "⚠️ Esta informação é educativa e não substitui consulta com profissional de saúde."
    ),
    ("o que fazes", "para que serves", "qual a tua função"): (
        "Respondo a perguntas médicas com base em literatura científica, "
        "diretrizes clínicas e dados estruturados."
    ),
    ("como funcionas", "como funcionas tu", "como trabalhas"): (
        "Utilizo um sistema RAG que pesquisa documentos médicos confiáveis "
        "e consulto bases de dados antes de gerar respostas. "
        "As respostas são fornecidas com base em evidência científica "
        "e informações estruturadas."
    ),
}


MEDICAL_EXAMPLES = [
    "o que é hipertensão",
    "sintomas de diabetes",
    "tenho febre e tosse",
    "como prevenir gripe",
    "efeitos do paracetamol",
]

NON_MEDICAL_EXAMPLES = [
    "quem ganhou o jogo",
    "melhor filme de 2024",
    "receita de bolo",
    "restaurantes em lisboa",
    "resultado do futebol",
]


medical_embeddings = model.encode(MEDICAL_EXAMPLES)
non_medical_embeddings = model.encode(NON_MEDICAL_EXAMPLES)


def validate_query(query: str):

    if not query or len(query.strip()) < 3:
        return "Por favor introduza uma pergunta válida."

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
        return "Este assistente responde apenas a perguntas relacionadas com saúde e medicina."

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
