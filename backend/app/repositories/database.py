import logging
import time
from collections.abc import Iterable
from typing import Any

import psycopg
from psycopg.rows import dict_row

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
        is_kyma_mobility BOOLEAN NOT NULL DEFAULT FALSE,
        search_text TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_source_domains (
        label TEXT PRIMARY KEY,
        source_count INTEGER NOT NULL DEFAULT 0,
        kyma_mobility_count INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_agency (
        agency_id TEXT PRIMARY KEY,
        agency_name TEXT NOT NULL,
        agency_url TEXT NOT NULL,
        agency_timezone TEXT NOT NULL,
        agency_lang TEXT,
        agency_phone TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_stops (
        stop_id TEXT PRIMARY KEY,
        stop_code TEXT,
        stop_name TEXT NOT NULL,
        stop_desc TEXT,
        stop_lat DOUBLE PRECISION,
        stop_lon DOUBLE PRECISION,
        zone_id TEXT,
        stop_url TEXT,
        location_type INTEGER,
        parent_station TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_routes (
        route_id TEXT PRIMARY KEY,
        agency_id TEXT REFERENCES transport_agency(agency_id),
        route_short_name TEXT,
        route_long_name TEXT,
        route_desc TEXT,
        route_type INTEGER NOT NULL,
        route_url TEXT,
        route_color TEXT,
        route_text_color TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_calendar (
        service_id TEXT PRIMARY KEY,
        monday INTEGER NOT NULL,
        tuesday INTEGER NOT NULL,
        wednesday INTEGER NOT NULL,
        thursday INTEGER NOT NULL,
        friday INTEGER NOT NULL,
        saturday INTEGER NOT NULL,
        sunday INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_calendar_dates (
        service_id TEXT NOT NULL,
        date TEXT NOT NULL,
        exception_type INTEGER NOT NULL,
        PRIMARY KEY (service_id, date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_trips (
        route_id TEXT REFERENCES transport_routes(route_id),
        service_id TEXT,
        trip_id TEXT PRIMARY KEY,
        trip_headsign TEXT,
        trip_short_name TEXT,
        direction_id INTEGER,
        block_id TEXT,
        shape_id TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_stop_times (
        trip_id TEXT REFERENCES transport_trips(trip_id),
        arrival_time TEXT NOT NULL,
        departure_time TEXT NOT NULL,
        stop_id TEXT REFERENCES transport_stops(stop_id),
        stop_sequence INTEGER NOT NULL,
        stop_headsign TEXT,
        pickup_type INTEGER,
        drop_off_type INTEGER,
        shape_dist_traveled DOUBLE PRECISION,
        PRIMARY KEY (trip_id, stop_sequence)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transport_stop_times_stop_id ON transport_stop_times (stop_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transport_trips_route_id ON transport_trips (route_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transport_stops_name ON transport_stops (stop_name);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_kb_sources_domain_label
    ON kb_sources (domain_label);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_kb_sources_kyma_mobility
    ON kb_sources (is_kyma_mobility);
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
