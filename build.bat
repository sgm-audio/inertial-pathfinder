@echo off
REM Build and optimize the Sonic Mind Forge container

setlocal enabledelayedexpansion

echo.
echo Building optimized Sonic Mind Forge image...
echo.

REM Build with BuildKit for better caching
set DOCKER_BUILDKIT=1
docker build ^
  -t sonic-mind-forge:optimized ^
  -t sonic-mind-forge:latest ^
  --progress=plain ^
  .

if errorlevel 1 (
    echo Error: Build failed
    exit /b 1
)

echo.
echo === Build complete ===
echo.

echo === Image Sizes ===
docker images sonic-mind-forge --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo.
echo === Layer Breakdown ===
docker history sonic-mind-forge:latest --human --no-trunc | findstr /V "MISSING"

echo.
echo === Next steps ===
echo 1. Run: docker compose up
echo 2. Test API: curl http://localhost:8080/health
echo 3. View stats: docker stats
echo.
