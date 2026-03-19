#!/usr/bin/env python3
"""Interactive terminal test for tool selection agent.
Run this to manually test the agent with your own questions.
"""

from tool_selection_agent import select_tool


def main():
    print("=" * 80)
    print("INTERACTIVE TEST - TOOL SELECTION AGENT")
    print("=" * 80)

    while True:
        try:
            question = input("\nQuestion: ").strip()

            if not question:
                continue

            if question.lower() in ["sair", "exit", "quit", "q"]:
                print("\nExiting... See you!")
                break

            print("\nAnalyzing...")
            result = select_tool(question)

            print(f"  Ferramenta: {result['tool'] or 'NONE'}")
            print(f"  Query: {result['query']}")
            print("-" * 80)

        except KeyboardInterrupt:
            print("\n\nInterrupted by the user. See you!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Make sure Ollama is running: ollama serve")
            print("-" * 80)


if __name__ == "__main__":
    main()
