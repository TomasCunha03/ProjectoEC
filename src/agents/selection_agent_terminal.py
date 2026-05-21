#!/usr/bin/env python3
"""Interactive terminal test harness for the tool selection agent.

Run this script directly to manually probe the agent with arbitrary questions
and see which backend tools it selects, without going through the full
application stack.  Useful for quick smoke-tests after changing the LLM model
or the system prompt in prompts.yaml.

Usage:
    python selection_agent_terminal.py

Prerequisites:
    Ollama must be running and the configured model must be available
    (ollama serve / ollama pull <model>).
"""

from agents.tool_selection_agent import select_tool


def main():
    """Run the interactive REPL loop until the user exits."""
    print("=" * 80)
    print("INTERACTIVE TEST - TOOL SELECTION AGENT")
    print("=" * 80)

    while True:
        try:
            question = input("\nQuestion: ").strip()

            # Skip blank input rather than sending an empty string to the LLM.
            if not question:
                continue

            # Accept exit commands in both Portuguese ("sair") and English.
            if question.lower() in ["sair", "exit", "quit", "q"]:
                print("\nExiting... See you!")
                break

            print("\nAnalyzing...")
            result = select_tool(question)

            print(f"  Ferramenta: {result['tool'] or 'NONE'}")
            print(f"  Query: {result['query']}")
            print("-" * 80)

        except KeyboardInterrupt:
            # Ctrl-C is a normal way to leave an interactive tool, so handle
            # it gracefully instead of printing a traceback.
            print("\n\nInterrupted by the user. See you!")
            break
        except Exception as e:
            # Catching broadly here is intentional — this is a developer test
            # harness, and any error should be surfaced without crashing the loop.
            print(f"\nError: {e}")
            print("Make sure Ollama is running: ollama serve")
            print("-" * 80)


if __name__ == "__main__":
    main()
