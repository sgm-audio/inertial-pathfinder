# Sonic Mind Forge Deployment Guide

Step-by-step instructions for deploying the AI Audio Analysis platform to Google Cloud Platform.

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed locally (for testing)
- n8n instance (Cloud Run or self-hosted)

## Quick Start (Local Development)

```bash
# 1. Clone and enter directory
cd inertial-pathfinder

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config
copy .env.example .env

# 5. Run the server
uvicorn src.main:app --reload --port 8000

# 6. Open API docs
# http://localhost:8000/docs
```

## GCP Deployment

### Step 1: Set Up GCP Project

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  sql.googleapis.com
```

### Step 2: Create GCS Buckets

```bash
# Create buckets for audio uploads and reports
gcloud storage buckets create gs://sonic-mind-forge-uploads \
  --location=us-central1 \
  --uniform-bucket-level-access

gcloud storage buckets create gs://sonic-mind-forge-reports \
  --location=us-central1 \
  --uniform-bucket-level-access
```

### Step 3: Deploy to Cloud Run

```bash
# Build and push container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/sonic-mind-forge

# Deploy to Cloud Run
gcloud run deploy sonic-mind-forge \
  --image gcr.io/YOUR_PROJECT_ID/sonic-mind-forge \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars "GCP_PROJECT_ID=YOUR_PROJECT_ID,GCS_BUCKET_NAME=sonic-mind-forge-uploads,GCS_REPORTS_BUCKET=sonic-mind-forge-reports,TARGET_LUFS_MIN=-14.0,TARGET_LUFS_MAX=-9.0,TARGET_PHASE_CORRELATION_MIN=0.5"
```

### Step 4: Set Up Service Account

```bash
# Create service account for Cloud Run
gcloud iam service-accounts create sonic-mind-forge-sa \
  --display-name="Sonic Mind Forge Service Account"

# Grant GCS access
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:sonic-mind-forge-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

## n8n Setup

### Option A: n8n on Cloud Run

```bash
# Deploy n8n to Cloud Run
gcloud run deploy n8n \
  --image n8nio/n8n \
  --platform managed \
  --region us-central1 \
  --memory 1Gi \
  --set-env-vars "N8N_BASIC_AUTH_ACTIVE=true,N8N_BASIC_AUTH_USER=admin,N8N_BASIC_AUTH_PASSWORD=your-secure-password"
```

### Option B: n8n on Compute Engine

For persistent workflows with Cloud SQL backend:

```bash
# Create VM
gcloud compute instances create n8n-server \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=cos-stable \
  --image-project=cos-cloud

# SSH and run Docker
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  -e N8N_BASIC_AUTH_ACTIVE=true \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=your-password \
  n8nio/n8n
```

### Import Workflows

1. Open n8n UI
2. Go to **Settings > Import from File**
3. Import each workflow:
   - `workflows/ai_grader.json`
   - `workflows/gatekeeper.json`
   - `workflows/content_engine.json`
4. Configure credentials for each service

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Your GCP project | `my-project-123` |
| `GCS_BUCKET_NAME` | Upload bucket | `sonic-mind-forge-uploads` |
| `GCS_REPORTS_BUCKET` | Reports bucket | `sonic-mind-forge-reports` |
| `API_KEY` | Optional API key | `your-secure-key` |
| `TARGET_LUFS_MIN` | Min LUFS target | `-14.0` |
| `TARGET_LUFS_MAX` | Max LUFS target | `-9.0` |
| `TARGET_PHASE_CORRELATION_MIN` | Min phase correlation | `0.5` |

## Testing the Deployment

```bash
# Health check
curl https://your-cloud-run-url/health

# Test analysis (with file)
curl -X POST https://your-cloud-run-url/analyze \
  -F "file=@test_mix.wav" \
  -F "generate_report=true"

# Test from GCS
curl -X POST https://your-cloud-run-url/analyze-from-gcs \
  -H "Content-Type: application/json" \
  -d '{"bucket": "sonic-mind-forge-uploads", "blob_name": "test.wav"}'
```

## Monitoring

```bash
# View Cloud Run logs
gcloud run logs read sonic-mind-forge --limit 50

# Set up Cloud Monitoring alert
gcloud alpha monitoring policies create \
  --notification-channels=your-channel \
  --display-name="Sonic Mind Forge Errors" \
  --condition-filter='resource.type="cloud_run_revision" AND severity>=ERROR'
```

## Cost Estimation

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Cloud Run | 1000 analyses @ 30s each | ~$5 |
| Cloud Storage | 10GB audio + reports | ~$2 |
| Cloud SQL (if using n8n) | db-f1-micro | ~$10 |
| **Total** | | **~$17-20/month** |

*Actual costs depend on usage. First 2M Cloud Run requests/month are free.*
