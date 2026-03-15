from chat_saude.rag.pipeline import rag_answer


def rag_tool(question: str):
    return rag_answer(question)
