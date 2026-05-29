import asyncio
import sys
import os
import logging

# Aggiunge la root del progetto al path
sys.path.append(os.getcwd())

from backend.app.services.agent_orchestrator import run_agent_orchestration
from backend.app.config import settings
from backend.app.services import rag_service

# Mock della KB come pronta per il test locale
rag_service._KB_READY = True
rag_service._KB_STATUS = "ok"

# Configura il logging per vedere i nodi di LangGraph in azione
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def test_langgraph():
    print("="*50)
    print("🚀 TEST LANGGRAPH ORCHESTRATOR - TARANTO 2026")
    print("="*50)
    
    # Query di test per verificare diversi percorsi nel grafo
    queries = [
        {
            "name": "General Info",
            "query": "Cosa sono i Giochi del Mediterraneo?"
        },
        {
            "name": "Operator Request (Direct Planning Path)",
            "query": "Voglio parlare con un operatore umano."
        },
        {
            "name": "Ticketing Info",
            "query": "Quanto costano i biglietti?"
        },
        {
            "name": "Specific Location (Venue)",
            "query": "Dove si trova lo stadio Iacovone?"
        }
    ]
    
    for q in queries:
        print(f"\n👉 TEST: {q['name']}")
        print(f"💬 Domanda: {q['query']}")
        
        try:
            # Esegue l'orchestratore
            # Nota: Assicurati che Ollama sia attivo se non sei in AI_DISABLED
            result = await run_agent_orchestration(
                message=q['query'],
                history=[],
                language="it"
            )
            
            print(f"✅ Nodo Finale Raggiunto")
            print(f"🤖 Risposta: {result['answer']}")
            print(f"🔍 Fonti recuperate: {len(result['contexts'])}")
            print(f"🚩 Escalation: {result['should_escalate']} (Motivo: {result['escalation_reason']})")
            
        except Exception as e:
            print(f"❌ Errore durante l'esecuzione: {e}")
            
    print("\n" + "="*50)
    print("🏁 TEST COMPLETATO")
    print("="*50)

if __name__ == "__main__":
    if settings.ai_disabled:
        print("⚠️  ATTENZIONE: AI_DISABLED è attivo. Il test userà risposte di fallback.")
    
    asyncio.run(test_langgraph())
