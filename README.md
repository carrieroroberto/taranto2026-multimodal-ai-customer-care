# RAG Assistant

Full-stack RAG assistant with a FastAPI backend and a React/Vite frontend.

The project currently provides:

- JSONL knowledge-base validation and ingestion
- ChromaDB storage
- BAAI/bge-m3 embeddings
- RAG retrieval with vector search, lightweight query planning and compact reranking
- Qwen3 8B through Ollama for grounded answer generation
- FastAPI runtime endpoints for health checks and chat
- React/Vite/Tailwind frontend prototype for the customer-care chat flow

## Project Layout

```text
.
|-- backend/
|   |-- Dockerfile
|   |-- requirements.txt
|   |-- app/
|   |   |-- api/              # FastAPI route modules
|   |   |-- repositories/     # ChromaDB and KB access
|   |   |-- schemas/          # request/response DTOs
|   |   |-- services/
|   |   |   |-- errors.py
|   |   |   `-- rag_service.py
|   |   |-- config.py
|   |   |-- main.py
|   `-- data/
|       `-- kb.jsonl
|-- frontend/                 # React/Vite/Tailwind frontend prototype
|   |-- Dockerfile
|   |-- index.html
|   |-- package.json
|   |-- postcss.config.js
|   |-- src/
|   |   |-- components/
|   |   |-- pages/
|   |   |-- services/
|   |   |-- utils/
|   |   |-- App.jsx
|   |   |-- main.jsx
|   |   `-- styles.css
|   |-- tailwind.config.js
|   `-- package-lock.json
|-- docker-compose.yml
`-- .env.example
```

## Setup

Create a local environment file:

```bash
cp .env.example .env
```

Start the containers:

```bash
docker compose up --build -d
```

The root `docker-compose.yml` orchestrates separate backend and frontend images:

```text
backend    -> backend:dev, container backend
frontend   -> frontend:dev, container frontend
vector-db  -> ChromaDB, container vector-db
llm        -> Ollama, container llm
llm-init   -> one-shot model pull helper
```

FastAPI is available at:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

The Docker-started frontend is available at:

```text
http://127.0.0.1:5173
```

The `frontend` service runs Vite and waits for the backend health check before starting. For frontend-only development after the first install, use:

```bash
docker compose up frontend
```

The frontend calls the backend `/chat` endpoint on port `8000` by default. The UI intentionally exposes only the conversation surface: no API configuration, retrieval details, source panel, map panel or suggested questions are shown in the current prototype.

The first startup can take time because it downloads `BAAI/bge-m3`, pulls `qwen3:8b` and ingests the KB if Chroma is empty or was created with a different embedding model. Hugging Face and Ollama models are stored in Docker volumes, so code-only changes do not download them again.

During development the backend runs with Uvicorn reload and `./backend` mounted into the container. For code-only changes, do not rebuild the image: keep Compose running and wait for the backend process to reload, or run `docker compose restart backend` if needed. Use `docker compose build backend` only after changing `backend/requirements.txt`, `backend/Dockerfile` or dependency-related settings. Avoid `docker compose down -v` unless you intentionally want to delete Chroma, Hugging Face and Ollama cached volumes.

## Runtime API

Health:

```bash
curl http://127.0.0.1:8000/health
```

Chat:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"I biglietti per Taranto 2026 sono gia disponibili?\"}"
```

`/chat` is the only runtime conversation endpoint. It builds a small query plan, retrieves context from Chroma, calls Ollama with a guarded prompt and returns `answer`, `sources`, `maps`, `should_escalate`, `reason` and optional `ticket_draft`. The `answer` field is conversational text only; source URLs are returned as strings in `sources`, while `maps` is a single optional Google Maps URL.

The target LLM is `qwen3:8b`. On the standard GPU workstation profile, keep `USE_LLM_QUERY_PARSER=true`, `N_RESULTS=8`, `LLM_CONTEXT_WINDOW=4096` and `MAX_CONTEXT_CHARS=3200`: the parser first normalizes/classifies/expands the user query, then Chroma retrieves and reranks multiple records, then the answer layer generates the final grounded response. On a CPU-only development machine, use a smaller model and disable the LLM query parser only for quick local debugging.

For a GPU workstation, install NVIDIA Container Toolkit and verify that Ollama can see the GPU before the demo. The backend image uses CPU PyTorch for embeddings, while Ollama serves the LLM; Hugging Face models and Ollama models remain in Docker volumes, so code-only changes should be handled with backend reload/restart and should not redownload model or package caches.

## Local Run Without Docker

Chroma must be reachable at `CHROMA_HOST` and `CHROMA_PORT`.

PowerShell example:

```powershell
$env:PYTHONPATH="."
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Use the HTTP `/chat` endpoint for RAG testing.

## Configuration

Environment variables:

```text
COLLECTION_NAME
EMBEDDING_MODEL
N_RESULTS
INGEST_BATCH_SIZE
KB_PATH
CHROMA_HOST
CHROMA_PORT
AUTO_INGEST_ON_STARTUP
FORCE_REINGEST_ON_STARTUP
OLLAMA_BASE_URL
OLLAMA_MODEL
LLM_TIMEOUT_SECONDS
LLM_TEMPERATURE
LLM_NUM_PREDICT
LLM_CONTEXT_WINDOW
MAX_CONTEXT_CHARS
USE_LLM_QUERY_PARSER
QUERY_PARSER_TIMEOUT_SECONDS
QUERY_PARSER_NUM_PREDICT
```

Default local KB path is `backend/data/kb.jsonl`.
