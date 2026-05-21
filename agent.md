# Chatbot AI Multimodale per Customer Care Giochi del Mediterraneo 2026 a Taranto

## Obiettivo generale

Sviluppare una prototipo universitaria funzionante di un sistema di customer care AI per i Giochi del Mediterraneo 2026 a Taranto.

Il sistema deve permettere a un utente di fare domande testuali, vocali o tramite immagini, ricevere una risposta utile generata da una pipeline RAG, e creare eventualmente un ticket per operatore umano quando la richiesta non è risolvibile automaticamente.

Il progetto deve essere sviluppabile in circa un mese, quindi la priorità è avere una demo stabile, comprensibile e completa nel flusso principale.

Non serve una struttura enterprise. Non serve gestire ogni casistica possibile. Non serve codice eccessivamente astratto. Serve una demo che funzioni bene end-to-end.

## Principio guida

Preferire sempre la soluzione più semplice che funziona.

Evitare:
- architetture troppo complesse;
- dizionari enormi di keyword;
- hardcoding per ogni singolo caso;
- gestione eccessiva degli errori;
- troppi livelli di classi e astrazioni;
- microservizi inutili;
- pattern enterprise non necessari;
- dashboard troppo sofisticate;
- multimodalità troppo avanzata se non serve alla demo.

Il codice deve essere:
- semplice;
- leggibile;
- modulare quanto basta;
- facile da eseguire.

## Architettura MVP

Il sistema è composto da:

1. Frontend React per utente finale.
2. Frontend React per dashboard operatore.
3. Backend FastAPI.
4. ChromaDB come vector database.
5. bge-m3 come modello embedding.
6. Ollama + Qwen3:8B come LLM locale sul PC con RTX 3060 (come fallback, altrimenti uso di api di modelli gratuiti con limiti alti di OpenAI)
7. Whisper per trascrizione audio.
8. Tesseract per OCR su immagini.
9. Database relazionale per conversazioni, messaggi, KPI e ticket.
10. Knowledge base locale in formato JSONL.

Flusso principale:

User text/audio/image
→ React frontend
→ FastAPI backend
→ eventuale Whisper/OCR
→ LLM di parsing per traduzione e normalizzazione input ed estrazione struttura che faciliti il retrieval
→ retrieval su ChromaDB
→ generazione risposta esaustiva e compoleta con LLM di output
→ salvataggio conversazione/messaggi/KPI
→ creazione eventuale ticket
→ risposta al frontend
→ attesa del feedback pollice su o pollice giu dell'utente come valutazione (serve per kpi)

## Divisione lavoro

### Backend

Il backend viene sviluppato sul PC del membro con RTX 3060, perché ha risorse migliori per far girare Ollama e Qwen3:8B.

Il backend deve occuparsi di:
- API REST;
- RAG;
- ChromaDB;
- Ollama;
- ingestione knowledge base;
- Whisper;
- Tesseract;
- database relazionale;
- ticketing;
- KPI base.

### Frontend

Il frontend viene sviluppato in parallelo su un altro PC.

Il frontend deve comunicare col backend tramite URL configurabile in `.env`.

Non deve conoscere l’implementazione interna del backend. Deve solo usare gli endpoint definiti.