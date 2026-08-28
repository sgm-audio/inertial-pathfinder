# 🎧 Sonic Mind Forge

**Zero-Touch AI Audio Analysis Platform**

Automated audio grading for music education. Students upload mixes, receive instant AI-powered analysis reports with LUFS, phase correlation, spectral balance, and professional recommendations.

## ⚡ Features

- **🔊 LUFS Analysis** - Integrated loudness measurement (ITU-R BS.1770-4)
- **📊 Spectral Balance** - Frequency band energy distribution
- **🎚️ Phase Correlation** - Mono compatibility detection
- **🎛️ Dynamic Range** - Crest factor and LRA analysis
- **📄 PDF Reports** - Professional branded reports
- **☁️ GCS Integration** - Cloud-native file handling
- **🔗 n8n Ready** - Pre-built automation workflows

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (limit reload watch to src/ to avoid venv churn)
uvicorn src.main:app --reload --reload-dir src

# Open API docs
open http://localhost:8000/docs
```

## 📁 Project Structure

```
├── src/
│   ├── main.py              # FastAPI application
│   ├── audio_analyzer.py    # Core analysis engine
│   ├── report_generator.py  # PDF generation
│   └── gcs_handler.py       # GCS integration
├── workflows/
│   ├── ai_grader.json       # n8n: Upload → Analyze → Email
│   ├── gatekeeper.json      # n8n: Sales automation
│   └── content_engine.json  # n8n: Content repurposing
├── tests/
├── Dockerfile
├── requirements.txt
└── DEPLOYMENT.md
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/analyze` | POST | Upload and analyze audio |
| `/analyze-from-gcs` | POST | Analyze from GCS bucket |
| `/webhook/n8n` | POST | n8n integration webhook |
| `/report/{name}` | GET | Download PDF report |

## 📊 Analysis Metrics

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

## 🔧 n8n Workflows

### 1. AI Grader (`ai_grader.json`)
`Webhook → GCS Upload → Analyze → Email Report`

### 2. Gatekeeper (`gatekeeper.json`)
`Stripe Payment → Split Funds → Teachable Enroll → Discord Role → Token Gen`

### 3. Content Engine (`content_engine.json`)
`YouTube Upload → LLM Analysis → FFmpeg Crop → Social Upload`

## ☁️ Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for full GCP setup instructions.

```bash
# Quick deploy to Cloud Run
gcloud run deploy sonic-mind-forge \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

## 📈 Cost

Costs vary with cloud provider and usage volume. See [DEPLOYMENT.md](./DEPLOYMENT.md) for cloud resource sizing guidance.

## 📜 License

MIT

---

Built for [Sonic Mind Forge](https://sonicmindforge.com) • Zero-Touch Music Education
