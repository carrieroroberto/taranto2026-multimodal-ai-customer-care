# T.A.L.O.S. | Taranto 2026

## Chatbot AI Multimodale Di Customer Care Per I Giochi Del Mediterraneo

T.A.L.O.S. e' una web app full-stack per il customer care dei Giochi del Mediterraneo Taranto 2026. Il sistema integra una chat multilingua, una pipeline RAG basata su knowledge base, una dashboard operatore per la gestione dei ticket e un modulo di benchmarking KPI esportabile in CSV.

L'obiettivo del progetto e' fornire risposte utili, brevi e fondate sulle fonti disponibili nella knowledge base, evitando risposte inventate su date, sedi, biglietti, risultati live o informazioni non presenti nei dati recuperati.

## Stato Della Consegna

La versione finale include:

- frontend React/Vite installabile come PWA;
- backend FastAPI con API testuali, audio e immagine;
- ChromaDB come vector database;
- Postgres per conversazioni, messaggi, feedback, operatori, ticket e KPI;
- pipeline RAG con query planning, retrieval, reranking e generazione finale;
- supporto LLM locale tramite Ollama;
- supporto Groq API per uso senza GPU locale;
- dashboard operatore protetta da login su `/operator`;
- ticketing da feedback negativo con riuso sicuro dell'email confermata;
- benchmark KPI in `eval/` con dataset testuale da 130 record;
- export unico in `eval/outputs/results.csv`;
- container, network e volumi rinominati con prefisso `talos`.

## Funzionalita Principali

- Chat testuale multilingua in italiano, inglese, spagnolo, francese e arabo.
- Risposte grounded sulla knowledge base Taranto 2026.
- Rilevamento/gestione lingua e risposta nella lingua dell'utente.
- Query planning LLM per dominio, intento e query di retrieval.
- Retrieval multi-query su ChromaDB con fallback globale.
- Reranking leggero dei documenti recuperati.
- Fonti mostrate come favicon cliccabili quando disponibili.
- Input multimodale: testo, testo + immagine, solo audio.
- Registrazione audio con playback e waveform.
- Upload immagine da pulsante, drag and drop e copia/incolla.
- Anteprima immagine e lightbox.
- Feedback utente sui messaggi del bot.
- Apertura ticket verso operatore umano su feedback negativo.
- Dashboard operatore con login, lista ticket, filtri, dettaglio conversazione, traduzione, bozza email e chiusura ticket.
- Tema chiaro/scuro e preferenze salvate in `localStorage`.
- PWA installabile e testabile anche da mobile tramite tunnel HTTPS Cloudflare.

## Architettura

```text
Utente / Operatore
      |
      v
Frontend React/Vite
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
Risposta grounded + fonti / ticket operatore / KPI
```

Servizi Docker:

| Servizio | Container | Porta host | Ruolo |
| --- | --- | --- | --- |
| `frontend` | `talos-frontend` | `5173` | App React/Vite |
| `backend` | `talos-backend` | `8000` | API FastAPI |
| `vector-db` | `talos-vector-db` | `8001` | ChromaDB |
| `database` | `talos-database` | `5433` | Postgres |
| `pgadmin` | `talos-pgadmin` | `5050` | UI database |
| `llm` | `talos-llm` | `11434` | Ollama locale |
| `llm-init` | `talos-llm-init` | - | Pull modelli Ollama |
| `cloudflared` | `talos-cloudflared` | - | Tunnel HTTPS temporaneo |

## Struttura Repository

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # Route FastAPI
│   │   ├── repositories/     # Postgres e ChromaDB
│   │   ├── schemas/          # DTO request/response
│   │   ├── services/         # RAG, LLM, multimodale, ticket
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
│       └── results.csv       # Output CSV generato/sovrascritto
├── frontend/
│   ├── public/               # Manifest PWA, icone, asset pubblici
│   ├── src/
│   │   ├── components/
│   │   ├── pages/            # ChatPage e OperatorDashboardPage
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
- Groq API key per usare la modalita' senza GPU locale.
- GPU NVIDIA e runtime Docker NVIDIA solo per la modalita' completa con Ollama locale.
- Spazio disco sufficiente per modelli, cache embedding, volumi Postgres e ChromaDB.

Il primo avvio puo' richiedere alcuni minuti per scaricare immagini Docker, inizializzare i volumi e indicizzare la knowledge base.

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
| `VITE_PROXY_TARGET` | Target proxy Vite verso backend |

Non inserire IP o URL backend assoluti nel frontend. Le chiamate React devono usare path relativi come `/api/chat`.

## Avvio Rapido

Su Windows:

```bat
run.bat lite
```

La modalita' `lite` e' consigliata per demo e consegna se e' configurata `GROQ_API_KEY`. Avvia frontend, backend, Postgres, pgAdmin, ChromaDB e Cloudflare, senza avviare Ollama locale.

Per la modalita' completa con Ollama:

```bat
run.bat full
```

Con Docker Compose:

```bash
docker compose up -d --build
```

Link locali:

- Chat: <http://localhost:5173>
- Dashboard operatore: <http://localhost:5173/operator>
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

## Accesso Mobile E PWA

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

Le API sono esposte anche con prefisso `/api`, usato dal frontend tramite proxy Vite.

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

Il feedback negativo puo' attivare il flusso di ticket verso operatore.

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

Operatore demo:

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

## KPI Database

```http
GET /api/kpis
```

La route restituisce metriche cumulative lette dal database:

- conversazioni totali;
- messaggi totali;
- messaggi utente;
- messaggi bot;
- ticket totali;
- ticket aperti;
- ticket chiusi;
- feedback positivi;
- feedback negativi;
- messaggi valutati;
- satisfaction rate.

Questa route descrive lo stato del database. Per test riproducibili e risultati da relazione usare il runner in `eval/`.

## Benchmark KPI E CSV

La cartella `eval/` contiene un runner esterno che misura KPI informativi, tecnici e operativi senza modificare chatbot e dashboard.

File principali:

| File | Descrizione |
| --- | --- |
| `eval/run_kpi_eval.py` | Script Python di benchmark |
| `eval/test_dataset.jsonl` | Dataset testuale da 130 record |
| `eval/outputs/results.csv` | CSV finale generato/sovrascritto |

Il dataset contiene casi in piu' lingue, domini informativi diversi, feedback positivi e negativi, casi con ticket e casi senza escalation. Non contiene input audio o immagine; per questo il benchmark finale non include un KPI ASR/OCR.

Esecuzione con backend gia' avviato:

```bash
python eval/run_kpi_eval.py --base-url http://127.0.0.1:8000/api
```

Validazione dataset:

```bash
python eval/run_kpi_eval.py --validate-only
```

Esecuzione da container backend:

```bash
docker exec talos-backend sh -lc "rm -rf /app/eval && mkdir -p /app/eval"
docker cp eval/run_kpi_eval.py talos-backend:/app/eval/run_kpi_eval.py
docker cp eval/test_dataset.jsonl talos-backend:/app/eval/test_dataset.jsonl
docker exec talos-backend python /app/eval/run_kpi_eval.py --base-url http://127.0.0.1:8000/api
docker cp talos-backend:/app/eval/outputs/results.csv eval/outputs/results.csv
```

Opzioni utili:

```bash
# ripete ogni domanda per stabilizzare la latenza
python eval/run_kpi_eval.py --repeat 3

# calcola solo retrieval, senza chiamare il chatbot
python eval/run_kpi_eval.py --skip-chat --skip-kpi-snapshot

# calcola solo chat/API, senza retrieval
python eval/run_kpi_eval.py --skip-retrieval

# scrive feedback sui messaggi generati
python eval/run_kpi_eval.py --post-feedback

# scrive feedback negativi e apre ticket sui casi marcati open_ticket=true
python eval/run_kpi_eval.py --post-feedback --post-tickets
```

Formato output:

```csv
kpi,description,value,unit
Domain Accuracy,Capacita di classificare correttamente il dominio della domanda,0.9262,percent
Recall@5,Almeno un documento corretto tra i primi 5 risultati,0.7951,ratio
```

Il CSV contiene solo quattro colonne:

- `kpi`;
- `description`;
- `value`;
- `unit`.

Per una relazione finale riproducibile e' consigliato usare un database dedicato alla run o ripartire da uno stato noto.

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

Regole importanti:

- usare sempre `/api/...` come base chiamate;
- non inserire `http://localhost:8000` nel codice React;
- gli asset importati dai componenti stanno in `frontend/src/assets`;
- manifest PWA e icone pubbliche stanno in `frontend/public`.

## Sviluppo Backend

Il backend e' basato su FastAPI.

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

## Knowledge Base E Retrieval

La knowledge base principale e' `backend/data/kb.jsonl`.

Pipeline RAG:

1. ricezione messaggio utente;
2. analisi tramite query planner;
3. normalizzazione lingua/dominio;
4. retrieval multi-query su ChromaDB;
5. fallback globale se il filtro per dominio e' povero;
6. merge e deduplicazione risultati;
7. reranking;
8. generazione finale vincolata ai contesti recuperati.

Alias, varianti e metadati informativi dovrebbero stare nella knowledge base, non in lunghi dizionari hardcoded nel codice.

## Comandi Di Verifica

Stato container:

```bash
docker compose ps
```

Health backend:

```bash
curl http://127.0.0.1:8000/health
```

KPI database:

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

### La knowledge base non sembra aggiornata

Impostare temporaneamente:

```env
FORCE_REINGEST_ON_STARTUP=true
```

Poi riavviare il backend:

```bash
docker compose restart backend
```

Al termine, riportare `FORCE_REINGEST_ON_STARTUP=false`.

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
- Le risposte dipendono dalla copertura e qualita della knowledge base.
- Il tunnel gratuito `trycloudflare.com` e' temporaneo.
- Accuratezza audio, OCR e vision dipende dal provider configurato.
- La configurazione e' pensata per sviluppo, demo e consegna progettuale; per produzione servono hardening sicurezza, gestione segreti, rate limit, logging strutturato, monitoraggio e backup.
