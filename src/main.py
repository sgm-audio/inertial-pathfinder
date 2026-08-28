"""
Sonic Mind Forge - FastAPI Application

Main API for AI-powered audio analysis and report generation.
Designed for Cloud Run deployment with n8n integration.
"""

import os
import tempfile
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query, Header
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings


# Local imports
from .audio_analyzer import AudioAnalyzer, AnalysisResult
from .report_generator import ReportGenerator, ReportConfig
from .gcs_handler import get_storage_handler, GCS_AVAILABLE


# =============================================================================
# Configuration
# =============================================================================

class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    debug: bool = True
    api_key: Optional[str] = None

    # GCP settings
    gcp_project_id: Optional[str] = None
    gcs_bucket_name: str = "sonic-mind-forge-uploads"
    gcs_reports_bucket: str = "sonic-mind-forge-reports"

    # Analysis targets
    target_lufs_min: float = -14.0
    target_lufs_max: float = -9.0
    target_phase_correlation_min: float = 0.5


settings = Settings()

# =============================================================================
# Logging
# =============================================================================

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sonic-mind-forge")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Sonic Mind Forge",
    description="AI-Powered Audio Analysis API for Music Production",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for web integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
analyzer = AudioAnalyzer(
    lufs_min=settings.target_lufs_min,
    lufs_max=settings.target_lufs_max,
    phase_min=settings.target_phase_correlation_min
)
report_generator = ReportGenerator()


# =============================================================================
# Request/Response Models
# =============================================================================

class AnalysisResponse(BaseModel):
    """Response model for audio analysis."""
    success: bool
    filename: str
    analysis: dict
    report_url: Optional[str] = None
    processing_time_ms: int


class GCSAnalysisRequest(BaseModel):
    """Request to analyze a file from GCS."""
    bucket: str = Field(..., description="GCS bucket name")
    blob_name: str = Field(..., description="Path to file in bucket")
    generate_report: bool = Field(True, description="Generate PDF report")
    callback_url: Optional[str] = Field(None, description="Webhook URL for async callback")


class WebhookPayload(BaseModel):
    """Payload for n8n webhook integration."""
    file_url: Optional[str] = None
    gcs_bucket: Optional[str] = None
    gcs_path: Optional[str] = None
    student_email: Optional[str] = None
    student_name: Optional[str] = None
    upload_token: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    gcs_available: bool
    s3_available: bool = False
    storage_backend: str = "local"
    timestamp: str


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Cloud Run."""
    import os as _os
    s3_available = bool(_os.getenv("S3_ENDPOINT_URL") or _os.getenv("S3_BUCKET_NAME"))
    gcs_ok = GCS_AVAILABLE and bool(settings.gcp_project_id)
    if gcs_ok:
        backend = "gcs"
    elif s3_available:
        backend = "s3"
    else:
        backend = "local"
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        gcs_available=gcs_ok,
        s3_available=s3_available,
        storage_backend=backend,
        timestamp=datetime.now(tz=timezone.utc).isoformat()
    )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_upload(
    file: UploadFile = File(..., description="Audio file to analyze (WAV, MP3, FLAC)"),
    generate_report: bool = Query(True, description="Generate PDF report"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Analyze an uploaded audio file.
    
    Accepts WAV, MP3, FLAC, and other common audio formats.
    Returns analysis metrics and optionally generates a PDF report.
    """
    # Simple API key check (optional)
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    start_time = datetime.now()
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    allowed_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.aiff', '.m4a'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {allowed_extensions}"
        )
    
    # Save to temp file for processing
    temp_file = None
    try:
        temp_file = tempfile.NamedTemporaryFile(
            suffix=file_ext,
            delete=False
        )
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        logger.info(f"Analyzing file: {file.filename} ({len(content)} bytes)")
        
        # Run analysis
        result = analyzer.analyze(temp_file.name)
        
        # Generate report if requested
        report_url = None
        if generate_report:
            pdf_bytes = report_generator.generate(
                result,
                filename=file.filename
            )
            
            # Store report (uses GCS, S3, or local based on config)
            storage = get_storage_handler()
            report_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(file.filename).stem}"
            report_uri = storage.upload_report(pdf_bytes, report_name)
            
            # Get signed URL for cloud storage backends
            if 'gs://' in report_uri or 's3://' in report_uri:
                report_url = storage.get_signed_url(f"{report_name}.pdf")
            elif 'file://' in report_uri:
                report_url = f"/report/{report_name}.pdf"
            else:
                report_url = report_uri
        
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return AnalysisResponse(
            success=True,
            filename=file.filename,
            analysis=result.to_dict(),
            report_url=report_url,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup temp file
        if temp_file and os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


@app.post("/analyze-from-gcs", response_model=AnalysisResponse)
async def analyze_from_gcs(
    request: GCSAnalysisRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Analyze a file stored in Google Cloud Storage.
    
    This endpoint is optimized for n8n webhook integrations where
    files are already uploaded to GCS.
    """
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not GCS_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="GCS not available. Use /analyze endpoint for direct uploads."
        )
    
    start_time = datetime.now()
    cleanup = None
    
    try:
        storage = get_storage_handler(use_gcs=True)
        
        # Download file
        temp_path, cleanup = storage.download_for_analysis(
            request.blob_name,
            request.bucket
        )
        
        logger.info(f"Analyzing GCS file: gs://{request.bucket}/{request.blob_name}")
        
        # Run analysis
        result = analyzer.analyze(temp_path)
        
        # Generate report if requested
        report_url = None
        if request.generate_report:
            pdf_bytes = report_generator.generate(
                result,
                filename=request.blob_name
            )
            
            report_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(request.blob_name).stem}"
            storage.upload_report(pdf_bytes, report_name)
            report_url = storage.get_signed_url(f"{report_name}.pdf")
        
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return AnalysisResponse(
            success=True,
            filename=request.blob_name,
            analysis=result.to_dict(),
            report_url=report_url,
            processing_time_ms=processing_time
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"GCS analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cleanup:
            cleanup()


@app.post("/webhook/n8n")
async def n8n_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    n8n webhook endpoint for automated analysis pipeline.
    
    Accepts file information and queues analysis as a background task.
    Returns immediately with a job ID for tracking.
    """
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
    
    logger.info(f"Received n8n webhook: {job_id}")
    logger.info(f"Payload: {payload}")
    
    # For now, return acknowledgment
    # In production, add to background task queue
    return JSONResponse({
        "status": "queued",
        "job_id": job_id,
        "message": "Analysis queued successfully"
    })


@app.get("/report/{report_name}")
async def get_report(
    report_name: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Download a generated PDF report.
    
    Returns the PDF file directly or redirects to signed URL.
    """
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    storage = get_storage_handler()
    
    try:
        if GCS_AVAILABLE and settings.gcp_project_id:
            # Return signed URL for GCS
            url = storage.get_signed_url(report_name)
            return JSONResponse({"url": url})
        else:
            # Read from local storage
            report_path = Path('./reports') / report_name
            if not report_path.exists():
                raise HTTPException(status_code=404, detail="Report not found")
            
            with open(report_path, 'rb') as f:
                pdf_content = f.read()
            
            return Response(
                content=pdf_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={report_name}"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.debug,
        reload_dirs=["src"],
        log_level="debug" if settings.debug else "info"
    )
