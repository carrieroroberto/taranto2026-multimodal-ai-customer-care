import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


def env_path(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default)).expanduser()
    if value.is_absolute():
        return value
    return PROJECT_ROOT / value


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://app:app@localhost:5433/app",
    )
    default_operator_email: str = os.getenv(
        "DEFAULT_OPERATOR_EMAIL",
        "operatore@tarai.it",
    )
    default_operator_password: str = os.getenv(
        "DEFAULT_OPERATOR_PASSWORD",
        "OperatoreTaranto2026!",
    )
    chroma_host: str = os.getenv("CHROMA_HOST", "localhost")
    chroma_port: int = int(os.getenv("CHROMA_PORT", "8001"))
    collection_name: str = os.getenv("COLLECTION_NAME", "taranto2026_kb")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    ingest_batch_size: int = int(os.getenv("INGEST_BATCH_SIZE", "64"))
    kb_path: Path = env_path("KB_PATH", "backend/data/kb.jsonl")
    n_results: int = int(os.getenv("N_RESULTS", "8"))
    auto_ingest_on_startup: bool = os.getenv("AUTO_INGEST_ON_STARTUP", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    force_reingest_on_startup: bool = os.getenv(
        "FORCE_REINGEST_ON_STARTUP",
        "false",
    ).lower() in {"1", "true", "yes"}
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    query_parser_model: str = os.getenv(
        "QUERY_PARSER_MODEL",
        os.getenv("OLLAMA_MODEL", "qwen3:8b"),
    )
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "150"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    llm_num_predict: int = int(os.getenv("LLM_NUM_PREDICT", "220"))
    llm_context_window: int = int(os.getenv("LLM_CONTEXT_WINDOW", "4096"))
    max_context_chars: int = int(os.getenv("MAX_CONTEXT_CHARS", "3200"))
    use_llm_query_parser: bool = os.getenv(
        "USE_LLM_QUERY_PARSER",
        "true",
    ).lower() in {"1", "true", "yes"}
    query_parser_timeout_seconds: int = int(
        os.getenv("QUERY_PARSER_TIMEOUT_SECONDS", "150")
    )
    query_parser_num_predict: int = int(os.getenv("QUERY_PARSER_NUM_PREDICT", "420"))


settings = Settings()
