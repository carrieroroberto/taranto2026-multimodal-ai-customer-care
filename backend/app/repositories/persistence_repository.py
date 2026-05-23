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

    with connect() as conn:
        with conn.cursor() as cursor:
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
                    status,
                    priority,
                    domain,
                    user_email,
                    summary,
                    original_message,
                    translated_message
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, conversation_id, status, priority, domain, user_email,
                    summary, original_message, translated_message, created_at
                """,
                (
                    conversation_id,
                    status,
                    priority,
                    domain,
                    user_email,
                    summary,
                    original_message,
                    translated_message,
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
