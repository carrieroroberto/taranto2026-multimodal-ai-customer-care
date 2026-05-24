import re
import uuid
from typing import Any

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
                INSERT INTO messages (conversation_id, role, type, content, created_at)
                VALUES (%s, %s, %s, %s, clock_timestamp())
                RETURNING id, conversation_id, role, type, content, satisfaction, created_at
                """,
                (resolved_id, role, message_type, content),
            )
            row = cursor.fetchone()

    return stringify_ids(dict(row))


def save_user_message(
    session_id: str,
    content: str,
    message_type: str = "text",
) -> dict[str, Any]:
    return save_message(session_id, "user", content, message_type)


def save_bot_message(session_id: str, content: str) -> dict[str, Any]:
    return save_message(session_id, "bot", content, "text")


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
        SELECT id, conversation_id, role, type, content, satisfaction, created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
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
                        SELECT id
                        FROM messages
                        WHERE conversation_id = %s AND role = 'bot'
                        ORDER BY created_at DESC
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
        params.append(status)
    if priority:
        query += " AND priority = %s"
        params.append(priority)
    if domain:
        query += " AND domain = %s"
        params.append(domain)
    
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

    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tickets
                SET status = %s, updated_at = clock_timestamp()
                WHERE id = %s
                RETURNING id, status, updated_at
                """,
                (status, resolved_id),
            )
            row = cursor.fetchone()
    
    return stringify_ids(dict(row)) if row else None


def update_conversation_summary(conversation_id: str, summary: str) -> None:
    resolved_id = conversation_uuid(conversation_id)
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE conversations
                SET ai_summary = %s
                WHERE id = %s
                """,
                (summary, resolved_id),
            )


def save_ticket(ticket_data: dict[str, Any]) -> dict[str, Any]:
    user_email = ticket_data.get("user_email") or ticket_data.get("contact_email")
    if not user_email:
        raise ValueError("user_email is required to create a ticket.")

    summary = str(ticket_data.get("summary") or "").strip()
    original_message = str(
        ticket_data.get("original_message")
        or ticket_data.get("user_message")
        or summary
    ).strip()

    if not summary:
        raise ValueError("summary is required to create a ticket.")
    if not original_message:
        raise ValueError("original_message is required to create a ticket.")

    conversation_id = conversation_uuid(
        ticket_data.get("conversation_id") or ticket_data.get("session_id")
    )
    status = ticket_data.get("status") or "open"
    priority = ticket_data.get("priority")
    domain = ticket_data.get("domain") or ticket_data.get("category")
    translated_message = ticket_data.get("translated_message")
    ai_summary = str(ticket_data.get("ai_summary") or summary or original_message).strip()
    if not ai_summary:
        ai_summary = "Richiesta inviata all'operatore senza dettagli aggiuntivi."

    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversations (id, ai_summary)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET ai_summary = EXCLUDED.ai_summary
                """,
                (conversation_id, ai_summary),
            )
            cursor.execute(
                """
                INSERT INTO tickets (
                    conversation_id,
                    status,
                    priority,
                    domain,
                    user_email,
                    summary,
                    ai_summary,
                    original_message,
                    translated_message
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, conversation_id, status, priority, domain, user_email,
                    summary, ai_summary, original_message, translated_message, created_at
                """,
                (
                    conversation_id,
                    status,
                    priority,
                    domain,
                    user_email,
                    summary,
                    ai_summary,
                    original_message,
                    translated_message,
                ),
            )
            row = cursor.fetchone()

    return stringify_ids(dict(row))


MOBILITY_TERMS = (
    "kyma",
    "mobilita",
    "mobility",
    "trasport",
    "transport",
    "autobus",
    "bus",
    "navetta",
    "shuttle",
    "treno",
    "train",
    "parcheggio",
    "parking",
    "fermata",
)


def sync_kb_sources(records: list[dict[str, Any]]) -> int:
    if not records:
        return 0

    with connect() as conn:
        with conn.cursor() as cursor:
            for record in records:
                metadata = record.get("metadata") or {}
                kb_type = str(metadata.get("type") or "general").strip() or "general"
                title = str(metadata.get("title") or "").strip() or None
                source_url = str(metadata.get("source_url") or "").strip() or None
                document = str(record.get("document") or "")
                search_text = " ".join(
                    part
                    for part in (
                        str(record.get("id") or ""),
                        kb_type,
                        title or "",
                        source_url or "",
                        document,
                    )
                    if part
                )
                cursor.execute(
                    """
                    INSERT INTO kb_sources (
                        id,
                        kb_type,
                        domain_label,
                        title,
                        source_url,
                        is_kyma_mobility,
                        search_text,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, clock_timestamp())
                    ON CONFLICT (id) DO UPDATE SET
                        kb_type = EXCLUDED.kb_type,
                        domain_label = EXCLUDED.domain_label,
                        title = EXCLUDED.title,
                        source_url = EXCLUDED.source_url,
                        is_kyma_mobility = EXCLUDED.is_kyma_mobility,
                        search_text = EXCLUDED.search_text,
                        updated_at = clock_timestamp()
                    """,
                    (
                        str(record["id"]),
                        kb_type,
                        kb_type,
                        title,
                        source_url,
                        source_mentions_mobility(search_text),
                        search_text,
                    ),
                )

            cursor.execute("TRUNCATE kb_source_domains")
            cursor.execute(
                """
                INSERT INTO kb_source_domains (
                    label,
                    source_count,
                    kyma_mobility_count,
                    updated_at
                )
                SELECT
                    domain_label,
                    COUNT(*)::int,
                    COUNT(*) FILTER (WHERE is_kyma_mobility)::int,
                    clock_timestamp()
                FROM kb_sources
                GROUP BY domain_label
                """
            )

    return len(records)


def source_mentions_mobility(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    tokens = set(normalized.split())
    return any(
        term in tokens if len(term) <= 4 else term in normalized
        for term in MOBILITY_TERMS
    )


def get_kb_source_domains() -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT label, source_count, kyma_mobility_count
        FROM kb_source_domains
        ORDER BY label ASC
        """
    )
    return [dict(row) for row in rows]


def get_kb_sources_for_triage(limit: int = 4000) -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT id, domain_label, title, source_url, is_kyma_mobility, search_text
        FROM kb_sources
        ORDER BY is_kyma_mobility DESC, domain_label ASC, id ASC
        LIMIT %s
        """,
        (max(limit, 1),),
    )
    return [dict(row) for row in rows]


def get_kpi_summary() -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM conversations)::int AS total_conversations,
            (SELECT COUNT(*) FROM messages)::int AS total_messages,
            (SELECT COUNT(*) FROM messages WHERE role = 'user')::int AS user_messages,
            (SELECT COUNT(*) FROM messages WHERE role = 'bot')::int AS bot_messages,
            (SELECT COUNT(*) FROM tickets)::int AS total_tickets,
            (SELECT COUNT(*) FROM tickets WHERE status = 'open')::int AS open_tickets,
            (SELECT COUNT(*) FROM tickets WHERE status = 'in_progress')::int AS in_progress_tickets,
            (SELECT COUNT(*) FROM tickets WHERE status = 'closed')::int AS closed_tickets,
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
    for key in ("id", "conversation_id"):
        if key in row and row[key] is not None:
            row[key] = str(row[key])
    return row
