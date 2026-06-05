@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=lite"

if /I "%MODE%"=="lite" goto VALID_MODE
if /I "%MODE%"=="full" goto VALID_MODE

pause
exit /b 1

:VALID_MODE
set "MAX_LINK_WAIT_SECONDS=120"
set "START_LOG=%TEMP%\tarai_compose_start_%RANDOM%.log"
set "CF_LOG=%TEMP%\tarai_cloudflare_logs_%RANDOM%.log"
set "CF_LINK="

echo Mode: %MODE%
echo.

if /I "%MODE%"=="full" (
    set "AI_DISABLED=false"
    call :START_FULL
) else (
    set "AI_DISABLED=true"
    call :START_LITE
)

if errorlevel 1 exit /b 1

call :PRINT_LOCAL_LINKS
call :FETCH_CLOUDFLARE_LINK

pause
exit /b 0

:START_LITE

docker compose stop llm llm-init >nul 2>&1

docker compose up -d --build --force-recreate --no-deps database pgadmin vector-db > "%START_LOG%" 2>&1
if errorlevel 1 goto START_ERROR

call :WAIT_HEALTH tarai-database 120
if errorlevel 1 goto START_ERROR

docker compose up -d --build --force-recreate --no-deps backend frontend cloudflared > "%START_LOG%" 2>&1
if errorlevel 1 goto START_ERROR

exit /b 0

:START_FULL

docker compose up -d --build --force-recreate database pgadmin vector-db llm > "%START_LOG%" 2>&1
if errorlevel 1 goto START_ERROR

call :WAIT_HEALTH tarai-database 120
if errorlevel 1 goto START_ERROR

docker compose up --build --force-recreate llm-init
if errorlevel 1 goto START_ERROR

docker compose up -d --build --force-recreate backend frontend cloudflared > "%START_LOG%" 2>&1
if errorlevel 1 goto START_ERROR

exit /b 0

:START_ERROR
echo ERRORE: avvio Docker Compose non riuscito.
echo.
if exist "%START_LOG%" type "%START_LOG%"
pause
exit /b 1

:PRINT_LOCAL_LINKS
echo Link:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000/docs
echo   pgAdmin:  http://localhost:5050
echo.
exit /b 0

:WAIT_HEALTH
set "SERVICE_NAME=%~1"
set "WAIT_SECONDS=%~2"
set /a health_tries=%WAIT_SECONDS% / 2
set /a health_count=0

:WAIT_HEALTH_LOOP
set "HEALTH_STATUS="
for /f "delims=" %%H in ('docker inspect --format "{{.State.Health.Status}}" %SERVICE_NAME% 2^>nul') do set "HEALTH_STATUS=%%H"

if /I "%HEALTH_STATUS%"=="healthy" (
    exit /b 0
)

set /a health_count+=1
if %health_count% GEQ %health_tries% (
    exit /b 1
)

timeout /t 2 /nobreak >nul
goto WAIT_HEALTH_LOOP

:FETCH_CLOUDFLARE_LINK
for /f "delims=" %%T in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')"') do set "SINCE_UTC=%%T"

docker compose restart cloudflared > "%START_LOG%" 2>&1
if errorlevel 1 (
    exit /b 1
)

set "CF_CONTAINER="
for /f "delims=" %%C in ('docker compose ps -q cloudflared') do set "CF_CONTAINER=%%C"

if not defined CF_CONTAINER (
    exit /b 1
)

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
        exit /b 1
    )
    timeout /t 2 /nobreak >nul
    goto WAIT_LINK
)

echo Link HTTPS Cloudflare:
echo   !CF_LINK!
echo.
exit /b 0