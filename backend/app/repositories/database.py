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
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        ai_summary TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS ai_summary TEXT;",
    """
    CREATE TABLE IF NOT EXISTS messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
        type TEXT NOT NULL DEFAULT 'text' CHECK (type IN ('text', 'image', 'audio')),
        content TEXT NOT NULL,
        satisfaction BOOLEAN DEFAULT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS type TEXT NOT NULL DEFAULT 'text';
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
        status TEXT NOT NULL DEFAULT 'open',
        priority TEXT,
        domain TEXT,
        user_email TEXT NOT NULL,
        summary TEXT NOT NULL,
        ai_summary TEXT,
        original_message TEXT NOT NULL,
        translated_message TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_sources (
        id TEXT PRIMARY KEY,
        kb_type TEXT NOT NULL,
        domain_label TEXT NOT NULL,
        title TEXT,
        source_url TEXT,
        search_text TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_source_domains (
        label TEXT PRIMARY KEY,
        source_count INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_kb_sources_domain_label
    ON kb_sources (domain_label);
    """,
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS ai_summary TEXT;",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();",
    """
    UPDATE tickets
    SET ai_summary = summary
    WHERE ai_summary IS NULL OR btrim(ai_summary) = '';
    """,
    """
    UPDATE conversations c
    SET ai_summary = t.ai_summary
    FROM (
        SELECT DISTINCT ON (conversation_id)
            conversation_id,
            ai_summary
        FROM tickets
        WHERE ai_summary IS NOT NULL AND btrim(ai_summary) <> ''
        ORDER BY conversation_id, created_at DESC
    ) AS t
    WHERE c.id = t.conversation_id
      AND (c.ai_summary IS NULL OR btrim(c.ai_summary) = '');
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
    password = settings.default_operator_password
    if not email or not password:
        return

    cursor.execute(
        """
        INSERT INTO operators (email, password_hash)
        VALUES (%s, crypt(%s, gen_salt('bf')))
        ON CONFLICT (email) DO NOTHING
        """,
        (email, password),
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
