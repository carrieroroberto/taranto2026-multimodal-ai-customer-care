Implementa solo il lato backend del sistema escalation ticket operatore.

Stack previsto:

* FastAPI
* PostgreSQL
* Docker Compose
* JWT per autenticazione operatori
* password hashing con bcrypt/passlib
* Tabelle consentite: operators, conversations, messages, tickets

Obiettivo generale:
Il backend deve supportare il flusso frontend in cui l’utente chatta normalmente, il sistema può richiedere escalation verso operatore, il frontend chiede l’email all’utente, poi crea un ticket tramite API. Deve inoltre esporre le API protette per dashboard operatore: login, lista ticket, dettaglio ticket, cambio stato ticket.

Non implementare invio email dal backend. Il frontend userà mailto.

Schema database richiesto:

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS operators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    domain TEXT NOT NULL DEFAULT 'general',
    summary TEXT NOT NULL,
    original_message TEXT,
    translated_message TEXT,
    language TEXT DEFAULT 'en',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

Endpoint chat:

1. POST /api/chat

Request indicativa:

```json
{
  "message": "string",
  "conversation_id": "uuid opzionale",
  "language": "it | en | fr | es | ar opzionale"
}
```

Comportamento:

* Se conversation_id non viene passato, crea una nuova conversazione.
* Salva il messaggio utente nella tabella messages.
* Genera la risposta del bot secondo la logica già esistente del chatbot.
* Salva la risposta bot nella tabella messages.
* Deve restituire sempre conversation_id.
* Deve restituire un campo booleano requires_escalation.
* requires_escalation deve essere true se:

  * il backend rileva bassa confidenza;
  * il messaggio utente richiede esplicitamente un operatore, assistenza umana, reclamo, problema non risolto, contatto diretto;
  * il chatbot non riesce a rispondere in modo affidabile.
* Il backend non deve chiedere direttamente l’email tramite endpoint ticket: deve solo segnalare al frontend che serve escalation.

Response:

```json
{
  "conversation_id": "uuid",
  "answer": "string",
  "requires_escalation": true,
  "language": "it",
  "sources": []
}
```

Il frontend, quando requires_escalation è true oppure l’utente chiede esplicitamente un operatore, chiederà l’email all’utente.

Endpoint creazione ticket:

2. POST /api/tickets

Request:

```json
{
  "conversation_id": "uuid",
  "user_email": "utente@example.com",
  "language": "it | en | fr | es | ar opzionale"
}
```

Comportamento:

* Valida user_email anche lato backend.
* Se email non valida, restituisce HTTP 422 o 400.
* Verifica che conversation_id esista.
* Recupera tutta la cronologia della conversazione ordinata per created_at.
* Individua l’ultimo messaggio utente prima dell’escalation.
* Genera i dati del ticket tramite funzione triage.
* Salva il ticket in PostgreSQL.
* Non invia email.
* Restituisce il ticket creato.

La funzione triage deve produrre almeno:

```python
{
    "priority": "low | medium | high | urgent",
    "domain": "transport | ticketing | venues | schedule | tourism | accessibility | complaint | technical | general",
    "summary": "breve sintesi del problema",
    "original_message": "ultimo messaggio utente rilevante in lingua originale",
    "translated_message": "traduzione inglese o italiana se utile, altrimenti null",
    "language": "lingua rilevata o passata dal frontend"
}
```

Response:

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "user_email": "utente@example.com",
  "status": "open",
  "priority": "medium",
  "domain": "ticketing",
  "summary": "L’utente chiede informazioni non risolte sui biglietti.",
  "original_message": "Vorrei parlare con un operatore per i biglietti.",
  "translated_message": "I would like to speak with an operator about tickets.",
  "language": "it",
  "created_at": "2026-05-23T12:00:00"
}
```

Autenticazione operatore:

3. POST /api/operator/login

Request:

```json
{
  "email": "operator@example.com",
  "password": "password"
}
```

Comportamento:

* Cerca l’operatore nella tabella operators.
* Verifica password tramite bcrypt/passlib.
* Se credenziali non valide, restituisce HTTP 401.
* Se valide, restituisce access_token JWT.
* Il token deve essere usato dal frontend nell’header:

```http
Authorization: Bearer <token>
```

Response:

```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "operator": {
    "id": "uuid",
    "email": "operator@example.com"
  }
}
```

API dashboard operatore protette da JWT:

4. GET /api/operator/tickets

Headers:

```http
Authorization: Bearer <token>
```

Comportamento:

* Restituisce lista ticket ordinata dal più recente al meno recente.
* Deve essere leggera, adatta al polling ogni 5 secondi.
* Deve includere solo i campi necessari alla card/lista dashboard.

Query params opzionali:

* status
* priority
* domain

Response:

```json
[
  {
    "id": "uuid",
    "status": "open",
    "priority": "high",
    "domain": "ticketing",
    "summary": "Problema sui biglietti per una gara.",
    "user_email": "utente@example.com",
    "created_at": "2026-05-23T12:00:00",
    "updated_at": "2026-05-23T12:00:00"
  }
]
```

5. GET /api/operator/tickets/{ticket_id}

Headers:

```http
Authorization: Bearer <token>
```

Comportamento:

* Restituisce dettaglio completo del ticket.
* Include summary, original_message, translated_message, user_email, status, priority, domain.
* Include conversazione completa in lingua originale.
* I messaggi devono essere ordinati cronologicamente.
* Non tradurre tutta la conversazione lato backend.
* Solo original_message e translated_message devono essere presenti come campi separati del ticket.

Response:

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "user_email": "utente@example.com",
  "status": "open",
  "priority": "high",
  "domain": "ticketing",
  "summary": "Problema sui biglietti per una gara.",
  "original_message": "Non riesco a capire se questo evento è gratuito o a pagamento.",
  "translated_message": "I cannot understand whether this event is free or paid.",
  "language": "it",
  "created_at": "2026-05-23T12:00:00",
  "updated_at": "2026-05-23T12:00:00",
  "conversation": [
    {
      "id": "uuid",
      "role": "user",
      "content": "Vorrei sapere se la finale è gratuita.",
      "created_at": "2026-05-23T11:58:00"
    },
    {
      "id": "uuid",
      "role": "bot",
      "content": "Non ho informazioni sufficienti per confermare il costo dell’evento.",
      "created_at": "2026-05-23T11:58:05"
    }
  ]
}
```

6. PATCH /api/operator/tickets/{ticket_id}/status

Headers:

```http
Authorization: Bearer <token>
```

Request:

```json
{
  "status": "open | in_progress | closed"
}
```

Comportamento:

* Valida lo status.
* Aggiorna status e updated_at.
* Restituisce il ticket aggiornato.
* Se ticket non esiste, HTTP 404.
* Se token mancante o invalido, HTTP 401.

Response:

```json
{
  "id": "uuid",
  "status": "in_progress",
  "updated_at": "2026-05-23T12:05:00"
}
```

Requisiti tecnici:

* Tutte le API devono essere sotto prefisso /api.
* CORS configurato per permettere il frontend locale.
* Usare variabili ambiente per:

  * DATABASE_URL
  * JWT_SECRET_KEY
  * JWT_ALGORITHM
  * ACCESS_TOKEN_EXPIRE_MINUTES
  * DEFAULT_OPERATOR_EMAIL opzionale
  * DEFAULT_OPERATOR_PASSWORD opzionale
* Prevedere eventualmente seed automatico di un operatore demo se le variabili DEFAULT_OPERATOR_EMAIL e DEFAULT_OPERATOR_PASSWORD sono presenti.
* Non salvare password in chiaro.
* Non loggare password o token.
* Non inviare email.
* Non implementare dashboard HTML lato backend: solo API JSON.

Docker Compose:

* Il backend deve funzionare dentro Docker Compose con PostgreSQL.
* Deve esporre la porta backend usata dal frontend.
* Deve attendere che PostgreSQL sia disponibile prima di avviare l’app o gestire retry di connessione.
* Le migration/schema init devono essere automatiche all’avvio oppure tramite script chiaro.

Criteri di accettazione:

* POST /api/chat crea o continua una conversazione.
* Ogni messaggio user/bot viene salvato nella tabella messages.
* POST /api/chat restituisce conversation_id.
* POST /api/chat può restituire requires_escalation=true.
* POST /api/tickets con email valida crea un ticket.
* POST /api/tickets con email non valida non crea ticket.
* POST /api/tickets con conversation_id inesistente restituisce errore.
* POST /api/operator/login restituisce token valido.
* Le API /api/operator/tickets sono accessibili solo con Authorization Bearer.
* GET /api/operator/tickets restituisce i ticket visibili entro massimo 5 secondi dal polling frontend.
* GET /api/operator/tickets/{ticket_id} restituisce dettaglio e conversazione completa.
* PATCH /api/operator/tickets/{ticket_id}/status aggiorna correttamente lo stato.
* Il backend non invia email: il pulsante “Rispondi” resta responsabilità del frontend tramite mailto.