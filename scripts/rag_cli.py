"""
Interactive CLI for RAG: asks questions and prints answers using chat_saude.rag.pipeline.
Run from repo root with PYTHONPATH=src: python scripts/rag_cli.py
"""
from chat_saude.rag.pipeline import rag_answer

while True:
    try:
        input_query = input("> Faça uma pergunta: ").strip()
        if not input_query:
            continue
        if input_query.lower() == "exit":
            break
        resposta = rag_answer(input_query)
        print("\nResposta:\n" + resposta)
        print()
    except KeyboardInterrupt:
        print("\nA encerrar...")
        break
    except Exception as e:
        print(f"Erro: {e}\n")
