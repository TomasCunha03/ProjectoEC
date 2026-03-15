"""
Interactive CLI to test the MongoDB tool pipeline.
Run from repo root with PYTHONPATH=src: python scripts/mongo_tool_terminal.py
"""
from chat_saude.tools.mongo_tool import (
    _get_dimension_values,
    _get_mongo_db,
    _list_collections,
    _search_indicators,
    mongo_query,
)


def test_connection(db):
    print("\n[1] A testar conexão ao MongoDB...")
    try:
        db.client.admin.command("ping")
        collections = _list_collections(db)
        print(f"    OK - {len(collections)} coleções encontradas:")
        for c in collections:
            print(f"       - {c}")
    except Exception as e:
        print(f"    ERRO: {e}")
        return False
    return True


def test_search_indicators(db):
    keyword = "diabetes"
    print(f"\n[2] A pesquisar indicadores para '{keyword}'...")
    results = _search_indicators(db, keyword, limit=5)
    if results:
        print(f"    OK - {len(results)} resultados:")
        for r in results:
            print(f"       [{r.get('IndicatorCode', 'N/A')}] {r.get('IndicatorName', 'N/A')}")
    else:
        print("    Sem resultados (base de dados vazia? corre api_ingestion.py primeiro)")


def test_dimension_values(db):
    dim = "COUNTRY"
    print(f"\n[3] A obter valores da dimensão '{dim}'...")
    results = _get_dimension_values(db, dim, limit=5)
    if results:
        print(f"    OK - primeiros {len(results)} países:")
        for r in results:
            print(f"       [{r.get('Code', 'N/A')}] {r.get('Title', 'N/A')}")
    else:
        print("    Sem resultados para esta dimensão")


def interactive_mode():
    print("\n" + "=" * 80)
    print("MODO INTERATIVO - MONGODB TOOL")
    print("=" * 80)
    print("Escreve uma pergunta para testar o pipeline completo (LLM + MongoDB)")
    print("Comandos: 'sair' para sair\n")

    while True:
        try:
            question = input("Pergunta: ").strip()
            if not question:
                continue
            if question.lower() in ["sair", "exit", "quit", "q"]:
                print("A encerrar...")
                break

            print("A processar...")
            result = mongo_query(question)
            print(f"\nResposta:\n{result}")
            print("-" * 80)

        except KeyboardInterrupt:
            print("\nInterrompido. Até logo!")
            break
        except Exception as e:
            print(f"Erro: {e}")
            print("-" * 80)


if __name__ == "__main__":
    db = _get_mongo_db()

    ok = test_connection(db)
    if ok:
        test_search_indicators(db)
        test_dimension_values(db)

    interactive_mode()
