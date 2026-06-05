import uuid
from typing import Any
from psycopg.types.json import Jsonb

from backend.app.repositories.database import connect, fetch_all, fetch_one


SESSION_NAMESPACE = uuid.UUID("5b1de06e-5d24-41f8-97c1-5aa8d7bb7b2a")


def conversation_uuid(value: str | None = None) -> uuid.UUID:
    if not value:
        return uuid.uuid4()

    try:
        return uuid.UUID(str(value))
    except ValueError:
        return uuid.uuid5(SESSION_NAMESPACE, str(value))


def ensure_conversation(
    conversation_id: str | None = None,
    session_id: str | None = None,
) -> str:
    resolved_id = conversation_uuid(conversation_id or session_id)
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversations (id)
                VALUES (%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (resolved_id,),
            )
    return str(resolved_id)


VALID_MESSAGE_TYPES = {"text", "image", "audio"}


def save_message(
    session_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    sources: list[Any] | None = None,
) -> dict[str, Any]:
    if role not in {"user", "bot"}:
        raise ValueError("role must be 'user' or 'bot'.")
    if message_type not in VALID_MESSAGE_TYPES:
        message_type = "text"

    resolved_id = conversation_uuid(session_id)
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversations (id)
                VALUES (%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (resolved_id,),
            )
            cursor.execute(
                """
                INSERT INTO messages (conversation_id, role, type, content, sources, created_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome')
                RETURNING id, conversation_id, role, type, content, sources, satisfaction, created_at
                """,
                (resolved_id, role, message_type, content, Jsonb(normalize_sources_for_storage(sources))),
            )
            row = cursor.fetchone()

    return stringify_ids(dict(row))


def save_user_message(
    session_id: str,
    content: str,
    message_type: str = "text",
) -> dict[str, Any]:
    return save_message(session_id, "user", content, message_type)


def save_bot_message(
    session_id: str,
    content: str,
    sources: list[Any] | None = None,
) -> dict[str, Any]:
    return save_message(session_id, "bot", content, "text", sources)


def save_interaction(session_id: str, interaction: dict[str, Any]) -> None:
    if not session_id:
        return

    user_message = str(interaction.get("message") or "")
    bot_answer = str(interaction.get("answer") or "")

    if user_message:
        save_user_message(session_id, user_message)
    if bot_answer:
        save_bot_message(session_id, bot_answer)


def get_conversation_messages(session_id: str) -> list[dict[str, Any]]:
    if not session_id:
        return []

    resolved_id = conversation_uuid(session_id)
    rows = fetch_all(
        """
        SELECT
            m.id,
            m.conversation_id,
            m.role,
            m.type,
            m.content,
            m.sources,
            m.satisfaction,
            EXISTS (
                SELECT 1
                FROM tickets t
                WHERE t.escalated_message_id = m.id
            ) AS ticket_opened,
            m.created_at
        FROM messages m
        WHERE m.conversation_id = %s
        ORDER BY m.created_at ASC
        """,
        (resolved_id,),
    )
    return [stringify_ids(dict(row)) for row in rows]


def get_session_history(session_id: str, limit: int = 5) -> list[dict[str, Any]]:
    if not session_id:
        return []

    resolved_id = conversation_uuid(session_id)
    rows = fetch_all(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (resolved_id, max(limit, 1) * 2),
    )
    rows.reverse()

    history: list[dict[str, Any]] = []
    pending_user: str | None = None

    for row in rows:
        role = row["role"]
        content = row["content"]
        if role == "user":
            if pending_user is not None:
                history.append({"message": pending_user, "answer": ""})
            pending_user = content
            continue

        if pending_user is None:
            history.append({"message": "", "answer": content})
        else:
            history.append({"message": pending_user, "answer": content})
            pending_user = None

    if pending_user is not None:
        history.append({"message": pending_user, "answer": ""})

    return history[-limit:]


def save_feedback(feedback_data: dict[str, Any]) -> bool:
    satisfaction = int(feedback_data["rating"]) >= 4
    message_id = feedback_data.get("message_id")
    session_id = feedback_data.get("session_id")

    with connect() as conn:
        with conn.cursor() as cursor:
            if message_id:
                try:
                    resolved_message_id = uuid.UUID(str(message_id))
                except ValueError:
                    resolved_message_id = None

                if resolved_message_id:
                    if is_feedback_locked(cursor, resolved_message_id):
                        raise ValueError("Feedback is locked because a ticket was already opened for this message.")

                    cursor.execute(
                        """
                        UPDATE messages
                        SET satisfaction = %s
                        WHERE id = %s AND role = 'bot'
                        """,
                        (satisfaction, resolved_message_id),
                    )
                    if cursor.rowcount:
                        return True

            if session_id:
                resolved_conversation_id = conversation_uuid(str(session_id))
                cursor.execute(
                    """
                    UPDATE messages
                    SET satisfaction = %s
                    WHERE id = (
                        SELECT m.id
                        FROM messages m
                        WHERE m.conversation_id = %s
                          AND m.role = 'bot'
                          AND NOT EXISTS (
                              SELECT 1
                              FROM tickets t
                              WHERE t.escalated_message_id = m.id
                          )
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    )
                    """,
                    (satisfaction, resolved_conversation_id),
                )
                return bool(cursor.rowcount)

    return False


def update_message_satisfaction(message_id: str, satisfaction: bool | None) -> dict[str, Any] | None:
    try:
        resolved_id = uuid.UUID(message_id)
    except ValueError:
        return None

    with connect() as conn:
        with conn.cursor() as cursor:
            # Check if exists and is bot
            cursor.execute("SELECT role FROM messages WHERE id = %s", (resolved_id,))
            row = cursor.fetchone()
            if not row:
                return None
            if row["role"] != "bot":
                raise ValueError("Feedback allowed only on bot messages.")
            if is_feedback_locked(cursor, resolved_id):
                raise ValueError("Feedback is locked because a ticket was already opened for this message.")

            cursor.execute(
                """
                UPDATE messages
                SET satisfaction = %s
                WHERE id = %s
                RETURNING id, satisfaction
                """,
                (satisfaction, resolved_id),
            )
            updated = cursor.fetchone()
    
    return stringify_ids(dict(updated)) if updated else None


def get_operator_by_email(email: str) -> dict[str, Any] | None:
    row = fetch_one(
        "SELECT id, email, password_hash FROM operators WHERE email = %s",
        (email,),
    )
    return dict(row) if row else None


def ensure_default_operator(email: str, password_hash: str) -> None:
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO operators (email, password_hash)
                VALUES (%s, %s)
                ON CONFLICT (email) DO NOTHING
                """,
                (email, password_hash),
            )


def get_tickets(
    status: str | None = None,
    priority: str | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if status:
        query += " AND status = %s"
        params.append(normalize_ticket_status(status))
    if priority:
        query += " AND priority = %s"
        params.append(normalize_ticket_priority(priority))
    if domain:
        query += " AND domain = %s"
        params.append(normalize_ticket_domain(domain))
    
    query += " ORDER BY created_at DESC"
    
    rows = fetch_all(query, tuple(params))
    return [stringify_ids(dict(row)) for row in rows]


def get_ticket_detail(ticket_id: str) -> dict[str, Any] | None:
    try:
        resolved_id = uuid.UUID(ticket_id)
    except ValueError:
        return None

    row = fetch_one("SELECT * FROM tickets WHERE id = %s", (resolved_id,))
    if not row:
        return None
    
    ticket = dict(row)
    # Also get conversation messages
    ticket["conversation"] = get_conversation_messages(str(ticket["conversation_id"]))
    
    return stringify_ids(ticket)


def update_ticket_status(ticket_id: str, status: str) -> dict[str, Any] | None:
    try:
        resolved_id = uuid.UUID(ticket_id)
    except ValueError:
        return None

    normalized_status = normalize_ticket_status(status)

    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tickets
                SET status = %s, updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Rome'
                WHERE id = %s
                RETURNING id, status, updated_at
                """,
                (normalized_status, resolved_id),
            )
            row = cursor.fetchone()
    
    return stringify_ids(dict(row)) if row else None


def save_ticket(ticket_data: dict[str, Any]) -> dict[str, Any]:
    user_email = ticket_data.get("user_email") or ticket_data.get("contact_email")
    if not user_email:
        raise ValueError("user_email is required to create a ticket.")

    summary = str(ticket_data.get("summary") or "").strip()

    if not summary:
        raise ValueError("summary is required to create a ticket.")

    conversation_id = conversation_uuid(
        ticket_data.get("conversation_id") or ticket_data.get("session_id")
    )
    status = normalize_ticket_status(ticket_data.get("status"))
    priority = normalize_ticket_priority(ticket_data.get("priority"))
    domain = normalize_ticket_domain(ticket_data.get("domain") or ticket_data.get("category"))
    escalated_message_id = parse_optional_uuid(ticket_data.get("escalated_message_id"))

    with connect() as conn:
        with conn.cursor() as cursor:
            if escalated_message_id:
                cursor.execute(
                    """
                    SELECT id
                    FROM messages
                    WHERE id = %s
                      AND conversation_id = %s
                      AND role = 'bot'
                    """,
                    (escalated_message_id, conversation_id),
                )
                if not cursor.fetchone():
                    raise ValueError("escalated_message_id must reference a bot message in the conversation.")

            cursor.execute(
                """
                INSERT INTO conversations (id)
                VALUES (%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (conversation_id,),
            )
            cursor.execute(
                """
                INSERT INTO tickets (
                    conversation_id,
                    escalated_message_id,
                    status,
                    priority,
                    domain,
                    user_email,
                    summary
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, conversation_id, escalated_message_id, status, priority, domain, user_email,
                    summary, created_at
                """,
                (
                    conversation_id,
                    escalated_message_id,
                    status,
                    priority,
                    domain,
                    user_email,
                    summary,
                ),
            )
            row = cursor.fetchone()

    return stringify_ids(dict(row))


def get_kpi_summary() -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM conversations)::int AS total_conversations,
            (SELECT COUNT(*) FROM messages)::int AS total_messages,
            (SELECT COUNT(*) FROM messages WHERE role = 'user')::int AS user_messages,
            (SELECT COUNT(*) FROM messages WHERE role = 'bot')::int AS bot_messages,
            (SELECT COUNT(*) FROM tickets)::int AS total_tickets,
            (SELECT COUNT(*) FROM tickets WHERE status = 'aperto')::int AS open_tickets,
            (SELECT COUNT(*) FROM tickets WHERE status = 'chiuso')::int AS closed_tickets,
            (SELECT COUNT(*) FROM messages WHERE satisfaction IS TRUE)::int AS positive_feedback,
            (SELECT COUNT(*) FROM messages WHERE satisfaction IS FALSE)::int AS negative_feedback,
            (SELECT COUNT(*) FROM messages WHERE satisfaction IS NOT NULL)::int AS rated_messages
        """
    )
    if not row:
        return {}

    rated_messages = row["rated_messages"] or 0
    positive_feedback = row["positive_feedback"] or 0
    satisfaction_rate = (
        round(positive_feedback / rated_messages, 4)
        if rated_messages
        else None
    )
    return {**row, "satisfaction_rate": satisfaction_rate}


def stringify_ids(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("id", "conversation_id", "escalated_message_id"):
        if key in row and row[key] is not None:
            row[key] = str(row[key])
    return row


def normalize_sources_for_storage(sources: list[Any] | None) -> list[dict[str, Any]]:
    if not sources:
        return []

    normalized_sources: list[dict[str, Any]] = []
    for source in sources[:4]:
        if hasattr(source, "model_dump"):
            source_data = source.model_dump()
        elif isinstance(source, dict):
            source_data = dict(source)
        else:
            continue

        url = str(source_data.get("url") or "").strip()
        maps_url = str(source_data.get("maps_url") or "").strip()
        if not url and not maps_url:
            continue

        normalized_sources.append(
            {
                "title": optional_source_string(source_data.get("title")),
                "url": url or maps_url,
                "type": optional_source_string(source_data.get("type")),
                "maps_url": maps_url or None,
            }
        )

    return normalized_sources


def optional_source_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def normalize_ticket_status(value: Any) -> str:
    normalized = normalize_ticket_label(value)
    return {
        "": "aperto",
        "open": "aperto",
        "aperto": "aperto",
        "in_progress": "aperto",
        "in progress": "aperto",
        "in_lavorazione": "aperto",
        "in lavorazione": "aperto",
        "closed": "chiuso",
        "chiuso": "chiuso",
    }.get(normalized, "aperto")


def normalize_ticket_priority(value: Any) -> str:
    normalized = normalize_ticket_label(value)
    return {
        "": "media",
        "low": "bassa",
        "bassa": "bassa",
        "medium": "media",
        "media": "media",
        "high": "alta",
        "alta": "alta",
    }.get(normalized, "media")


def normalize_ticket_domain(value: Any) -> str:
    normalized = normalize_ticket_label(value)
    return {
        "": "informazioni generali",
        "general": "informazioni generali",
        "general information": "informazioni generali",
        "general_information": "informazioni generali",
        "games general": "informazioni generali",
        "games_general": "informazioni generali",
        "unknown": "informazioni generali",
        "ticketing": "biglietteria",
        "venue": "impianti",
        "venue information": "impianti",
        "venue_information": "impianti",
        "event schedule": "calendario",
        "event_schedule": "calendario",
        "calendar": "calendario",
        "schedule": "calendario",
        "transport": "trasporti",
        "accessibility": "accessibilita",
        "volunteering": "volontariato",
        "volunteers": "volontariato",
        "contacts": "contatti",
        "complaint": "reclamo",
        "partnership": "partnership",
        "school project": "progetto scuola",
        "school_project": "progetto scuola",
        "tender notice": "bandi e avvisi",
        "tender_notice": "bandi e avvisi",
        "organizing committee": "comitato organizzatore",
        "organizing_committee": "comitato organizzatore",
        "historical results page": "risultati storici",
        "historical_results_page": "risultati storici",
        "sport": "sport",
        "faq": "faq",
    }.get(normalized, "informazioni generali")


def normalize_ticket_label(value: Any) -> str:
    return str(value or "").strip().lower()


def parse_optional_uuid(value: Any) -> uuid.UUID | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValueError("escalated_message_id must be a valid UUID.") from exc


def is_feedback_locked(cursor: Any, message_id: uuid.UUID) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM tickets
        WHERE escalated_message_id = %s
        LIMIT 1
        """,
        (message_id,),
    )
    return cursor.fetchone() is not None
