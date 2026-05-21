import json
import os
from datetime import datetime
from typing import Any


DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.jsonl")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.jsonl")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")


def save_to_jsonl(file_path: str, data: dict[str, Any]):
    """Saves a dictionary as a JSON line in the specified file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Add timestamp
    data["timestamp"] = datetime.now().isoformat()
    
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def save_feedback(feedback_data: dict[str, Any]):
    save_to_jsonl(FEEDBACK_FILE, feedback_data)


def save_ticket(ticket_data: dict[str, Any]):
    save_to_jsonl(TICKETS_FILE, ticket_data)


def save_interaction(session_id: str, interaction: dict[str, Any]):
    """Saves a single interaction (user message and bot response) to a session file."""
    if not session_id:
        return
    
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    session_file = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
    
    interaction["timestamp"] = datetime.now().isoformat()
    
    with open(session_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(interaction, ensure_ascii=False) + "\n")


def get_session_history(session_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Retrieves the last N interactions for a given session."""
    if not session_id:
        return []
        
    session_file = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
    if not os.path.exists(session_file):
        return []
        
    history = []
    with open(session_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            
    return history[-limit:]
