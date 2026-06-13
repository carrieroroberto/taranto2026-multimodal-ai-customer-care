from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import json
import mimetypes
import os
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = PROJECT_ROOT / "eval" / "test_dataset.jsonl"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "eval" / "outputs"
DEFAULT_BASE_URL = os.getenv("KPI_EVAL_BASE_URL", "http://127.0.0.1:8000/api")

RESULT_FIELDS = [
    "kpi",
    "description",
    "value",
    "unit",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run KPI evaluation without changing chatbot or operator dashboard code.",
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--skip-kpi-snapshot", action="store_true")
    parser.add_argument("--post-feedback", action="store_true")
    parser.add_argument("--post-tickets", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def now_run_id() -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"kpi_eval_{timestamp}_{uuid.uuid4().hex[:8]}"


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(case, dict):
                raise ValueError(f"{path}:{line_number}: each row must be an object")
            case["_line_number"] = line_number
            cases.append(case)
    return cases


def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for case in cases:
        prefix = f"line {case.get('_line_number', '?')}"
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            errors.append(f"{prefix}: missing id")
        elif case_id in seen_ids:
            errors.append(f"{prefix}: duplicated id {case_id}")
        seen_ids.add(case_id)

        modality = str(case.get("modality") or "text").strip().lower()
        if modality not in {"text", "audio", "image"}:
            errors.append(f"{prefix}: unsupported modality {modality!r}")

        message = str(case.get("message") or "").strip()
        if modality == "text" and not message:
            errors.append(f"{prefix}: text cases require message")

        if modality in {"audio", "image"}:
            file_path = case.get("file_path")
            if not file_path:
                errors.append(f"{prefix}: {modality} cases require file_path")
            else:
                resolved = resolve_case_path(Path(str(file_path)))
                if not resolved.exists():
                    errors.append(f"{prefix}: file_path does not exist: {resolved}")

        relevant = case.get("relevant_doc_ids", [])
        if relevant is not None and not isinstance(relevant, list):
            errors.append(f"{prefix}: relevant_doc_ids must be a list")

        feedback = case.get("feedback")
        if feedback is not None and not isinstance(feedback, bool):
            errors.append(f"{prefix}: feedback must be true or false")

        if case.get("open_ticket"):
            if feedback is not False:
                errors.append(f"{prefix}: open_ticket cases must use feedback=false")
            user_email = str(case.get("user_email") or "").strip()
            if user_email and "@" not in user_email:
                errors.append(f"{prefix}: user_email is not a valid benchmark email")
    return errors


def resolve_case_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def compact_json(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def to_bool_text(value: Any) -> str:
    if value is None:
        return ""
    return "true" if bool(value) else "false"


def clean_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def api_url(base_url: str, path: str) -> str:
    return f"{clean_base_url(base_url)}/{path.lstrip('/')}"


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 180.0,
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, parse_json_body(body), None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, parse_json_body(body), body or str(exc)
    except Exception as exc:
        return None, None, str(exc)


def parse_json_body(body: str) -> dict[str, Any] | None:
    if not body:
        return None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def request_multipart(
    url: str,
    fields: dict[str, str | None],
    file_field: str,
    file_path: Path,
    timeout: float,
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    boundary = f"----kpi-eval-{uuid.uuid4().hex}"
    body_parts: list[bytes] = []

    for name, value in fields.items():
        if value is None:
            continue
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8")
        )
        body_parts.append(str(value).encode("utf-8"))
        body_parts.append(b"\r\n")

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    body_parts.append(file_path.read_bytes())
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    req = request.Request(
        url,
        data=b"".join(body_parts),
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, parse_json_body(body), None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, parse_json_body(body), body or str(exc)
    except Exception as exc:
        return None, None, str(exc)


def run_chat_case(
    case: dict[str, Any],
    args: argparse.Namespace,
    run_id: str,
    repeat_index: int,
) -> dict[str, Any]:
    case_id = str(case["id"])
    modality = str(case.get("modality") or "text").lower()
    language = str(case.get("language") or "it")
    session_id = f"{run_id}:{case_id}:{repeat_index}"
    message = str(case.get("message") or "")
    started = time.perf_counter()
    status_code: int | None = None
    payload: dict[str, Any] | None = None
    error_text: str | None = None

    try:
        if modality == "text":
            status_code, payload, error_text = request_json(
                "POST",
                api_url(args.base_url, "/chat"),
                {
                    "message": message,
                    "session_id": session_id,
                    "language": language,
                },
                timeout=args.timeout,
            )
        elif modality == "audio":
            status_code, payload, error_text = request_multipart(
                api_url(args.base_url, "/chat/audio"),
                {"session_id": session_id, "language": language},
                "file",
                resolve_case_path(Path(str(case["file_path"]))),
                timeout=args.timeout,
            )
        elif modality == "image":
            status_code, payload, error_text = request_multipart(
                api_url(args.base_url, "/chat/multimodal"),
                {"session_id": session_id, "language": language, "message": message},
                "file",
                resolve_case_path(Path(str(case["file_path"]))),
                timeout=args.timeout,
            )
        else:
            error_text = f"unsupported modality: {modality}"
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    payload = payload or {}
    success = bool(status_code and 200 <= status_code < 300 and payload.get("answer"))
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    source_titles = [str(source.get("title") or "") for source in sources if isinstance(source, dict)]
    source_urls = [str(source.get("url") or "") for source in sources if isinstance(source, dict)]
    should_escalate = payload.get("should_escalate")
    expected_escalation = case.get("expected_escalation")
    escalation_correct = (
        bool(should_escalate) == bool(expected_escalation)
        if expected_escalation is not None and should_escalate is not None
        else None
    )
    asr_ocr_case = modality in {"audio", "image"}
    asr_ocr_success = success if asr_ocr_case else None

    row = base_row(run_id, case, repeat_index)
    row.update(
        {
            "session_id": session_id,
            "chat_attempted": True,
            "status_code": status_code,
            "success": success,
            "latency_ms": latency_ms,
            "error": error_text,
            "conversation_id": payload.get("conversation_id"),
            "message_id": payload.get("message_id") or payload.get("bot_message_id"),
            "answer_chars": len(str(payload.get("answer") or "")),
            "source_count": len(sources),
            "source_titles": source_titles,
            "source_urls": source_urls,
            "source_coverage": len(sources) > 0,
            "should_escalate": should_escalate,
            "expected_escalation": expected_escalation,
            "escalation_correct": escalation_correct,
            "asr_ocr_case": asr_ocr_case,
            "asr_ocr_success": asr_ocr_success,
        }
    )

    if args.post_feedback and success and "feedback" in case:
        feedback_ok = post_feedback(args, row["message_id"], bool(case["feedback"]))
        row["feedback_posted"] = feedback_ok
        row["feedback_value"] = bool(case["feedback"])

    if args.post_tickets and success and case.get("open_ticket"):
        if case.get("feedback") is False and not row.get("feedback_posted"):
            row["feedback_posted"] = post_feedback(args, row["message_id"], False)
            row["feedback_value"] = False
        ticket_result = post_ticket(args, row, case)
        row.update(ticket_result)

    return row


def post_feedback(args: argparse.Namespace, message_id: str | None, satisfaction: bool) -> bool:
    if not message_id:
        return False
    status_code, _payload, error_text = request_json(
        "PATCH",
        api_url(args.base_url, f"/messages/{message_id}/feedback"),
        {"satisfaction": satisfaction},
        timeout=args.timeout,
    )
    return bool(status_code and 200 <= status_code < 300 and not error_text)


def post_ticket(
    args: argparse.Namespace,
    row: dict[str, Any],
    case: dict[str, Any],
) -> dict[str, Any]:
    conversation_id = row.get("conversation_id")
    message_id = row.get("message_id")
    if not conversation_id:
        return {
            "ticket_attempted": True,
            "ticket_created": False,
            "ticket_id": None,
            "ticket_error": "missing conversation_id",
        }

    user_email = str(case.get("user_email") or "").strip()
    if not user_email:
        user_email = default_ticket_email(str(case.get("id") or "case"))

    status_code, payload, error_text = request_json(
        "POST",
        api_url(args.base_url, "/tickets"),
        {
            "conversation_id": conversation_id,
            "user_email": user_email,
            "language": case.get("language") or "it",
            "escalated_message_id": message_id,
        },
        timeout=args.timeout,
    )
    ticket = (payload or {}).get("ticket") if isinstance(payload, dict) else None
    ticket_id = ticket.get("id") if isinstance(ticket, dict) else None
    created = bool(status_code and 200 <= status_code < 300 and ticket_id and not error_text)
    return {
        "ticket_attempted": True,
        "ticket_created": created,
        "ticket_id": ticket_id,
        "ticket_error": None if created else error_text or f"HTTP {status_code}",
    }


def default_ticket_email(case_id: str) -> str:
    safe_case_id = "".join(char if char.isalnum() else "." for char in case_id.lower()).strip(".")
    safe_case_id = safe_case_id or "case"
    return f"kpi.eval+{safe_case_id}@example.com"


def base_row(run_id: str, case: dict[str, Any], repeat_index: int) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "case_id": case.get("id"),
        "repeat_index": repeat_index,
        "modality": str(case.get("modality") or "text").lower(),
        "language": case.get("language") or "it",
        "message": case.get("message") or "",
        "chat_attempted": False,
        "feedback_posted": False,
        "feedback_value": None,
        "ticket_attempted": False,
        "ticket_created": False,
        "ticket_id": None,
        "ticket_error": None,
        "asr_ocr_case": False,
        "retrieval_attempted": False,
        "expected_domain": case.get("expected_domain"),
        "relevant_doc_ids": case.get("relevant_doc_ids") or [],
    }


async def run_retrieval_cases(
    cases: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, dict[str, Any]]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.services.llm_service import build_query_plan
    from backend.app.services.rag_service import mark_kb_ready, retrieve_context

    mark_kb_ready("eval")
    results: dict[str, dict[str, Any]] = {}

    for case in cases:
        case_id = str(case["id"])
        if case.get("skip_retrieval"):
            continue
        message = str(case.get("message") or "").strip()
        if not message:
            continue
        started = time.perf_counter()
        expected_domain = case.get("expected_domain")
        relevant_ids = [str(item) for item in case.get("relevant_doc_ids") or []]
        row: dict[str, Any] = {
            "retrieval_attempted": True,
            "expected_domain": expected_domain,
            "relevant_doc_ids": relevant_ids,
        }
        try:
            plan = await build_query_plan(
                message,
                history=[],
                ui_language=str(case.get("language") or "it"),
            )
            candidates = retrieve_context(plan, n_results=args.top_k)
            retrieved_ids = [candidate.item_id for candidate in candidates[: args.top_k]]
            retrieved_scores = [round(float(candidate.score), 6) for candidate in candidates[: args.top_k]]
            row.update(
                {
                    "predicted_domain": plan.domain,
                    "predicted_domains": list(plan.domains),
                    "domain_correct": domain_matches(expected_domain, plan.domain, plan.domains),
                    "retrieved_ids_top5": retrieved_ids,
                    "retrieved_scores_top5": retrieved_scores,
                    **retrieval_metrics(retrieved_ids, relevant_ids, args.top_k),
                }
            )
        except Exception as exc:
            row["retrieval_error"] = f"{type(exc).__name__}: {exc}"
            row["retrieval_traceback"] = traceback.format_exc(limit=3)
        row["retrieval_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        results[case_id] = row

    return results


def domain_matches(
    expected_domain: Any,
    predicted_domain: str | None,
    predicted_domains: list[str] | None,
) -> bool | None:
    if expected_domain is None:
        return None
    expected = str(expected_domain).strip().lower()
    if not expected:
        return None
    predicted = {str(predicted_domain or "").strip().lower()}
    predicted.update(str(domain).strip().lower() for domain in predicted_domains or [])
    return expected in predicted


def retrieval_metrics(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    top_k: int,
) -> dict[str, float | None]:
    if not relevant_ids:
        return {"recall_at_5": None, "precision_at_5": None, "mrr": None}
    relevant = set(relevant_ids)
    top = retrieved_ids[:top_k]
    hits = [doc_id for doc_id in top if doc_id in relevant]
    first_rank = next((index + 1 for index, doc_id in enumerate(top) if doc_id in relevant), None)
    return {
        "recall_at_5": 1.0 if hits else 0.0,
        "precision_at_5": round(len(hits) / float(top_k), 4) if top_k else None,
        "mrr": round(1.0 / first_rank, 4) if first_rank else 0.0,
    }


def merge_retrieval(row: dict[str, Any], retrieval: dict[str, Any] | None) -> dict[str, Any]:
    if retrieval:
        row.update(retrieval)
    return row


def fetch_kpi_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    status_code, payload, error_text = request_json(
        "GET",
        api_url(args.base_url, "/kpis"),
        timeout=args.timeout,
    )
    return {
        "status_code": status_code,
        "error": error_text,
        "payload": payload or {},
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def write_results_csv(rows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                csv_ready_row(
                    {
                        "kpi": row.get("kpi"),
                        "description": row.get("measure"),
                        "value": row.get("value"),
                        "unit": row.get("unit"),
                    },
                    RESULT_FIELDS,
                )
            )


def csv_ready_row(row: dict[str, Any], fieldnames: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fieldnames:
        value = row.get(field)
        if isinstance(value, (list, dict)):
            result[field] = compact_json(value)
        elif isinstance(value, bool):
            result[field] = to_bool_text(value)
        elif value is None:
            result[field] = ""
        else:
            result[field] = value
    return result


def build_summary(
    run_id: str,
    rows: list[dict[str, Any]],
    kpi_before: dict[str, Any] | None,
    kpi_after: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    chat_rows = [row for row in rows if row.get("chat_attempted")]
    successful_chat = [row for row in chat_rows if row.get("success")]
    retrieval_rows = unique_case_rows([row for row in rows if row.get("retrieval_attempted")])

    value, numerator, denominator = ratio_parts(
        [row.get("domain_correct") for row in retrieval_rows]
    )
    add_metric(
        summary,
        run_id,
        "Qualita Informativa",
        "Domain Accuracy",
        "Capacita di classificare correttamente il dominio della domanda",
        value,
        "percent",
        "Retrieval",
        numerator=numerator,
        denominator=denominator,
    )
    value, numerator, denominator = average_parts([row.get("recall_at_5") for row in retrieval_rows])
    add_metric(
        summary,
        run_id,
        "Qualita Informativa",
        "Recall@5",
        "Almeno un documento corretto tra i primi 5 risultati",
        value,
        "ratio",
        "Retrieval",
        numerator=numerator,
        denominator=denominator,
    )
    value, numerator, denominator = average_parts([row.get("precision_at_5") for row in retrieval_rows])
    add_metric(
        summary,
        run_id,
        "Qualita Informativa",
        "Precision@5",
        "Quota di documenti pertinenti tra i primi 5 risultati",
        value,
        "ratio",
        "Retrieval",
        numerator=numerator,
        denominator=denominator,
    )
    value, numerator, denominator = average_parts([row.get("mrr") for row in retrieval_rows])
    add_metric(
        summary,
        run_id,
        "Qualita Informativa",
        "MRR",
        "Reciprocal rank medio del primo documento corretto",
        value,
        "ratio",
        "Retrieval",
        numerator=numerator,
        denominator=denominator,
    )

    source_values = [row.get("source_coverage") for row in successful_chat]
    value, numerator, denominator = ratio_parts(source_values)
    add_metric(
        summary,
        run_id,
        "Qualita Informativa",
        "Source Coverage Rate",
        "Percentuale di risposte supportate da almeno una fonte della KB",
        value,
        "percent",
        "Retrieval/API",
        numerator=numerator,
        denominator=denominator,
    )

    latencies = [to_float(row.get("latency_ms")) for row in chat_rows]
    latencies = [value for value in latencies if value is not None]
    value, numerator, denominator = average_parts(latencies)
    add_metric(
        summary,
        run_id,
        "Performance Tecnica",
        "Average Latency",
        "Tempo medio di risposta end-to-end del sistema",
        value,
        "ms",
        "Backend/API",
        numerator=numerator,
        denominator=denominator,
    )
    add_metric(
        summary,
        run_id,
        "Performance Tecnica",
        "p95 Latency",
        "Tempo entro cui rientra il 95 percento delle richieste",
        percentile(latencies, 95),
        "ms",
        "Backend/API",
        denominator=len(latencies) if latencies else None,
    )
    value, numerator, denominator = ratio_parts(
        [not bool(row.get("success")) for row in chat_rows]
    )
    add_metric(
        summary,
        run_id,
        "Performance Tecnica",
        "Error Rate",
        "Percentuale di richieste fallite rispetto al totale",
        value,
        "percent",
        "Backend/API",
        numerator=numerator,
        denominator=denominator,
    )
    operational_escalations = [
        bool(row.get("ticket_created") or row.get("should_escalate"))
        for row in successful_chat
    ]
    value, numerator, denominator = ratio_parts(operational_escalations)
    add_metric(
        summary,
        run_id,
        "Impatto Operativo",
        "Escalation Rate",
        "Percentuale di conversazioni test trasferite o trasformate in ticket operatore",
        value,
        "percent",
        "API/Tickets",
        numerator=numerator,
        denominator=denominator,
    )
    value, numerator, denominator = ratio_parts([not value for value in operational_escalations])
    add_metric(
        summary,
        run_id,
        "Impatto Operativo",
        "Containment Rate",
        "Percentuale di conversazioni risolte senza operatore",
        value,
        "percent",
        "API/Tickets",
        numerator=numerator,
        denominator=denominator,
    )

    add_database_metrics(summary, run_id, kpi_before, kpi_after)
    return summary


def unique_case_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row.get("case_id") or "")
        if case_id in seen:
            continue
        seen.add(case_id)
        result.append(row)
    return result


def add_database_metrics(
    summary: list[dict[str, Any]],
    run_id: str,
    kpi_before: dict[str, Any] | None,
    kpi_after: dict[str, Any] | None,
) -> None:
    snapshot = (kpi_after or {}).get("payload") or {}
    if not snapshot:
        return

    conversations = to_float(snapshot.get("total_conversations")) or 0.0
    tickets = to_float(snapshot.get("total_tickets")) or 0.0
    db_escalation = tickets / conversations if conversations else None
    db_containment = 1.0 - db_escalation if db_escalation is not None else None

    add_metric(
        summary,
        run_id,
        "Impatto Operativo",
        "Escalation Rate DB Snapshot",
        "Ticket totali diviso conversazioni totali nel database",
        db_escalation,
        "percent",
        "Database /api/kpis",
        numerator=tickets,
        denominator=conversations,
        notes="Snapshot cumulativo; usare DB pulito o delta before/after per run isolati.",
    )
    add_metric(
        summary,
        run_id,
        "Impatto Operativo",
        "Containment Rate DB Snapshot",
        "Conversazioni senza ticket operatore nel database",
        db_containment,
        "percent",
        "Database /api/kpis",
        numerator=(conversations - tickets) if conversations else None,
        denominator=conversations,
        notes="Snapshot cumulativo; usare DB pulito o delta before/after per run isolati.",
    )
    add_metric(
        summary,
        run_id,
        "Impatto Operativo",
        "Feedback Score",
        "Soddisfazione utente sui messaggi valutati",
        to_float(snapshot.get("satisfaction_rate")),
        "percent",
        "Database /api/kpis",
        numerator=to_float(snapshot.get("positive_feedback")),
        denominator=to_float(snapshot.get("rated_messages")),
    )

    before = (kpi_before or {}).get("payload") or {}
    if before:
        delta_conversations = (to_float(snapshot.get("total_conversations")) or 0) - (
            to_float(before.get("total_conversations")) or 0
        )
        delta_tickets = (to_float(snapshot.get("total_tickets")) or 0) - (
            to_float(before.get("total_tickets")) or 0
        )
        delta_escalation = delta_tickets / delta_conversations if delta_conversations else None
        add_metric(
            summary,
            run_id,
            "Impatto Operativo",
            "Escalation Rate DB Delta",
            "Nuovi ticket diviso nuove conversazioni durante la run",
            delta_escalation,
            "percent",
            "Database /api/kpis",
            numerator=delta_tickets,
            denominator=delta_conversations,
            notes="Valido solo se la run crea ticket tramite il flusso applicativo.",
        )


def add_metric(
    rows: list[dict[str, Any]],
    run_id: str,
    macroarea: str,
    kpi: str,
    measure: str,
    value: float | None,
    unit: str,
    source: str,
    numerator: float | None = None,
    denominator: float | None = None,
    notes: str = "",
) -> None:
    if numerator is None or denominator is None:
        numerator, denominator = infer_ratio_parts(value)
    rows.append(
        {
            "run_id": run_id,
            "macroarea": macroarea,
            "kpi": kpi,
            "measure": measure,
            "value": round(value, 4) if isinstance(value, float) else value,
            "numerator": numerator,
            "denominator": denominator,
            "unit": unit,
            "source": source,
            "notes": notes,
        }
    )


def infer_ratio_parts(value: float | None) -> tuple[None, None]:
    return None, None


def ratio(values: list[Any]) -> float | None:
    value, _numerator, _denominator = ratio_parts(values)
    return value


def ratio_parts(values: list[Any]) -> tuple[float | None, int | None, int | None]:
    filtered = [value for value in values if value is not None and value != ""]
    if not filtered:
        return None, None, None
    numerator = sum(1 for value in filtered if bool(value))
    denominator = len(filtered)
    return numerator / denominator, numerator, denominator


def average_number(values: list[Any]) -> float | None:
    value, _numerator, _denominator = average_parts(values)
    return value


def average_parts(values: list[Any]) -> tuple[float | None, float | None, int | None]:
    numbers = [to_float(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if not numbers:
        return None, None, None
    numerator = sum(numbers)
    denominator = len(numbers)
    return numerator / denominator, numerator, denominator


def percentile(values: list[float], percentile_value: float) -> float | None:
    numbers = sorted(value for value in values if value is not None)
    if not numbers:
        return None
    if len(numbers) == 1:
        return numbers[0]
    rank = (len(numbers) - 1) * percentile_value / 100.0
    lower = int(rank)
    upper = min(lower + 1, len(numbers) - 1)
    weight = rank - lower
    return numbers[lower] * (1 - weight) + numbers[upper] * weight


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def print_summary(summary: list[dict[str, Any]], output_dir: Path) -> None:
    print(f"Wrote KPI results to: {output_dir / 'results.csv'}")
    for row in summary:
        value = row.get("value")
        if value is None:
            value_text = "n/a"
        elif row.get("unit") == "percent":
            value_text = f"{float(value) * 100:.2f}%"
        elif row.get("unit") == "ms":
            value_text = f"{float(value):.2f} ms"
        else:
            value_text = str(value)
        print(f"- {row['kpi']}: {value_text}")


def main() -> int:
    args = parse_args()
    args.repeat = max(1, args.repeat)
    args.top_k = max(1, args.top_k)
    run_id = args.run_id or now_run_id()
    output_dir = args.output_dir or DEFAULT_OUTPUT_ROOT

    cases = load_cases(args.cases)
    validation_errors = validate_cases(cases)
    if validation_errors:
        for validation_error in validation_errors:
            print(f"ERROR: {validation_error}", file=sys.stderr)
        return 2
    if args.validate_only:
        print(f"Validated {len(cases)} cases from {args.cases}")
        return 0

    kpi_before = None
    if not args.skip_kpi_snapshot:
        kpi_before = fetch_kpi_snapshot(args)

    retrieval_by_case: dict[str, dict[str, Any]] = {}
    if not args.skip_retrieval:
        retrieval_by_case = asyncio.run(run_retrieval_cases(cases, args))

    rows: list[dict[str, Any]] = []
    if args.skip_chat:
        for case in cases:
            row = base_row(run_id, case, repeat_index=0)
            rows.append(merge_retrieval(row, retrieval_by_case.get(str(case["id"]))))
    else:
        for repeat_index in range(args.repeat):
            for case in cases:
                if case.get("skip_chat"):
                    row = base_row(run_id, case, repeat_index)
                else:
                    row = run_chat_case(case, args, run_id, repeat_index)
                rows.append(merge_retrieval(row, retrieval_by_case.get(str(case["id"]))))

    kpi_after = None
    if not args.skip_kpi_snapshot:
        kpi_after = fetch_kpi_snapshot(args)

    summary = build_summary(run_id, rows, kpi_before, kpi_after)
    write_results_csv(summary, output_dir)
    print_summary(summary, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
