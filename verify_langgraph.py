import asyncio
import sys
import os

# Aggiunge la root del progetto al path per importare i moduli del backend
sys.path.append(os.getcwd())

from backend.app.services.agent_orchestrator import run_agent_orchestration
from backend.app.schemas.chat import ChatRequestDTO

async def test_langgraph_flow():
    print("--- Inizio Test LangGraph Orchestrator ---")
    
    test_queries = [
        "Qual è il motto dei Giochi del Mediterraneo 2026?",
        "Vorrei parlare con un operatore umano.",
        "Cosa sono i Giochi del Mediterraneo?"
    ]
    
    for query in test_queries:
        print(f"\nDomanda: {query}")
        try:
            result = await run_agent_orchestration(
                message=query,
                history=[],
                language="it"
            )
            
            print(f"Risposta: {result['answer']}")
            print(f"Escalation richiesta: {result['should_escalate']}")
            print(f"Ragione escalation: {result['escalation_reason']}")
            if result.get('plan'):
                print(f"Intento rilevato: {result['plan'].intent}")
            print(f"Fonti trovate: {len(result['contexts'])}")
            
        except Exception as e:
            print(f"Errore durante il test: {e}")

    print("\n--- Fine Test ---")

if __name__ == "__main__":
    # Assicurati che le variabili d'ambiente siano caricate se necessario
    # os.environ["DATABASE_URL"] = "..."
    asyncio.run(test_langgraph_flow())
