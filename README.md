# T.A.L.O.S. | Taranto 2026 AI Live Operator Support

## Chatbot AI Multimodale di Customer Care per i Giochi del Mediterraneo

T.A.L.O.S. è una web app full-stack che integra una chat multilingua, una pipeline RAG basata su Knowledge Base, una dashboard operatore per la gestione dei ticket e un modulo di benchmarking KPI.

L'obiettivo del progetto è fornire risposte automatiche esaustive, basate sulle fonti disponibili nella knowledge base, evitando allucinazioni e risposte inventate.

## Funzionalità

- ChatBot AI multilingua con supporto per italiano, inglese, spagnolo, francese e arabo.
- Risposte basate sulla knowledge base fornita.
- Rilevamento/gestione lingua e risposta nella lingua dell'utente.
- Query planning LLM per dominio, intento e query di retrieval.
- Retrieval multi-query su database vettoriale ChromaDB.
- Reranking dei documenti recuperati.
- Fonti mostrate nel messaggio come link ipertestuali, quando disponibili.
- Input multimodale con testo, immagini e audio.
- Risposta audio con playback automatico.
- Upload immagine da pulsante, drag and drop e copia/incolla.
- Anteprima immagini con zoom.
- Feedback utente sui messaggi del bot.
- Apertura ticket verso operatore umano su feedback negativo.
- Dashboard operatore con login, lista ticket, filtri, dettaglio conversazione, traduzione, suggerimento email di risposta multilingua e chiusura ticket.
- Gestione della knowledge base tramite GUI con inserimento record e ingest immediato.
- Tema chiaro/scuro e preferenze salvate in `localStorage`.
- PWA installabile e testabile anche da mobile tramite tunnel HTTPS Cloudflare.

## Architettura

```text
Utente / Operatore
      |
      v
Frontend React
      |
      | /api/*
      v
Backend FastAPI
      |
      +-- Postgres: conversazioni, messaggi, feedback, ticket, operatori
      |
      +-- ChromaDB: retrieval semantico sulla knowledge base
      |
      +-- Ollama o Groq: query planning, generazione, multimodale
      |
      v
Risposta + fonti / ticket operatore / KPI
```

Servizi Docker:

| Servizio | Container | Porta | Ruolo |
| --- | --- | --- | --- |
| `frontend` | `talos-frontend` | `5173` | App React |
| `backend` | `talos-backend` | `8000` | API FastAPI |
| `vector-db` | `talos-vector-db` | `8001` | ChromaDB |
| `database` | `talos-database` | `5433` | Postgres |
| `pgadmin` | `talos-pgadmin` | `5050` | UI database |
| `llm` | `talos-llm` | `11434` | Ollama locale |
| `llm-init` | `talos-llm-init` | - | Pull modelli Ollama |
| `cloudflared` | `talos-cloudflared` | - | Tunnel HTTPS temporaneo |

## Struttura

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # Route FastAPI
│   │   ├── repositories/     # Postgres e ChromaDB
│   │   ├── schemas/          # DTO request/response
│   │   ├── services/         # RAG, LLM, multimodale, ticket, ingest KB
│   │   ├── config.py
│   │   └── main.py
│   ├── data/
│   │   └── kb.jsonl          # Knowledge base
│   ├── db/
│   │   └── init.sql          # Schema iniziale Postgres
│   ├── requirements.txt
│   └── Dockerfile
├── eval/
│   ├── run_kpi_eval.py       # Runner benchmark KPI
│   ├── test_dataset.jsonl    # Dataset testuale di valutazione
│   └── outputs/
│       └── results.csv       # Output CSV
├── frontend/
│   ├── public/               # Manifest PWA, icone, asset pubblici
│   ├── src/
│   │   ├── components/
│   │   ├── pages/            # ChatPage, OperatorDashboardPage e KnowledgeBaseAdminPage
│   │   ├── services/         # Client API frontend
│   │   ├── utils/
│   │   ├── i18n.js
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── run.bat
├── .env.example
└── README.md
```

## Requisiti

- Docker Desktop con Docker Compose.
- Groq API key per usare la modalità senza GPU locale.
- GPU NVIDIA e runtime Docker NVIDIA solo per la modalità completa con Ollama locale.
- Spazio disco sufficiente per modelli, cache embedding, volumi Postgres e ChromaDB.

Il primo avvio può richiedere alcuni minuti per scaricare immagini Docker, inizializzare i volumi e indicizzare la knowledge base.

## Configurazione

Creare il file `.env` partendo dall'esempio:

```powershell
Copy-Item .env.example .env
```

Su macOS/Linux:

```bash
cp .env.example .env
```

Variabili principali:

| Variabile | Descrizione |
| --- | --- |
| `POSTGRES_DB` | Database Postgres, default `talos` |
| `POSTGRES_USER` | Utente Postgres, default `talos` |
| `POSTGRES_PASSWORD` | Password Postgres di sviluppo |
| `DATABASE_URL` | URL Postgres per esecuzione backend fuori Docker |
| `COLLECTION_NAME` | Nome collezione ChromaDB |
| `KB_PATH` | Path knowledge base |
| `EMBEDDING_MODEL` | Modello embedding |
| `N_RESULTS` | Numero base di risultati recuperati |
| `AUTO_INGEST_ON_STARTUP` | Ingest automatico knowledge base all'avvio |
| `FORCE_REINGEST_ON_STARTUP` | Reindicizzazione forzata a ogni avvio |
| `OLLAMA_MODEL` | Modello LLM locale |
| `QUERY_PARSER_MODEL` | Modello per query planning |
| `VISION_MODEL` | Modello vision locale |
| `GROQ_API_KEY` | Chiave Groq |
| `GROQ_MODEL` | Modello Groq testuale |
| `GROQ_VISION_MODEL` | Modello Groq vision |
| `GROQ_TRANSCRIPTION_MODEL` | Modello Groq audio |
| `LLM_FALLBACK_TIMEOUT_SECONDS` | Timeout prima del fallback Groq |
| `MULTIMODAL_PROVIDER` | `groq`, `local` o `auto` |
| `VITE_API_BASE_URL` | Base API frontend, default `/api` |
| `VITE_PROXY_TARGET` | Target proxy verso backend |

Non inserire IP o URL backend assoluti nel frontend. Le chiamate React devono usare path relativi come `/api/chat`.

## Avvio Rapido

Su Windows:

```bat
run.bat lite
```

La modalità `lite` è consigliata se è configurata `GROQ_API_KEY`. Avvia frontend, backend, Postgres, pgAdmin, ChromaDB e Cloudflare, senza avviare Ollama locale.

Per la modalità completa con Ollama:

```bat
run.bat
```

Con Docker Compose:

```bash
docker compose up -d --build
```

Link locali:

- ChatBot: <http://localhost:5173>
- Dashboard operatore: <http://localhost:5173/operator>
- Gestione knowledge base: <http://localhost:5173/knowledge>
- API docs: <http://localhost:8000/docs>
- Health backend: <http://localhost:8000/health>
- ChromaDB: <http://localhost:8001>
- pgAdmin: <http://localhost:5050>
- Postgres: `localhost:5433`

Accesso pgAdmin:

- Email: `admin@talos.com`
- Password: `ChatbotTaranto2026!`

Connessione Postgres da pgAdmin:

- Host: `database`
- Port: `5432`
- Maintenance database: `talos`
- Username: `talos`
- Password: `ChatbotTaranto2026!`

Da strumenti installati sul PC usare host `localhost` e porta `5433`.

Per fermare i servizi:

```bash
docker compose down
```

Evitare `docker compose down -v` se non si vogliono cancellare database, modelli, upload e indice ChromaDB.

## Accesso Mobile e PWA

Per microfono e PWA su iPhone serve HTTPS. Il servizio `cloudflared` crea un tunnel temporaneo.

Visualizzare il link:

```bash
docker compose logs -f cloudflared
```

Cercare un URL simile a:

```text
https://nome-casuale.trycloudflare.com
```

Da iPhone:

1. Aprire l'URL in Safari.
2. Testare chat, audio e immagini.
3. Installare la PWA da Condividi -> Aggiungi alla schermata Home.

Il link gratuito `trycloudflare.com` cambia a ogni riavvio del tunnel.

## API Principali

Le API sono esposte anche con prefisso `/api`, usato dal frontend tramite proxy.

### Health

```http
GET /health
GET /api/health
```

### Chat Testuale

```http
POST /api/chat
Content-Type: application/json
```

Esempio:

```json
{
  "message": "Dove si svolge il nuoto a Taranto 2026?",
  "session_id": "sessione-demo",
  "language": "it"
}
```

La risposta include:

- `conversation_id`;
- `user_message_id`;
- `bot_message_id`;
- `answer`;
- `sources`;
- `should_escalate`;
- `ticket_draft`, quando applicabile.

### Conversazioni

```http
POST /api/conversations
GET /api/conversations/{session_id}/messages
POST /api/conversations/{session_id}/messages
DELETE /api/conversations/{session_id}/messages
```

Il frontend salva un `session_id` in `localStorage`, riusa la conversazione alla riapertura della PWA e ricarica i messaggi persistiti da Postgres.

### Chat Audio

```http
POST /api/chat/audio
Content-Type: multipart/form-data
```

Campi:

- `file`: file audio;
- `session_id`: opzionale;
- `language`: opzionale.

### Chat Multimodale

```http
POST /api/chat/multimodal
Content-Type: multipart/form-data
```

Campi:

- `message`: testo dell'utente, richiesto per immagine;
- `file`: file immagine o audio;
- `session_id`: opzionale;
- `language`: opzionale.

Il frontend consente tre combinazioni: testo, testo + immagine, solo audio.

### Feedback

```http
PATCH /api/messages/{message_id}/feedback
POST /api/feedback
```

Il feedback valorizza `messages.satisfaction` sui messaggi bot:

- `true`: risposta utile;
- `false`: risposta non utile;
- `null`: feedback rimosso.

Il feedback negativo può attivare il flusso di ticket verso operatore.

### Ticket

```http
POST /api/tickets
Content-Type: application/json
```

Esempio:

```json
{
  "conversation_id": "uuid-conversazione",
  "escalated_message_id": "uuid-messaggio-bot",
  "user_email": "utente@example.com",
  "language": "it"
}
```

Il ticket viene salvato in Postgres nella tabella `tickets` e collegato alla conversazione.

## Dashboard Operatore

Path frontend:

```text
/operator
```

Operatore Default:

- Email: `operatore@talos.it`
- Password: `OperatoreTaranto2026!`

Funzioni disponibili:

- login/logout con JWT;
- lista ticket con filtri e ordinamento;
- modal dettaglio ticket con conversazione completa;
- visualizzazione media allegati;
- traduzione della conversazione;
- generazione bozza email;
- chiusura e riapertura ticket;
- polling automatico dei nuovi ticket.

Route usate dalla dashboard:

```http
POST /api/operator/login
POST /api/operator/logout
GET /api/operator/me
GET /api/operator/tickets
GET /api/operator/tickets/{ticket_id}
POST /api/operator/tickets/{ticket_id}/translate
POST /api/operator/tickets/{ticket_id}/email-draft
PATCH /api/operator/tickets/{ticket_id}/status
```

## Gestione Knowledge Base

Path frontend:

```text
/knowledge
```

La pagina usa login operatore e permette di aggiungere nuove informazioni alla knowledge base tramite form.

Flusso operativo:

1. l'operatore accede con le credenziali della dashboard;
2. compila titolo, fonte, tipo, dominio e documento;
3. se il tipo o il dominio descrivono un luogo, il form abilita anche indirizzo, latitudine e longitudine;
4. al click su `Aggiungi`, il backend crea il record JSONL e lo indicizza in ChromaDB;
5. la richiesta termina solo quando il nuovo contenuto è disponibile per il retrieval del ChatBot.

Campi del form:

| Campo | Obbligatorio | Note |
| --- | --- | --- |
| `title` | Si | Titolo del contenuto informativo |
| `source_url` | Si | URL della fonte informativa |
| `item_type` | Si | Tipo del record, scelto dalle opzioni backend |
| `domain` | Si | Dominio informativo, scelto dalle opzioni backend |
| `document` | Si | Testo indicizzabile nella knowledge base |
| `address` | Solo se attivo | Abilitato per record coerenti con informazioni geografiche |
| `latitude` | Solo se attivo | Valore numerico tra -90 e 90 |
| `longitude` | Solo se attivo | Valore numerico tra -180 e 180 |

L'ID record non viene richiesto all'operatore, ma viene generato automaticamente dal backend a partire dal titolo e da un suffisso univoco.

I campi geografici sono abilitati quando `item_type` è uno tra `venue`, `event_schedule`, `transport`, `accessibility`, oppure quando `domain` è `venue` o `accessibility`. Se la combinazione selezionata non è geografica, i campi restano disabilitati e non vengono inviati.

Il backend valida il payload, aggiunge un record JSONL a `backend/data/kb.jsonl` e indicizza subito il nuovo documento in ChromaDB.

Route protette:

```http
GET /api/knowledge/options
POST /api/knowledge/records
```

## Benchmark KPI e CSV

La cartella `eval/` contiene un runner esterno che misura KPI informativi, tecnici e operativi.

File principali:

| File | Descrizione |
| --- | --- |
| `eval/run_kpi_eval.py` | Script Python di benchmark |
| `eval/test_dataset.jsonl` | Dataset testuale da 130 record |
| `eval/outputs/results.csv` | CSV finale generato |

Il dataset di test contiene casi in più lingue, domini informativi diversi, feedback positivi e negativi, casi con ticket e casi senza escalation. Non contiene input audio o immagine.

Esecuzione con backend già avviato:

```bash
python eval/run_kpi_eval.py --base-url http://127.0.0.1:8000/api
```

Esecuzione da container backend:

```bash
docker exec talos-backend sh -lc "rm -rf /app/eval && mkdir -p /app/eval"
docker cp eval/run_kpi_eval.py talos-backend:/app/eval/run_kpi_eval.py
docker cp eval/test_dataset.jsonl talos-backend:/app/eval/test_dataset.jsonl
docker exec talos-backend python /app/eval/run_kpi_eval.py --base-url http://127.0.0.1:8000/api
docker cp talos-backend:/app/eval/outputs/results.csv eval/outputs/results.csv
```

## KPI Calcolati

| Macroarea | KPI | Formula |
| --- | --- | --- |
| Qualita informativa | Domain Accuracy | `domini_corretti / casi_con_dominio_atteso` |
| Qualita informativa | Recall@5 | `casi_con_almeno_un_doc_rilevante_in_top5 / casi_valutati` |
| Qualita informativa | Precision@5 | `media(|top5 ∩ rilevanti| / 5)` |
| Qualita informativa | MRR | `media(1 / rank_primo_documento_rilevante)` |
| Qualita informativa | Source Coverage Rate | `risposte_con_fonti / risposte_valide` |
| Performance tecnica | Average Latency | `somma_latenze / richieste` |
| Performance tecnica | p95 Latency | `95esimo percentile delle latenze` |
| Performance tecnica | Error Rate | `richieste_fallite / richieste_totali` |
| Impatto operativo | Escalation Rate | `conversazioni_con_ticket_o_escalation / conversazioni_valide` |
| Impatto operativo | Containment Rate | `1 - escalation_rate` |
| Impatto operativo | Feedback Score | `feedback_positivi / feedback_totali` |

## Sviluppo Frontend

```bash
cd frontend
npm install
npm run dev
```

Build:

```bash
npm run build
```

## Sviluppo Backend

Il backend è basato su FastAPI.

Responsabilita principali:

- validazione request/response;
- gestione conversazioni e sessioni;
- persistenza messaggi e feedback;
- trascrizione audio;
- OCR/vision per immagini;
- query planning;
- retrieval e reranking;
- generazione risposta finale;
- ticketing;
- autenticazione operatore;
- aggregazione KPI.

In Docker il backend comunica con:

- ChromaDB tramite `vector-db:8000`;
- Postgres tramite `database:5432`;
- Ollama tramite `llm:11434`, se avviato.

Riavvio backend:

```bash
docker compose restart backend
```

Log backend:

```bash
docker compose logs -f backend
```

## Knowledge Base e Retrieval

La knowledge base principale è `backend/data/kb.jsonl`.

Pipeline RAG:

1. ricezione messaggio utente;
2. analisi tramite query planner;
3. normalizzazione lingua/dominio;
4. retrieval multi-query su ChromaDB;
5. fallback globale se il filtro per dominio è povero;
6. merge e deduplicazione risultati;
7. reranking;
8. generazione finale vincolata ai contesti recuperati.

## Comandi di Verifica

Stato container:

```bash
docker compose ps
```

Health backend:

```bash
curl http://127.0.0.1:8000/health
```

KPI:

```bash
curl http://127.0.0.1:8000/api/kpis
```

Build frontend:

```bash
docker exec talos-frontend npm run build
```

Login operatore da UI:

```text
http://localhost:5173/operator
```

Gestione knowledge base da UI:

```text
http://localhost:5173/knowledge
```

## Troubleshooting

### Il frontend non si apre

```bash
docker compose logs -f frontend
docker compose up -d --build --force-recreate frontend
```

### Il backend non risponde

```bash
docker compose logs -f backend
docker compose ps
```

Verificare che `talos-database` sia `healthy` e che `talos-vector-db` sia avviato.

### Il microfono non funziona su iPhone

Usare l'URL HTTPS di Cloudflare, non `localhost` e non un IP locale:

```bash
docker compose logs -f cloudflared
```

### Voglio cancellare tutto

Solo se si vogliono eliminare anche volumi, database, cache, upload e indice:

```bash
docker compose down -v
```

## Limiti Noti

- Il sistema non fornisce risultati live, medagliere live, disponibilita biglietti personali o informazioni in tempo reale se non integrate da fonti esterne dedicate.
- Le risposte dipendono dalla copertura e qualità della knowledge base.
- Il tunnel gratuito `trycloudflare.com` è temporaneo.
- Accuratezza audio, OCR e vision dipende dal provider configurato.
- La configurazione è pensata per demo progettuale.
