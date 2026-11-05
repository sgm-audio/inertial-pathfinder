#!/bin/bash
# Benchmark script for Sonic Mind Forge

set -e

echo "📊 Sonic Mind Forge - Performance Benchmark"
echo ""

# Check if container is running
if ! docker ps | grep -q sonic-mind-forge; then
    echo "❌ Container not running. Start with: docker compose up"
    exit 1
fi

echo "⏱️  Testing health endpoint..."
time curl -s http://localhost:8080/health > /dev/null

echo ""
echo "📈 Container Stats:"
docker stats --no-stream sonic-mind-forge

echo ""
echo "💾 Image Size:"
docker images sonic-mind-forge:latest --format "{{.Repository}}:{{.Tag}}\t{{.Size}}"

echo ""
echo "🔍 Memory Usage:"
docker inspect sonic-mind-forge --format='{{json .State}}' | grep -o '"Pid":[0-9]*' | cut -d: -f2 | xargs -I {} sh -c 'ps aux | grep {} | grep -v grep'

echo ""
echo "📊 Running 100 requests..."
if command -v ab &> /dev/null; then
    ab -n 100 -c 10 http://localhost:8080/health
else
    echo "⚠️  Apache Bench not installed. Install with:"
    echo "  Ubuntu/Debian: sudo apt-get install apache2-utils"
    echo "  macOS: brew install httpd"
    echo "  Or use: docker run -it --rm grafana/k6:latest run /app/load-test.js"
fi
