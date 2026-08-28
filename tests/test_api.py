"""
Integration tests for the FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
import numpy as np
import io
import wave
import tempfile
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app


client = TestClient(app)


def create_test_wav(duration_seconds: float = 2.0, sample_rate: int = 44100) -> bytes:
    """Create a simple test WAV file in memory."""
    # Generate a simple sine wave
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
    
    # Mix of frequencies for more interesting analysis
    signal = (
        0.5 * np.sin(2 * np.pi * 440 * t) +    # A4
        0.3 * np.sin(2 * np.pi * 880 * t) +    # A5
        0.2 * np.sin(2 * np.pi * 100 * t)      # Low bass
    )
    
    # Normalize and convert to 16-bit
    signal = signal / np.max(np.abs(signal)) * 0.8
    signal_int = (signal * 32767).astype(np.int16)
    
    # Create stereo (duplicate to both channels)
    stereo = np.column_stack([signal_int, signal_int])
    
    # Write to WAV bytes
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(stereo.tobytes())
    
    return buffer.getvalue()


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check_root(self):
        """Test root endpoint returns health status."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
    
    def test_health_check_endpoint(self):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAnalyzeEndpoint:
    """Test the main /analyze endpoint."""
    
    def test_analyze_valid_wav(self):
        """Test analysis of a valid WAV file."""
        wav_bytes = create_test_wav()
        
        response = client.post(
            "/analyze",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
            params={"generate_report": False}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["filename"] == "test.wav"
        assert "analysis" in data
        assert "processing_time_ms" in data
        
        # Verify analysis structure
        analysis = data["analysis"]
        assert "integrated_lufs" in analysis
        assert "spectral_balance" in analysis
        assert "dynamics" in analysis
        assert "stereo" in analysis
        assert "overall_grade" in analysis
        assert "recommendations" in analysis
    
    def test_analyze_with_report(self):
        """Test analysis with PDF report generation."""
        wav_bytes = create_test_wav()
        
        response = client.post(
            "/analyze",
            files={"file": ("test_report.wav", wav_bytes, "audio/wav")},
            params={"generate_report": True}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["report_url"] is not None
        assert data["report_url"] != ""
        assert "/report/" in data["report_url"]
    
    def test_analyze_invalid_extension(self):
        """Test rejection of invalid file types."""
        response = client.post(
            "/analyze",
            files={"file": ("test.txt", b"not audio data", "text/plain")},
        )
        
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]
    
    def test_analyze_no_file(self):
        """Test error when no file provided."""
        response = client.post("/analyze")
        assert response.status_code == 422  # Validation error


class TestAnalysisQuality:
    """Test the quality of analysis results."""
    
    def test_lufs_reasonable_range(self):
        """Test that LUFS is in a reasonable range."""
        wav_bytes = create_test_wav()
        
        response = client.post(
            "/analyze",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
            params={"generate_report": False}
        )
        
        data = response.json()
        lufs = data["analysis"]["integrated_lufs"]
        
        # Test signal should be in a reasonable range
        assert -50 < lufs < 0, f"LUFS {lufs} is outside reasonable range"
    
    def test_phase_correlation_stereo(self):
        """Test phase correlation for mono-compatible stereo."""
        wav_bytes = create_test_wav()  # Our test creates identical L/R
        
        response = client.post(
            "/analyze",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
            params={"generate_report": False}
        )
        
        data = response.json()
        phase = data["analysis"]["stereo"]["phase_correlation"]
        
        # Identical L/R should have perfect correlation
        assert phase > 0.9, f"Phase correlation {phase} should be high for identical channels"
    
    def test_spectral_balance_present(self):
        """Test that all spectral bands are present."""
        wav_bytes = create_test_wav()
        
        response = client.post(
            "/analyze",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
            params={"generate_report": False}
        )
        
        data = response.json()
        spectral = data["analysis"]["spectral_balance"]
        
        expected_bands = ['sub', 'low', 'low_mid', 'mid', 'high_mid', 'high', 'brightness']
        for band in expected_bands:
            assert band in spectral, f"Missing spectral band: {band}"


class TestN8nWebhook:
    """Test n8n webhook integration."""

    def test_webhook_accepts_payload(self):
        """Test webhook endpoint accepts n8n payload."""
        payload = {
            "gcs_bucket": "test-bucket",
            "gcs_path": "student-uploads/mix.wav",
            "student_email": "student@example.com",
            "student_name": "Test Student"
        }

        response = client.post("/webhook/n8n", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "job_id" in data

    def test_webhook_minimal_payload(self):
        """Test webhook accepts minimal payload (no optional fields)."""
        response = client.post("/webhook/n8n", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    def test_webhook_with_file_url(self):
        """Test webhook with file_url payload."""
        payload = {"file_url": "https://example.com/audio.wav"}
        response = client.post("/webhook/n8n", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_webhook_job_ids_are_unique(self):
        """Test that consecutive requests get unique job IDs."""
        response1 = client.post("/webhook/n8n", json={})
        response2 = client.post("/webhook/n8n", json={})
        assert response1.json()["job_id"] != response2.json()["job_id"]

    def test_webhook_job_id_format(self):
        """Test job ID follows expected format."""
        response = client.post("/webhook/n8n", json={})
        job_id = response.json()["job_id"]
        assert job_id.startswith("job_")
        assert len(job_id) > 15  # timestamp + random hex

    def test_webhook_full_payload(self):
        """Test webhook with all possible fields."""
        payload = {
            "file_url": "https://storage.example.com/file.wav",
            "gcs_bucket": "sonic-mind-forge-uploads",
            "gcs_path": "2024/01/student_upload.wav",
            "student_email": "student@school.edu",
            "student_name": "Jane Doe",
            "upload_token": "tok_abc123",
        }
        response = client.post("/webhook/n8n", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_webhook_rejects_non_json(self):
        """Test webhook rejects non-JSON content type."""
        response = client.post("/webhook/n8n", data="not json")
        assert response.status_code == 422


# Run with: pytest tests/test_api.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
