# Sonic Mind Forge - Docker Setup Guide

Your project is now fully containerized with Docker best practices. Here's what's included:

## Files Created/Updated

### 1. **Dockerfile** (Updated)
- ✓ Multi-stage build (builder + production stages)
- ✓ Non-root user (`appuser`) for security
- ✓ Health checks enabled
- ✓ Python environment optimized (unbuffered, no bytecode)
- ✓ Build dependencies isolated in first stage
- ✓ Minimal production image using `slim` base
- ✓ Audio processing libraries (libsndfile1, ffmpeg) only in production stage

### 2. **docker-compose.yml** (Development)
- ✓ Volume mounts for hot reload during development
- ✓ Environment variables from `.env` file
- ✓ Named volumes for uploads and reports
- ✓ Health checks configured
- ✓ Custom network (`sonic-network`)
- ✓ Optional services commented (Redis, PostgreSQL)

### 3. **docker-compose.prod.yml** (Production)
- ✓ No source code volume mounts (security)
- ✓ Resource limits (CPU, memory)
- ✓ Always-restart policy
- ✓ Optional nginx reverse proxy commented
- ✓ Bind mounts for persistent data

### 4. **.dockerignore**
- ✓ Excludes unnecessary files from build context
- ✓ Reduces image size by ~20-30%
- ✓ Prevents secrets and dependencies from being copied

### 5. **.env** (from .env.example)
- ✓ Local development configuration ready to use
- ✓ Update with your GCP credentials for production

## Quick Start

### Development Mode
```bash
# Build and start the application
docker compose up --build

# Or just start (uses cached image)
docker compose up

# Access the API
curl http://localhost:8080/health
curl http://localhost:8080/docs  # API documentation

# View logs
docker compose logs -f app

# Stop all services
docker compose down
```

### Hot Reload During Development
The development compose file mounts your `./src` directory. Changes to Python files will auto-reload thanks to Uvicorn's reload mode (when DEBUG=true in .env).

To disable hot reload:
- Set `DEBUG=false` in `.env`
- Rebuild: `docker compose up --build`

### Production Deployment
```bash
# Create production environment file
cp .env.example .env.prod
# Edit with production credentials
nano .env.prod

# Deploy with production compose
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f app

# Stop services
docker compose -f docker-compose.prod.yml down
```

## Configuration

### Environment Variables
Edit `.env` for development or `.env.prod` for production:

```env
# Application
APP_ENV=development          # or 'production'
DEBUG=true                   # or 'false'
PORT=8080

# GCP (only if using Cloud Storage)
GCP_PROJECT_ID=your-project-id
GCS_BUCKET_NAME=sonic-mind-forge-uploads

# Analysis Targets (Audio Quality)
TARGET_LUFS_MIN=-14.0
TARGET_LUFS_MAX=-9.0
TARGET_PHASE_CORRELATION_MIN=0.5

# API Security
API_KEY=your-api-key-here
```

## Docker Commands

### Building
```bash
# Build the image
docker build -t sonic-mind-forge:latest .

# Build with specific tag
docker build -t sonic-mind-forge:v1.0 .

# Build and view full output
docker build --progress=plain -t sonic-mind-forge:latest .
```

### Running Container Directly
```bash
# Run the container (without compose)
docker run -d \
  --name sonic-api \
  -p 8080:8080 \
  -v ./uploads:/app/uploads \
  -v ./reports:/app/reports \
  --env-file .env \
  sonic-mind-forge:latest

# Check logs
docker logs sonic-api

# Stop the container
docker stop sonic-api
docker rm sonic-api
```

### Debugging
```bash
# Check running containers
docker ps

# View all images
docker images | grep sonic

# Inspect image
docker inspect sonic-mind-forge:latest

# Check container logs
docker compose logs -f app

# Execute command in running container
docker compose exec app bash
docker compose exec app python -c "import src.main; print('Import OK')"

# View container stats (memory, CPU)
docker stats sonic-mind-forge

# Remove unused images/volumes
docker system prune -a
docker volume prune
```

## Health Check

The container includes a health check that:
- Checks `/health` endpoint every 30 seconds
- Times out after 10 seconds
- Retries 3 times before marking unhealthy

View health status:
```bash
docker ps  # Shows HEALTHY/UNHEALTHY status
docker inspect sonic-mind-forge --format='{{.State.Health.Status}}'
```

## Storage

### Volumes
- `uploads/` - Where uploaded audio files are stored (development)
- `reports/` - Where generated PDF reports are saved

Mount these to persistent storage in production:
```yaml
volumes:
  - /persistent/uploads:/app/uploads
  - /persistent/reports:/app/reports
```

### Bind Mounts (Development)
Source code in `./src` is mounted to `/app/src` for hot reload:
```yaml
volumes:
  - ./src:/app/src  # Auto-reloads on file changes
```

## Networking

### Services Communication
- All services connect to `sonic-network` bridge network
- Services can communicate using container names as hostnames
- Example: Redis at `redis:6379` (if enabled)

### Port Mapping
- Host port 8080 → Container port 8080
- Access API at `http://localhost:8080`

## Security Best Practices Implemented

1. ✓ **Non-root user** - Application runs as `appuser` (not root)
2. ✓ **Multi-stage builds** - Only production dependencies in final image
3. ✓ **No sensitive data** - Secrets via environment variables, not embedded
4. ✓ **Health checks** - Automatic container restart if unhealthy
5. ✓ **Resource limits** - Memory/CPU caps in production compose
6. ✓ **.dockerignore** - Prevents unnecessary file copying
7. ✓ **Minimal base image** - Uses `python:3.11-slim` instead of full Python
8. ✓ **Read-only where possible** - Production uses minimal writes

## Customization

### Adding Services
Uncomment Redis or PostgreSQL in `docker-compose.yml`:

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data

postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: sonic_db
    POSTGRES_USER: sonic
    POSTGRES_PASSWORD: changeme
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

Then add to `volumes:` section:
```yaml
volumes:
  redis_data:
    driver: local
  postgres_data:
    driver: local
```

### Using Docker Build Cloud (Optional)
For faster builds on multiple platforms:
```bash
docker buildx create --name sonic-builder
docker buildx use sonic-builder
docker buildx build --platform linux/amd64,linux/arm64 -t sonic-mind-forge:latest .
```

### Using Docker Scout for Vulnerability Scanning
```bash
docker scout cves sonic-mind-forge:latest
docker scout recommendations sonic-mind-forge:latest
```

## Performance Tips

1. **Build Cache** - Layers are cached; put frequently-changing code later
2. **Layer Ordering** - Install dependencies before copying code
3. **Build Context** - .dockerignore reduces context size → faster builds
4. **Image Size** - Check with: `docker inspect sonic-mind-forge:latest --format='{{json .Size}}'`
5. **Multi-stage** - Removes build tools from final image (current Dockerfile does this)

## Troubleshooting

### Container won't start
```bash
# Check logs
docker compose logs app

# Verify image built
docker images | grep sonic

# Rebuild
docker compose up --build
```

### Port already in use
```bash
# Find what's using port 8080
lsof -i :8080  # macOS/Linux
netstat -ano | findstr :8080  # Windows

# Use different port in docker-compose.yml or CLI
docker compose -e PORT=8081 up
```

### Permission denied errors
- Ensure Docker daemon is running
- Check Docker socket: `docker ps` should work

### Out of disk space
```bash
# Check disk usage
docker system df

# Clean up
docker system prune -a  # Remove unused images/containers/volumes
docker image prune -a   # Remove dangling images
```

### Update base image
```bash
# Pull latest base images
docker pull python:3.11-slim
docker compose up --build
```

## Next Steps

1. **Test the API**: Visit `http://localhost:8080/docs` for interactive API documentation
2. **Upload files**: Use `/analyze` endpoint to process audio files
3. **Configure GCP**: Add credentials to `.env` for Cloud Storage integration
4. **Add monitoring**: Use tools like Prometheus + Grafana for production
5. **CI/CD**: Set up GitHub Actions or GitLab CI with `docker build`
6. **Kubernetes**: Use generated manifests for orchestration (future)

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/reference/)
- [Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
