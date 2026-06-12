import logging
import psycopg
from psycopg.rows import dict_row
from typing import Any, Iterable
from datetime import datetime
import time

from backend.app.config import settings


logger = logging.getLogger(__name__)


SCHEMA_STATEMENTS = (
    'CREATE EXTENSION IF NOT EXISTS "pgcrypto";',
    """
    CREATE TABLE IF NOT EXISTS operators (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL DEFAULT 'Operatore',
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome')
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome')
    );
    """,
    "ALTER TABLE conversations DROP COLUMN IF EXISTS ai_summary;",
    """
    CREATE TABLE IF NOT EXISTS messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
        type TEXT NOT NULL DEFAULT 'text' CHECK (type IN ('text', 'image', 'audio')),
        content TEXT DEFAULT NULL,
        caption TEXT DEFAULT NULL,
        media_url TEXT DEFAULT NULL,
        sources JSONB DEFAULT NULL,
        satisfaction BOOLEAN DEFAULT NULL,
        created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome')
    );
    """,
    "ALTER TABLE operators ALTER COLUMN created_at SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome');",
    "ALTER TABLE operators ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT 'Operatore';",
    "ALTER TABLE conversations ALTER COLUMN created_at SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome');",
    "ALTER TABLE messages ALTER COLUMN created_at SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome');",
    "ALTER TABLE messages ALTER COLUMN content DROP NOT NULL;",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS caption TEXT DEFAULT NULL;",
    """
    ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS type TEXT NOT NULL DEFAULT 'text';
    """,
    """
    ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS sources JSONB DEFAULT NULL;
    """,
    "ALTER TABLE messages ALTER COLUMN sources DROP NOT NULL;",
    "ALTER TABLE messages ALTER COLUMN sources DROP DEFAULT;",
    "UPDATE messages SET sources = NULL WHERE role = 'user';",
    """
    ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS media_url TEXT DEFAULT NULL;
    """,
    """
    UPDATE messages
    SET media_url = substring(content from '\\[IMAGE_URL:([^\\]]+)\\]')
    WHERE media_url IS NULL
      AND type = 'image'
      AND content LIKE '[IMAGE_URL:%';
    """,
    """
    UPDATE messages
    SET media_url = substring(content from '\\[AUDIO_URL:([^\\]]+)\\]')
    WHERE media_url IS NULL
      AND type = 'audio'
      AND content LIKE '[AUDIO_URL:%';
    """,
    """
    UPDATE messages
    SET content = NULL
    WHERE type IN ('image', 'audio')
      AND content IS NOT NULL;
    """,
    """
    UPDATE messages
    SET type = 'text'
    WHERE type IS NULL OR type NOT IN ('text', 'image', 'audio');
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'messages_type_valid'
        ) THEN
            ALTER TABLE messages
            ADD CONSTRAINT messages_type_valid
            CHECK (type IN ('text', 'image', 'audio'));
        END IF;
    END $$;
    """,
    """
    UPDATE messages
    SET satisfaction = NULL
    WHERE role = 'user' AND satisfaction IS NOT NULL;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'messages_user_satisfaction_null'
        ) THEN
            ALTER TABLE messages
            ADD CONSTRAINT messages_user_satisfaction_null
            CHECK (role = 'bot' OR satisfaction IS NULL);
        END IF;
    END $$;
    """,
    """
    CREATE TABLE IF NOT EXISTS tickets (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        escalated_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'aperto',
        priority TEXT,
        domain TEXT,
        user_email TEXT NOT NULL,
        summary TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome')
    );
    """,
    "ALTER TABLE tickets ALTER COLUMN created_at SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome');",
    "ALTER TABLE tickets DROP COLUMN IF EXISTS updated_at;",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS escalated_message_id UUID REFERENCES messages(id) ON DELETE SET NULL;",
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'tickets'
              AND column_name = 'feedback_message_id'
        ) THEN
            UPDATE tickets
            SET escalated_message_id = feedback_message_id
            WHERE escalated_message_id IS NULL
              AND feedback_message_id IS NOT NULL;
        END IF;

        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'tickets'
              AND column_name = 'feedback_message_id'
        ) AND EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'messages'
              AND column_name = 'ticket_opened'
        ) THEN
            UPDATE tickets t
            SET escalated_message_id = (
                SELECT m.id
                FROM messages m
                WHERE m.conversation_id = t.conversation_id
                  AND m.role = 'bot'
                  AND m.ticket_opened IS TRUE
                ORDER BY m.created_at DESC
                LIMIT 1
            )
            WHERE t.escalated_message_id IS NULL;
        END IF;
    END $$;
    """,
    "DROP INDEX IF EXISTS idx_tickets_feedback_message_id;",
    "ALTER TABLE tickets DROP COLUMN IF EXISTS feedback_message_id;",
    "CREATE INDEX IF NOT EXISTS idx_tickets_escalated_message_id ON tickets(escalated_message_id);",
    "ALTER TABLE messages DROP COLUMN IF EXISTS ticket_opened;",
    "ALTER TABLE tickets DROP COLUMN IF EXISTS ai_summary;",
    "ALTER TABLE tickets DROP COLUMN IF EXISTS original_message;",
    "ALTER TABLE tickets DROP COLUMN IF EXISTS translated_message;",
    """
    UPDATE tickets
    SET status = CASE LOWER(TRIM(status))
        WHEN 'open' THEN 'aperto'
        WHEN 'aperto' THEN 'aperto'
        WHEN 'in_progress' THEN 'aperto'
        WHEN 'in progress' THEN 'aperto'
        WHEN 'in_lavorazione' THEN 'aperto'
        WHEN 'in lavorazione' THEN 'aperto'
        WHEN 'closed' THEN 'chiuso'
        WHEN 'chiuso' THEN 'chiuso'
        ELSE 'aperto'
    END;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'tickets_status_valid'
        ) THEN
            ALTER TABLE tickets
            ADD CONSTRAINT tickets_status_valid
            CHECK (status IN ('aperto', 'chiuso'));
        END IF;
    END $$;
    """,
    """
    UPDATE tickets
    SET priority = CASE LOWER(TRIM(COALESCE(priority, '')))
        WHEN 'low' THEN 'bassa'
        WHEN 'bassa' THEN 'bassa'
        WHEN 'medium' THEN 'media'
        WHEN 'media' THEN 'media'
        WHEN 'high' THEN 'alta'
        WHEN 'alta' THEN 'alta'
        ELSE 'media'
    END;
    """,
    """
    UPDATE tickets
    SET domain = CASE LOWER(TRIM(COALESCE(domain, '')))
        WHEN 'general' THEN 'informazioni generali'
        WHEN 'general_information' THEN 'informazioni generali'
        WHEN 'games general' THEN 'informazioni generali'
        WHEN 'games_general' THEN 'informazioni generali'
        WHEN 'unknown' THEN 'informazioni generali'
        WHEN 'ticketing' THEN 'biglietteria'
        WHEN 'venue' THEN 'impianti'
        WHEN 'venue_information' THEN 'impianti'
        WHEN 'event_schedule' THEN 'calendario'
        WHEN 'calendar' THEN 'calendario'
        WHEN 'schedule' THEN 'calendario'
        WHEN 'transport' THEN 'trasporti'
        WHEN 'accessibility' THEN 'accessibilita'
        WHEN 'volunteering' THEN 'volontariato'
        WHEN 'volunteers' THEN 'volontariato'
        WHEN 'contacts' THEN 'contatti'
        WHEN 'complaint' THEN 'reclamo'
        WHEN 'partnership' THEN 'partnership'
        WHEN 'school_project' THEN 'progetto scuola'
        WHEN 'tender_notice' THEN 'bandi e avvisi'
        WHEN 'organizing committee' THEN 'comitato organizzatore'
        WHEN 'organizing_committee' THEN 'comitato organizzatore'
        WHEN 'historical results page' THEN 'risultati storici'
        WHEN 'historical_results_page' THEN 'risultati storici'
        WHEN 'sport' THEN 'sport'
        WHEN 'faq' THEN 'faq'
        ELSE 'informazioni generali'
    END;
    """,
)


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def init_database(max_attempts: int = 30, delay_seconds: float = 1.0) -> None:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg.connect(settings.database_url, autocommit=True) as conn:
                with conn.cursor() as cursor:
                    for statement in SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                    seed_default_operator(cursor)
            logger.info("database initialized")
            return
        except psycopg.Error as exc:
            last_error = exc
            logger.warning(
                "database init attempt %s/%s failed: %s",
                attempt,
                max_attempts,
                exc,
            )
            time.sleep(delay_seconds)

    raise RuntimeError("Database initialization failed.") from last_error


def seed_default_operator(cursor: psycopg.Cursor) -> None:
    email = settings.default_operator_email.strip().lower()
    name = settings.default_operator_name.strip() or "Operatore"
    password = settings.default_operator_password
    if not email or not password:
        return

    cursor.execute(
        """
        INSERT INTO operators (name, email, password_hash)
        VALUES (%s, %s, crypt(%s, gen_salt('bf')))
        ON CONFLICT (email) DO UPDATE
        SET name = EXCLUDED.name
        WHERE operators.name IS NULL
           OR TRIM(operators.name) = ''
           OR operators.name = 'Operatore'
        """,
        (name, email, password),
    )


def fetch_one(query: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


def fetch_all(query: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())
