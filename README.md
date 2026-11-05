# Sonic Mind Forge (inertial-pathfinder)

An audio analysis API for mix feedback in music lessons. A student uploads a mix and gets back a report with loudness, phase correlation, spectral balance and dynamics numbers, plus rule-based recommendations as JSON and a PDF. There's no AI model in the analysis. It's librosa, pyloudnorm and fixed thresholds.

## What it measures

- **Integrated loudness**: pyloudnorm (ITU-R BS.1770-4 K-weighting and gating)
- **Spectral balance**: energy share in six bands (sub, low, low-mid, mid, high-mid, high)
- **Phase correlation**: L/R correlation, as a mono-compatibility check
- **Crest factor**: peak minus RMS in dB
- **"Dynamic range"**: the 95th minus 10th percentile of 400 ms RMS windows. It's a rough stand-in for loudness range, not EBU R128 LRA (no K-weighting or gating), so don't compare it to LRA from a meter.
- **PDF report**: built with `report_generator.py`
- **Storage**: GCS or S3 for uploads and reports
- **n8n**: example workflows in `workflows/`

Tests: `pytest -q tests` gives 95 passed (Python 3.12, Linux x86_64, Oct 2026).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (limit reload watch to src/ to avoid venv churn)
uvicorn src.main:app --reload --reload-dir src

# Open API docs
open http://localhost:8000/docs
```

## Project Structure

```
├── src/
│   ├── main.py              # FastAPI application
│   ├── audio_analyzer.py    # Core analysis engine
│   ├── report_generator.py  # PDF generation
│   ├── gcs_handler.py       # GCS integration
│   └── s3_handler.py        # S3 integration
├── workflows/
│   ├── ai_grader.json       # n8n: Upload → Analyze → Email
│   ├── gatekeeper.json      # n8n: Sales automation
│   └── content_engine.json  # n8n: Content repurposing
├── tests/
├── Dockerfile
├── requirements.txt
└── DEPLOYMENT.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/analyze` | POST | Upload and analyze audio |
| `/analyze-from-gcs` | POST | Analyze from GCS bucket |
| `/webhook/n8n` | POST | n8n integration webhook |
| `/report/{name}` | GET | Download PDF report |

## Analysis Metrics

```json
{
  "integrated_lufs": -11.2,
  "phase_correlation": 0.87,
  "spectral_balance": {
    "sub": 8.2,
    "low": 22.1,
    "low_mid": 15.3,
    "mid": 28.4,
    "high_mid": 18.7,
    "high": 7.3
  },
  "dynamics": {
    "crest_factor_db": 8.5,
    "dynamic_range_db": 6.2
  },
  "overall_grade": "GOOD",
  "recommendations": [...]
}
```

## n8n Workflows

### 1. AI Grader (`ai_grader.json`)
`Webhook → GCS Upload → Analyze → Email Report`

### 2. Gatekeeper (`gatekeeper.json`)
`Stripe Payment → Split Funds → Teachable Enroll → Discord Role → Token Gen`

### 3. Content Engine (`content_engine.json`)
`YouTube Upload → LLM Analysis → FFmpeg Crop → Social Upload`

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for full GCP setup instructions.

```bash
# Quick deploy to Cloud Run
gcloud run deploy sonic-mind-forge \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

## Cost

Costs vary with cloud provider and usage volume. See [DEPLOYMENT.md](./DEPLOYMENT.md) for cloud resource sizing guidance.

## License

MIT. See [LICENSE](LICENSE).

---

Built for [Sonic Mind Forge](https://sonicmindforge.com).
