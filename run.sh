#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-full}"
MODE_LC="$(printf '%s' "$MODE" | tr '[:upper:]' '[:lower:]')"

pause() {
    read -rp "Premi INVIO per uscire..."
}

usage() {
    echo "Uso: ./run.sh [lite|full]"
    echo
    echo "  lite  = Groq API per testo e multimodalita, senza Ollama locale"
    echo "  full  = modelli locali con Ollama GPU, Groq solo fallback da timeout"
    echo
}

if [[ "$MODE_LC" != "lite" && "$MODE_LC" != "full" ]]; then
    usage
    pause
    exit 1
fi

MAX_LINK_WAIT_SECONDS=120
START_LOG="$(mktemp "${TMPDIR:-/tmp}/talos_compose_start_XXXXXX.log")"
CF_LOG="$(mktemp "${TMPDIR:-/tmp}/talos_cloudflare_logs_XXXXXX.log")"
CF_LINK=""

COMPOSE_CMD=(docker compose)

echo "Mode: $MODE_LC"
echo

start_error() {
    echo "ERRORE: avvio Docker Compose non riuscito."
    echo

    if [[ -f "$START_LOG" ]]; then
        cat "$START_LOG"
    fi

    pause
    exit 1
}

wait_health() {
    local service_name="$1"
    local wait_seconds="$2"
    local health_tries=$((wait_seconds / 2))
    local health_count=0
    local health_status=""

    while true; do
        health_status="$(docker inspect --format '{{.State.Health.Status}}' "$service_name" 2>/dev/null || true)"

        if [[ "$health_status" == "healthy" ]]; then
            return 0
        fi

        health_count=$((health_count + 1))

        if (( health_count >= health_tries )); then
            return 1
        fi

        sleep 2
    done
}

start_lite() {
    "${COMPOSE_CMD[@]}" stop llm llm-init >/dev/null 2>&1 || true

    "${COMPOSE_CMD[@]}" up -d --build --force-recreate --no-deps database pgadmin vector-db > "$START_LOG" 2>&1 \
        || start_error

    wait_health talos-database 120 \
        || start_error

    "${COMPOSE_CMD[@]}" up -d --build --force-recreate --no-deps backend frontend cloudflared > "$START_LOG" 2>&1 \
        || start_error

    wait_health talos-backend 180 \
        || start_error
}

start_full() {
    "${COMPOSE_CMD[@]}" up -d --build --force-recreate database pgadmin vector-db llm > "$START_LOG" 2>&1 \
        || start_error

    wait_health talos-database 120 \
        || start_error

    "${COMPOSE_CMD[@]}" up --build --force-recreate llm-init \
        || start_error

    "${COMPOSE_CMD[@]}" up -d --build --force-recreate backend frontend cloudflared > "$START_LOG" 2>&1 \
        || start_error
}

print_local_links() {
    echo "Link:"
    echo "  Frontend: http://localhost:5173"
    echo "  Backend:  http://localhost:8000/docs"
    echo "  pgAdmin:  http://localhost:5050"
    echo
}

fetch_cloudflare_link() {
    local since_utc
    local cf_container
    local tries=0
    local max_tries=$((MAX_LINK_WAIT_SECONDS / 2))

    since_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    "${COMPOSE_CMD[@]}" restart cloudflared > "$START_LOG" 2>&1 \
        || return 1

    cf_container="$("${COMPOSE_CMD[@]}" ps -q cloudflared | tail -n 1)"

    if [[ -z "$cf_container" ]]; then
        return 1
    fi

    while true; do
        docker logs --since "$since_utc" --tail 300 "$cf_container" > "$CF_LOG" 2>&1 || true

        CF_LINK="$(grep -Eo 'https://[A-Za-z0-9-]+\.trycloudflare\.com' "$CF_LOG" | tail -n 1 || true)"

        if [[ -n "$CF_LINK" ]]; then
            echo "Link HTTPS Cloudflare:"
            echo "  $CF_LINK"
            echo
            return 0
        fi

        tries=$((tries + 1))

        if (( tries >= max_tries )); then
            return 1
        fi

        sleep 2
    done
}

if [[ "$MODE_LC" == "full" ]]; then
    export AI_DISABLED=false
    export MULTIMODAL_PROVIDER=local
    export LLM_FALLBACK_TIMEOUT_SECONDS=40
    start_full
else
    export AI_DISABLED=false
    export MULTIMODAL_PROVIDER=groq
    export LLM_FALLBACK_TIMEOUT_SECONDS=0
    start_lite
fi

print_local_links

if ! fetch_cloudflare_link; then
    echo "ATTENZIONE: link HTTPS Cloudflare non recuperato entro ${MAX_LINK_WAIT_SECONDS} secondi."
    echo
fi

pause
exit 0