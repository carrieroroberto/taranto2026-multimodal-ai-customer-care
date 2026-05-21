# Taranto 2026 RAG Backend - Handoff

Documento per prendere in mano il backend e portarlo a chiusura mentre il frontend viene sviluppato in parallelo.

## Stato Attuale

Il backend e' un MVP FastAPI + ChromaDB + Ollama per un assistente customer-care sui Giochi del Mediterraneo Taranto 2026.

Componenti gia presenti:

- Knowledge base JSONL in `backend/data/kb.jsonl`, 2557 record.
- ChromaDB persistente via Docker volume.
- Embedding con `BAAI/bge-m3`.
- Ingest automatico all'avvio se Chroma e' vuoto, incompleto o creato con embedding model diverso.
- API FastAPI:
  - `GET /health`
  - `POST /chat`
- Pipeline RAG:
  - query planner LLM;
  - multi-query retrieval su Chroma;
  - fallback globale se il filtro dominio non produce risultati;
  - deduplica per document id;
  - reranking leggero;
  - LLM finale con prompt grounded;
  - fonti e Google Maps runtime se ci sono coordinate;
  - ticket draft in caso di escalation.
- Guardrail principali:
  - non inventare prezzi, biglietti, disponibilita, risultati live, coordinate o orari;
  - ticketing non disponibile se la KB non contiene dati pubblicati;
  - risposta nella lingua originale dell'utente quando il planner LLM funziona.

## Configurazione Consigliata

Usare un solo file `.env`, derivato da `.env.example`.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Modelli configurati:

```env
OLLAMA_MODEL=qwen3:8b
QUERY_PARSER_MODEL=qwen3:8b
```

Ragione:

- `qwen3:8b` viene usato sia come query planner sia come generatore finale.
- Il planner deve produrre solo JSON, non la risposta finale.
- Usare lo stesso modello evita overhead di caricamento e rende piu stabile il piano semantico.
- `OLLAMA_NUM_PARALLEL=1` evita saturazione VRAM.
- `OLLAMA_MAX_LOADED_MODELS=1` mantiene un solo modello residente.
- `LLM_CONTEXT_WINDOW=4096` e `MAX_CONTEXT_CHARS=3200` sono valori prudenti per una workstation con GPU consumer.

Prerequisiti accelerazione GPU:

1. Driver NVIDIA installato.
2. Docker Desktop aggiornato.
3. NVIDIA Container Toolkit installato se si usa Docker Engine/Linux.
4. Verifica:

```powershell
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Se il comando non vede la GPU, Ollama andra' in CPU e la pipeline sara' molto lenta.

## Avvio

```powershell
docker compose up --build -d
docker compose logs -f ollama
docker compose logs -f backend
```

Il servizio `ollama-pull` scarica:

- `${OLLAMA_MODEL:-qwen3:8b}`
- `${QUERY_PARSER_MODEL:-qwen3:8b}` solo se diverso dal modello finale

La prima partenza puo' richiedere tempo per download modelli e ingest KB.

## Verifiche Rapide

Health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json -Depth 10
```

Atteso:

```json
{
  "status": "ok",
  "collection_count": 2557,
  "kb_ready": true
}
```

Chat:

```powershell
$body = @{
  message = "Quando iniziano i Giochi del Mediterraneo di Taranto 2026?"
  session_id = "smoke-1"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 10
```

Risposta attesa:

- deve indicare il 21 agosto 2026;
- deve citare la cerimonia di apertura;
- non deve fare escalation;
- deve restituire almeno una fonte.

## Architettura Codice

File principali:

- `backend/app/api/chat.py`
  - route FastAPI `/chat`;
  - non contiene business logic.

- `backend/app/services/chat_service.py`
  - orchestrazione della chiamata chat;
  - validazione messaggio;
  - chiama planner, retrieval, answer generation;
  - costruisce `sources`, `maps`, escalation e `ticket_draft`.

- `backend/app/services/llm_service.py`
  - query planner LLM;
  - fallback plan minimale;
  - prompt risposta finale;
  - chiamata Ollama;
  - guardrail risposta;
  - traduzione risposte statiche.

- `backend/app/services/rag_service.py`
  - startup/ingest KB;
  - embedding;
  - retrieval Chroma;
  - fallback globale;
  - merge/dedup;
  - reranking leggero;
  - conversione in contesto.

- `backend/app/config.py`
  - configurazione da `.env`.

## Pipeline Attuale

```text
User message
-> POST /chat
-> chat_service.answer_chat
-> llm_service.build_query_plan
-> Query Planner LLM JSON
-> rag_service.retrieve_context
-> multi-query Chroma retrieval
-> fallback globale se filtro dominio e' debole
-> reranking leggero
-> llm_service.build_answer
-> Final Answer LLM
-> risposta grounded + sources + maps + escalation
```

## Query Planner JSON

Il planner deve restituire solo JSON:

```json
{
  "query_it": "...",
  "language": "it|en|fr|es|de|other",
  "intent": "general_info|event_schedule|venue_info|ticketing|transport|accessibility|volunteering|history|contacts|complaint|unknown",
  "domains": ["general", "calendar"],
  "normalized_query": "...",
  "entities": {
    "sport": null,
    "city": null,
    "venue": null,
    "date": null,
    "event": null,
    "ticket_type": null
  },
  "filters": ["..."],
  "expanded_queries": ["..."],
  "retrieval_queries": [
    {
      "query": "...",
      "domain": "calendar",
      "weight": 1.0
    }
  ],
  "needs_clarification": false,
  "clarification_question": null
}
```

Fallback se il planner fallisce:

```json
{
  "language": "it",
  "intent": "unknown",
  "domains": ["general"],
  "normalized_query": "messaggio originale",
  "entities": {},
  "retrieval_queries": [
    {
      "query": "messaggio originale",
      "domain": null,
      "weight": 1.0
    }
  ]
}
```

## Cosa E' Stato Appena Refactorizzato

La vecchia logica rigida basata su dizionari keyword e' stata rimossa o ridotta.

Non ci sono piu':

- `DOMAIN_SIGNALS`
- `LANGUAGE_HINTS`
- `CITY_NAMES`
- `DOMAIN_PRECEDENCE`
- `detect_domain()`
- `refine_domain()`
- `expand_queries()` hardcoded
- dizionari sport/citta/traduzioni nel codice Python

Il dominio ora arriva dal planner LLM. Il retrieval lo usa come hint, non come vincolo assoluto.

Nota importante: il contratto KB attuale vieta metadata come `domain`, `sport`, `city`, `venue`. Per questo il codice e' gia pronto a usare `metadata.domain` se in futuro viene autorizzato, ma oggi lavora soprattutto su `title`, `type`, `address` e `document`.

## Stato Endpoint

Gia pronti:

- `GET /health`
- `POST /chat`

Mancano ancora:

- `POST /feedback`.
- `POST /tickets` vero e persistente.
- Persistenza sessioni.
- Storage feedback/ticket.
- Dashboard operatori.

Per il frontend, oggi usare solo:

```text
POST http://127.0.0.1:8000/chat
```

Request:

```json
{
  "message": "string",
  "session_id": "optional string"
}
```

Response:

```json
{
  "session_id": "string|null",
  "answer": "string",
  "sources": ["string"],
  "maps": "string|null",
  "should_escalate": false,
  "reason": "string|null",
  "ticket_draft": null
}
```

## Cose Da Migliorare Prima Di Chiudere Il Backend

Priorita alta:

1. Rendere il planner piu veloce.
   - Con accelerazione GPU dovrebbe andare molto meglio che in CPU.
   - Se resta lento, provare planner piu piccolo:
     - `qwen2.5:3b`
     - `qwen2.5:1.5b`
     - `llama3.2:3b`
     - provider esterno veloce tipo Groq/Cerebras.

2. Migliorare `sources`.
   - Oggi sono URL semplici.
   - Sarebbe meglio restituire oggetti con `title`, `type`, `url`.
   - Questo richiede aggiornare schema e frontend.

3. Aggiungere test/evaluation script.
   - Input: JSONL con `message` e `target_answer`.
   - Output: JSONL con answer, sources, reason, latency, verdict.
   - KPI minimi: answer correctness, faithfulness, hallucination, escalation correctness, source usefulness, latency.

4. Logging piu utile.
   - Salvare latency del planner, retrieval, generation.
   - Salvare `intent`, `domains`, retrieved ids, selected ids.

Priorita media:

5. Endpoint `POST /tickets`.
   - Oggi esiste solo `ticket_draft` nella risposta chat.
   - Serve endpoint vero se si vuole simulare customer-care.

6. Endpoint `POST /feedback`.
   - Utile per frontend: thumbs up/down e commento.
   - Anche senza DB, puo' scrivere JSONL locale in sviluppo.

7. Gestione sessione/follow-up.
   - Attualmente `session_id` viene restituito ma non c'e memoria conversazionale persistente.
   - I follow-up tipo "E quanto costa?" non hanno ancora contesto sessione affidabile.

8. Clarification handling.
   - Il planner ha `needs_clarification`, ma la risposta non usa ancora in modo deterministico `clarification_question`.
   - Se true, il backend dovrebbe rispondere direttamente con la domanda di chiarimento senza retrieval pesante.

9. Migliorare ticketing guardrail.
   - Il blocco attuale e' buono, ma resta euristico.
   - Verificare su dataset ticketing che non compaiano prezzi, "gratis" o canali inventati.

Priorita bassa:

10. Separare ulteriormente moduli.
   - `llm_service.py` e `rag_service.py` sono ancora grandi.
   - In futuro si puo' dividere in:
     - `query_planner.py`
     - `prompt_builder.py`
     - `generator.py`
     - `retriever.py`
     - `reranker.py`

11. Supporto multimodale.
   - Non implementare ora.
   - Roadmap futura: OCR immagini/PDF, audio Whisper, venue recognition.

## Test Set Consigliato

Smoke test manuali:

```text
Quando iniziano i Giochi del Mediterraneo di Taranto 2026?
quando finiscono i giochi del mediterraneo 2026?
Dove si svolge il taekwondo?
Dove si gioca la pallavolo?
I biglietti per Taranto 2026 sono gia disponibili?
Voglio vedere il basket: dimmi dove si gioca, se serve biglietto e come posso arrivarci.
Where can I watch basketball during Taranto 2026?
Je veux savoir si les billets sont gratuits ou payants.
Quanti parcheggi liberi ci sono ora vicino al PalaMazzola?
Chi vincera il medagliere finale?
```

Attesi:

- date e venue solo se presenti in KB;
- biglietti: nessun prezzo inventato;
- live data: dichiarare non disponibile;
- lingua finale uguale alla lingua utente;
- sources presenti quando ci sono contesti;
- maps presente solo quando c'e una singola venue con coordinate utili.

## Limiti Noti

- La KB resta tutta in italiano; il planner traduce query estere in italiano.
- Non ci sono dati live: parcheggi, bus live, risultati, medagliere live non devono essere inventati.
- Non c'e DB: ticket, feedback e sessioni non persistono.
- La qualita dipende molto dal planner LLM. Se il planner produce JSON scarso, il retrieval peggiora.
- Con CPU la pipeline a due LLM e' troppo lenta. Con accelerazione GPU dovrebbe essere usabile, ma va misurata.

## Comandi Utili

Log backend:

```powershell
docker compose logs -f backend
```

Log Ollama:

```powershell
docker compose logs -f ollama
```

Lista modelli:

```powershell
docker exec -it ta2026-ollama ollama list
```

Pull manuale modelli:

```powershell
docker exec -it ta2026-ollama ollama pull qwen3:8b
```

Restart solo backend:

```powershell
docker compose restart backend
```

Restart Ollama:

```powershell
docker compose restart ollama
```

Reset Chroma e modelli solo se serve davvero:

```powershell
docker compose down -v
```

Attenzione: cancella i volumi Docker, quindi Chroma, Hugging Face cache e modelli Ollama verranno riscaricati/reingestiti.

## Suggerimento Di Lavoro

Per chi prende il backend:

1. Avviare con `.env.example` copiato in `.env`.
2. Misurare latency planner, retrieval, answer.
4. Lanciare smoke test.
5. Correggere retrieval/reranking dove fallisce.
6. Aggiungere evaluation script e KPI.
7. Implementare feedback/tickets minimi solo dopo che `/chat` e' stabile.

Per il frontend:

- integrare prima `/chat`;
- mostrare `answer`, `sources`, `maps`;
- se `should_escalate=true`, mostrare `ticket_draft`;
- prevedere loading lungo perche il backend puo' impiegare molti secondi durante generazione LLM.
