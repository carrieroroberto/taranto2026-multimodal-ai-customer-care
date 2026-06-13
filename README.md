# T.A.L.O.S. | Taranto 2026 Live Operator Support

## ChatBot AI Multimodale di Customer-Care per i Giochi del Mediterraneo

T.A.L.O.S. è un assistente customer-care multimodale per i Giochi del Mediterraneo di Taranto 2026. Il progetto combina una UI React installabile come PWA, un backend FastAPI e una pipeline RAG basata su ChromaDB, embedding semantici e LLM locale tramite Ollama.

L'obiettivo è fornire risposte utili, brevi e fondate sulla knowledge base del progetto, evitando di inventare date, prezzi, sedi, risultati live o informazioni non presenti nei dati recuperati.

## Stato Attuale

Il progetto è una web app full-stack containerizzata con Docker Compose.

- Frontend React/Vite con Tailwind CSS.
- Backend FastAPI con endpoint testuali, audio e multimodali.
- ChromaDB come vector database.
- Postgres per conversazioni, messaggi, ticket e KPI.
- Ollama come servizio LLM locale.
- Groq API supportata per usare LLM e multimodale senza GPU locale.
- Dashboard operatore protetta da login su `/operator`, con lista ticket, dettaglio conversazione, traduzione, bozza email e chiusura ticket.
- Runner benchmark KPI in `eval/` per esportare metriche tecniche, informative e operative in `results.csv`.
- Modello LLM configurato di default: `qwen3:8b`.
- Modello embedding configurato di default: `BAAI/bge-m3`.
- Tunnel HTTPS temporaneo con Cloudflare per test da iPhone, PWA e microfono.
- UI multilingua: italiano, inglese, spagnolo, francese e arabo.
- Tema chiaro/scuro con lettura automatica del tema di sistema e preferenza salvata in `localStorage`.

## Funzionalità

- Chat testuale con risposte generate dal backend.
- Risposte grounded: il modello deve usare solo i contesti recuperati dalla knowledge base.
- Query planning LLM per normalizzare la richiesta, gestire lingua, dominio e query di retrieval.
- Retrieval multi-query su ChromaDB con fallback globale quando il filtro di dominio recupera pochi risultati.
- Reranking leggero dei documenti recuperati.
- Supporto multilingua della UI e risposta nella lingua selezionata/originaria.
- Input multimodale:
  - solo testo;
  - testo + immagine;
  - solo audio.
- Registrazione audio con durata, playback e waveform.
- Upload immagine da pulsante, drag and drop da tutta la finestra e copia/incolla.
- Anteprima immagine prima dell'invio e lightbox per ingrandire immagini inviate o in preview.
- PWA installabile su iPhone e Android.
- Fonti mostrate come favicon cliccabili dopo le risposte del bot, quando disponibili.
- Domande suggerite tradotte in base alla lingua della UI.
- Countdown nell'header.
- Feedback utente sui messaggi bot e apertura ticket verso operatore umano.
- Dashboard operatore con filtri, ordinamento, polling automatico nuovi ticket e modal dettaglio.
- Export benchmark KPI in `eval/outputs/results.csv` tramite un singolo CSV strutturato.

## Architettura

```text
Utente
  |
  v
Frontend React/Vite
  |
  |  /api/*
  v
Backend FastAPI
  |
  +--> Query Planner LLM
  |
  +--> ChromaDB retrieval + reranking
  |
  +--> Final Answer LLM
  |
  v
Risposta grounded + fonti
```

Servizi Docker principali:

| Servizio | Ruolo |
| --- | --- |
| `frontend` | App React/Vite sulla porta `5173` |
| `backend` | API FastAPI sulla porta `8000` |
| `vector-db` | ChromaDB sulla porta `8001` |
| `database` | Postgres sulla porta host `5433` |
| `pgadmin` | UI grafica per Postgres sulla porta `5050` |
| `llm` | Ollama per modelli locali |
| `llm-init` | Pull automatico dei modelli locali configurati |
| `cloudflared` | Tunnel HTTPS temporaneo `trycloudflare.com` |

## Struttura Del Repository

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # Route FastAPI
│   │   ├── repositories/     # Postgres e ChromaDB
│   │   ├── schemas/          # Schemi request/response
│   │   ├── services/         # RAG, LLM, OCR, ASR, visione, ticket
│   │   ├── config.py
│   │   └── main.py
│   ├── data/
│   │   └── kb.jsonl          # Knowledge base indicizzata
│   ├── db/
│   │   └── init.sql          # Schema iniziale Postgres
│   ├── requirements.txt
│   └── Dockerfile
├── eval/
│   ├── run_kpi_eval.py      # Runner benchmark KPI
│   └── test_cases.jsonl     # Dataset ground truth per valutazione
├── frontend/
│   ├── public/
│   │   ├── icons/            # Icone PWA e fallback favicon fonti
│   │   └── manifest.json
│   ├── src/
│   │   ├── assets/           # Asset importati da React
│   │   ├── components/       # Componenti UI
│   │   ├── pages/            # Chat e dashboard operatore
│   │   ├── services/         # Client API frontend
│   │   ├── utils/            # Utility frontend
│   │   ├── i18n.js
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Requisiti

- Docker e Docker Compose.
- Una GPU NVIDIA compatibile e runtime Docker NVIDIA se si usa il servizio Ollama locale con accelerazione GPU.
- Spazio disco sufficiente per modelli LLM, embedding e volumi Docker.

Il primo avvio puo' richiedere tempo per scaricare i modelli e inizializzare i dati.

## Configurazione

Copiare il file di esempio:

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
| `COLLECTION_NAME` | Nome collezione ChromaDB |
| `POSTGRES_DB` | Nome database Postgres |
| `POSTGRES_USER` | Utente Postgres |
| `POSTGRES_PASSWORD` | Password Postgres di sviluppo |
| `POSTGRES_HOST_PORT` | Porta host per Postgres, di default `5433` |
| `DATABASE_URL` | URL Postgres per esecuzione backend fuori Docker |
| `PGADMIN_DEFAULT_EMAIL` | Email di login pgAdmin |
| `PGADMIN_DEFAULT_PASSWORD` | Password di login pgAdmin |
| `PGADMIN_HOST_PORT` | Porta host pgAdmin, di default `5050` |
| `DEFAULT_OPERATOR_EMAIL` | Operatore demo creato automaticamente |
| `DEFAULT_OPERATOR_PASSWORD` | Password demo hashata nel DB |
| `EMBEDDING_MODEL` | Modello embedding |
| `N_RESULTS` | Numero base di risultati recuperati |
| `OLLAMA_MODEL` | Modello usato dal backend |
| `QUERY_PARSER_MODEL` | Modello usato dal query planner |
| `USE_LLM_QUERY_PARSER` | Abilita il planner LLM |
| `AI_DISABLED` | Disattiva i modelli AI. Per usare Groq/API con RAG e multimodale deve restare `false` |
| `GROQ_API_KEY` | Chiave Groq per query planner, generazione testuale, trascrizione e vision via API |
| `GROQ_MODEL` | Modello Groq testuale |
| `GROQ_VISION_MODEL` | Modello Groq usato per descrivere immagini |
| `GROQ_TRANSCRIPTION_MODEL` | Modello Groq usato per trascrivere audio |
| `LLM_FALLBACK_TIMEOUT_SECONDS` | `0` forza Groq diretto; un valore maggiore prova prima Ollama e poi Groq |
| `MULTIMODAL_PROVIDER` | `groq`, `local` o `auto` per audio/vision |
| `VISION_MODEL` | Modello vision locale Ollama, di default `moondream` |
| `VITE_API_BASE_URL` | Base API del frontend, di default `/api` |
| `VITE_PROXY_TARGET` | Target proxy Vite verso il backend |

Non inserire IP locali hardcoded nel frontend. Le chiamate devono passare da path relativi come `/api/chat`.

## Avvio Con Docker

Il progetto Docker Compose usa il nome progetto `tarai`, quindi rete e risorse Compose vengono isolate sotto quel nome.

Su Windows si puo' usare lo script rapido:

```bat
run.bat
```

Di default equivale alla modalita' completa:

```bat
run.bat full
```

Per usare Groq API per testo e multimodalita', senza Ollama locale:

```bat
run.bat lite
```

La modalita' `lite` avvia frontend, backend, Postgres, pgAdmin, ChromaDB e tunnel Cloudflare, ma non avvia `llm` e `llm-init`. Imposta `AI_DISABLED=false`, `MULTIMODAL_PROVIDER=groq` e `LLM_FALLBACK_TIMEOUT_SECONDS=0`, quindi usa Groq per query planner, risposta finale, trascrizione audio e vision immagini quando `GROQ_API_KEY` e' configurata.

Per la versione completa con modelli AI locali:

```bat
run.bat full
```

La modalita' `full` avvia anche Ollama con accelerazione NVIDIA dal compose principale, verifica/scarica il modello testuale e il modello vision configurati e usa i modelli locali come percorso principale. Groq resta solo fallback del testo in base a `LLM_FALLBACK_TIMEOUT_SECONDS`, impostato dallo script a `40` secondi.

Il progetto mantiene un solo `docker-compose.yml`. In `lite` il servizio `llm` non viene avviato, quindi il requisito GPU non viene coinvolto.

Dalla root del progetto:

```bash
docker compose up --build
```

Aprire da PC:

- Frontend: <http://localhost:5173>
- Dashboard operatore: <http://localhost:5173/operator>
- Backend API docs: <http://localhost:8000/docs>
- ChromaDB: <http://localhost:8001>
- Postgres: `localhost:5433`
- pgAdmin: <http://localhost:5050>

Accesso pgAdmin di sviluppo:

- Email: `admin@tarai.com`
- Password: `ChatbotTaranto2026!`

Per collegare il database in pgAdmin:

- Host name/address: `database`
- Port: `5432`
- Maintenance database: `tarai`
- Username: `tarai`
- Password: `ChatbotTaranto2026!`

Se si accede a Postgres da strumenti installati sul PC, usare invece host `localhost` e porta `5433`.

Log utili:

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f cloudflared
```

Per fermare i servizi:

```bash
docker compose down
```

Evitare `docker compose down -v` se non si vogliono cancellare volumi, modelli e dati indicizzati.

## Accesso Da iPhone, Android E PWA

Safari iOS richiede HTTPS per usare il microfono e per una PWA in modalità standalone. Per questo il progetto include `cloudflared`.

Avviare tutto:

```bash
docker compose up --build
```

Poi leggere l'URL HTTPS temporaneo dai log:

```bash
docker compose logs -f cloudflared
```

Cercare un URL simile a:

```text
https://nome-casuale.trycloudflare.com
```

Da iPhone:

1. Aprire quell'URL in Safari.
2. Verificare chat e microfono.
3. Per installare la PWA: Condividi -> Aggiungi alla schermata Home.
4. Aprire T.A.L.O.S. dall'icona installata.

Il tunnel gratuito è temporaneo: a ogni riavvio puo' cambiare URL.

## API Principali

Le API sono esposte dal backend e raggiunte dal frontend tramite proxy `/api`.

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
  "message": "Quando iniziano i Giochi del Mediterraneo di Taranto 2026?",
  "session_id": "sessione-demo",
  "language": "it"
}
```

La risposta include anche gli identificativi persistiti:

- `conversation_id`
- `user_message_id`
- `bot_message_id`

Questi ID collegano ogni turno della chat alle tabelle `conversations` e `messages`.
Ogni riga in `messages` contiene anche `type`, valorizzato con `text`, `image` o `audio`.

### Conversazioni

```http
POST /api/conversations
GET /api/conversations/{session_id}/messages
```

Il frontend crea o recupera una conversazione usando il `session_id` salvato in `localStorage`. Alla riapertura del browser o della PWA, la stessa sessione viene riutilizzata e i messaggi precedenti vengono ricaricati.

### Chat Audio

```http
POST /api/chat/audio
Content-Type: multipart/form-data
```

Campi:

- `file`: file audio registrato.
- `session_id`: opzionale.
- `language`: opzionale.

### Chat Multimodale

```http
POST /api/chat/multimodal
Content-Type: multipart/form-data
```

Campi principali:

- `message`: testo dell'utente.
- `file`: file immagine o audio.
- `session_id`: opzionale.
- `language`: opzionale.

Il frontend applica già le combinazioni consentite:

- testo;
- testo + immagine;
- audio.

### Ticket

```http
POST /api/tickets
Content-Type: application/json
```

Il ticket viene salvato in Postgres nella tabella `tickets` e collegato alla conversazione.

Operatore demo creato automaticamente:

- Email: `operatore@tarai.it`
- Password: `OperatoreTaranto2026!`

La password viene salvata nella tabella `operators` come hash generato da `pgcrypto`; non viene salvata in chiaro. Non e' prevista registrazione pubblica di nuovi operatori.

### Dashboard Operatore

La dashboard e' disponibile nel frontend al path:

```text
/operator
```

Funzioni principali:

- login/logout operatore con JWT;
- lista ticket con filtri per stato, ordinamento e modalita' card/lista;
- polling automatico dei nuovi ticket;
- dettaglio ticket con conversazione associata e media allegati;
- traduzione della conversazione;
- generazione bozza email di risposta;
- chiusura ticket da modal dettaglio.

Route principali usate dalla dashboard:

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

### KPI

```http
GET /api/kpis
```

Restituisce conteggi aggregati da `conversations`, `messages` e `tickets`, inclusi ticket per stato e feedback positivo/negativo. La route espone metriche operative cumulative del database; per benchmark riproducibili usare anche il runner `eval/run_kpi_eval.py`.

### Feedback

```http
POST /api/feedback
```

Il feedback aggiorna `messages.satisfaction` sul messaggio bot selezionato: `true` per pollice su, `false` per pollice giu'. Il valore iniziale nel database resta `NULL`.
Per vincolo DB, `satisfaction` puo' essere valorizzato solo su righe `role = 'bot'`; sui messaggi utente resta sempre `NULL`.

## Benchmark KPI E Export CSV

La cartella `eval/` contiene una soluzione esterna per misurare KPI tecnici,
informativi e operativi senza modificare il funzionamento del chatbot o della
dashboard operatore.

Il runner usa due fonti:

- API HTTP esistenti: `/api/chat`, `/api/messages/{message_id}/feedback`,
  `/api/tickets`, `/api/kpis`;
- import read-only dei servizi backend per le metriche retrieval top-5:
  `build_query_plan()` e `retrieve_context()`.

Output predefinito:

```text
eval/outputs/results.csv
```

`results.csv` viene sovrascritto a ogni run e contiene solo le colonne
`kpi`, `description`, `value` e `unit`.
`eval/outputs/` e' ignorata da Git per non versionare risultati di benchmark locali.

Uso rapido, con backend, database e ChromaDB gia' avviati:

```bash
python eval/run_kpi_eval.py --base-url http://127.0.0.1:8000/api
```

Se si esegue da host e mancano dipendenze Python del backend, usare il container:

```bash
docker exec tarai-backend sh -lc "rm -rf /app/eval && mkdir -p /app/eval"
docker cp eval/run_kpi_eval.py tarai-backend:/app/eval/run_kpi_eval.py
docker cp eval/test_cases.jsonl tarai-backend:/app/eval/test_cases.jsonl
docker exec tarai-backend python /app/eval/run_kpi_eval.py --base-url http://127.0.0.1:8000/api
docker cp tarai-backend:/app/eval/outputs/results.csv eval/outputs/results.csv
```

Comandi utili:

```bash
# valida solo il dataset
python eval/run_kpi_eval.py --validate-only

# solo metriche HTTP e KPI database
python eval/run_kpi_eval.py --skip-retrieval

# solo metriche retrieval, senza chiamare il chatbot
python eval/run_kpi_eval.py --skip-chat --skip-kpi-snapshot

# ripete ogni domanda 3 volte per stabilizzare la latenza
python eval/run_kpi_eval.py --repeat 3

# scrive feedback di test sui messaggi bot generati
python eval/run_kpi_eval.py --post-feedback

# scrive feedback negativi e apre ticket sui casi marcati open_ticket=true
python eval/run_kpi_eval.py --post-feedback --post-tickets
```

Per una relazione finale riproducibile, usare un database pulito o un database
dedicato alla run di benchmark.

Il dataset `eval/test_cases.jsonl` contiene una domanda per riga:

```json
{
  "id": "venue_canoe_001",
  "message": "Dove si svolge la canoa kayak a Taranto 2026?",
  "language": "it",
  "expected_domain": "venue",
  "relevant_doc_ids": ["sport_canoa_kayak"],
  "expected_escalation": false,
  "feedback": true
}
```

Il dataset attuale e' testuale. Per simulare escalation operative senza
alterare chatbot o dashboard, alcuni casi usano feedback negativo e
`open_ticket: true`; con `--post-tickets` il runner apre un ticket tramite la
route pubblica `/api/tickets`.

```json
{
  "id": "edge_payment_problem_129",
  "modality": "text",
  "message": "Il pagamento online del biglietto non funziona...",
  "language": "it",
  "expected_domain": "ticketing",
  "relevant_doc_ids": ["ticketing_general_taranto_2026"],
  "feedback": false,
  "open_ticket": true,
  "user_email": "kpi.eval+payment@example.com"
}
```

KPI calcolati:

| Macroarea | KPI | Fonte |
| --- | --- | --- |
| Qualita informativa | Domain Accuracy | Retrieval |
| Qualita informativa | Recall@5 | Retrieval |
| Qualita informativa | Precision@5 | Retrieval |
| Qualita informativa | MRR | Retrieval |
| Qualita informativa | Source Coverage Rate | API/Retrieval |
| Performance tecnica | Average Latency | Backend/API |
| Performance tecnica | p95 Latency | Backend/API |
| Performance tecnica | Error Rate | Backend/API |
| Impatto operativo | Containment Rate | API/Database |
| Impatto operativo | Escalation Rate | API/Database |
| Impatto operativo | Feedback Score | Database |

## Sviluppo Frontend

Il frontend è un progetto React/Vite.

```bash
cd frontend
npm install
npm run dev
```

La configurazione Vite espone l'app su `0.0.0.0:5173` e inoltra `/api` al backend.

Note di sviluppo:

- Non usare URL backend assoluti come `http://localhost:8000` nel codice React.
- Usare sempre `/api/...`.
- Gli asset importati dai componenti stanno in `frontend/src/assets`.
- I file statici pubblici, manifest PWA e icone installabili stanno in `frontend/public`.

## Sviluppo Backend

Il backend è basato su FastAPI.

Responsabilità principali:

- validazione request/response;
- gestione sessione;
- trascrizione audio;
- analisi immagine/OCR quando disponibile;
- query planning LLM;
- retrieval e reranking;
- generazione della risposta finale;
- ticketing e feedback utente;
- autenticazione operatore e API dashboard;
- aggregazione KPI e metriche operative.

In Docker il backend comunica con:

- ChromaDB tramite `vector-db:8000`;
- Postgres tramite `database:5432`;
- Ollama tramite `llm:11434`.

Per modifiche backend durante lo sviluppo puo' essere necessario riavviare il container:

```bash
docker compose restart backend
```

## Knowledge Base E Retrieval

La knowledge base viene indicizzata in ChromaDB e interrogata dal RAG service.

La pipeline desiderata è:

1. analisi della query utente tramite LLM planner;
2. normalizzazione/traduzione semantica della query per il retrieval;
3. retrieval multi-query su ChromaDB;
4. fallback globale se il filtro di dominio recupera pochi risultati;
5. merge, deduplicazione e reranking;
6. generazione finale usando solo i contesti recuperati.

La logica Python non dovrebbe dipendere da lunghi dizionari hardcoded di sport, città, sinonimi o keyword. Alias, varianti e metadati dovrebbero stare nella knowledge base.

## Convenzioni Importanti

- Il frontend deve usare solo path relativi `/api`.
- Il backend deve evitare risposte inventate se il dato non è nel contesto.
- Le fonti devono essere mostrate solo se il backend le restituisce.
- Il messaggio iniziale della UI non mostra fonti.
- I messaggi di errore non mostrano fonti.
- Il microfono su iOS va testato da HTTPS, quindi tramite URL Cloudflare.
- Le preferenze UI di tema e lingua vengono salvate in `localStorage`.

## Troubleshooting

### Il frontend è bianco

Controllare i log:

```bash
docker compose logs -f frontend
```

Poi ricostruire:

```bash
docker compose up --build frontend
```

### Il backend non risponde

Controllare:

```bash
docker compose logs -f backend
docker compose ps
```

Verificare anche che ChromaDB e Ollama siano avviati.

### Il modello non è pronto

Al primo avvio `llm-init` scarica il modello configurato. Finchè il modello non è disponibile, alcune risposte possono fallire.

```bash
docker compose logs -f llm-init
docker compose logs -f llm
```

### Il microfono non funziona su iPhone

Usare l'URL HTTPS generato da `cloudflared`, non `http://localhost` e non un IP locale.

```bash
docker compose logs -f cloudflared
```

### Voglio pulire tutto

Solo se si vuole cancellare anche dati e cache:

```bash
docker compose down -v
```

Questa operazione rimuove i volumi Docker e puo' richiedere un nuovo download/ingestion.

## Limiti Noti

- Il sistema non fornisce risultati live, medagliere live, parcheggi in tempo reale o disponibilità biglietti personali se non integrati con fonti esterne dedicate.
- Le risposte dipendono dalla qualità e copertura della knowledge base indicizzata.
- Il tunnel `trycloudflare.com` gratuito è temporaneo.
- La pipeline multimodale prepara audio e immagini per il backend, ma accuratezza ASR/OCR/vision dipende dai moduli configurati.
- Il progetto non va considerato pronto per produzione senza hardening di sicurezza, autenticazione, rate limit, logging strutturato e monitoraggio.
