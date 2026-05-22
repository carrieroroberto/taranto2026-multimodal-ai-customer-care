@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "CLOUDFLARE_SERVICE=cloudflared"
set "MAX_LINK_WAIT_SECONDS=120"

set "START_LOG=%TEMP%\compose_start_%RANDOM%.log"
set "CF_LOG=%TEMP%\cloudflare_logs_%RANDOM%.log"
set "CF_LINK="

REM 1) Avvia frontend, vector-db e cloudflared senza dipendenze.
docker compose up -d --no-deps frontend vector-db %CLOUDFLARE_SERVICE% > "%START_LOG%" 2>&1
if errorlevel 1 (
    echo ERRORE: docker compose up non riuscito.
    echo.
    type "%START_LOG%"
    echo.
    pause
    exit /b 1
)

REM 2) Salva il timestamp appena prima del restart, per leggere solo i log nuovi.
for /f "delims=" %%T in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')"') do set "SINCE_UTC=%%T"

REM 3) Riavvia cloudflared.
docker compose restart %CLOUDFLARE_SERVICE% > "%START_LOG%" 2>&1
if errorlevel 1 (
    echo ERRORE: docker compose restart %CLOUDFLARE_SERVICE% non riuscito.
    echo.
    type "%START_LOG%"
    echo.
    echo Controlla che il servizio nel docker-compose.yml si chiami "%CLOUDFLARE_SERVICE%".
    echo.
    pause
    exit /b 1
)

REM 4) Recupera l'ID del container cloudflared.
set "CF_CONTAINER="
for /f "delims=" %%C in ('docker compose ps -q %CLOUDFLARE_SERVICE%') do set "CF_CONTAINER=%%C"

if not defined CF_CONTAINER (
    echo ERRORE: container %CLOUDFLARE_SERVICE% non trovato.
    pause
    exit /b 1
)

REM 5) Legge i log dopo il restart ed estrae il link trycloudflare.com.
set /a tries=0
set /a max_tries=%MAX_LINK_WAIT_SECONDS% / 2
set "CF_LOG_FILE=%CF_LOG%"

:WAIT_LINK
docker logs --since "%SINCE_UTC%" --tail 300 "%CF_CONTAINER%" > "%CF_LOG%" 2>&1

for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$text = Get-Content -Raw $env:CF_LOG_FILE -ErrorAction SilentlyContinue; $matches = [regex]::Matches($text, 'https://[A-Za-z0-9-]+\.trycloudflare\.com'); if ($matches.Count -gt 0) { $matches[$matches.Count - 1].Value }"`) do (
    set "CF_LINK=%%A"
)

if not defined CF_LINK (
    set /a tries+=1
    if !tries! GEQ !max_tries! (
        echo ERRORE: link Cloudflare non trovato entro %MAX_LINK_WAIT_SECONDS% secondi.
        echo.
        echo Ultimi log Cloudflare:
        type "%CF_LOG%"
        echo.
        pause
        exit /b 1
    )
    timeout /t 2 /nobreak >nul
    goto WAIT_LINK
)

echo !CF_LINK!

pause
