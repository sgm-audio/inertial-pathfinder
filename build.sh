#!/bin/bash
# Build and optimize the Sonic Mind Forge container

set -e

echo "🔨 Building optimized Sonic Mind Forge image..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Build with BuildKit for better caching
DOCKER_BUILDKIT=1 docker build \
  -t sonic-mind-forge:optimized \
  -t sonic-mind-forge:latest \
  --progress=plain \
  .

echo ""
echo -e "${GREEN}✓ Build complete${NC}"
echo ""

# Check image size
echo -e "${BLUE}Image Sizes:${NC}"
docker images sonic-mind-forge --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo ""
echo -e "${BLUE}Layer Breakdown:${NC}"
docker history sonic-mind-forge:latest --human --no-trunc | head -15

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Run: docker compose up"
echo "2. Test API: curl http://localhost:8080/health"
echo "3. View stats: docker stats"
echo ""
