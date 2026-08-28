"""
Sonic Mind Forge - Google Cloud Storage Handler

Manages file uploads/downloads from GCS for the audio analysis pipeline.
"""

import os
import tempfile
from datetime import timedelta
from typing import Optional, Tuple
from pathlib import Path

try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False


class GCSHandler:
    """
    Handle file operations with Google Cloud Storage.
    
    Supports:
    - Downloading audio files for analysis
    - Uploading generated PDF reports
    - Generating signed URLs for secure access
    """
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        uploads_bucket: Optional[str] = None,
        reports_bucket: Optional[str] = None
    ):
        """
        Initialize GCS handler.
        
        Args:
            project_id: GCP project ID (defaults to env var)
            uploads_bucket: Bucket for incoming audio files
            reports_bucket: Bucket for generated reports
        """
        if not GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage is not installed. "
                "Run: pip install google-cloud-storage"
            )
        
        self.project_id = project_id or os.getenv('GCP_PROJECT_ID')
        self.uploads_bucket = uploads_bucket or os.getenv('GCS_BUCKET_NAME', 'sonic-mind-forge-uploads')
        self.reports_bucket = reports_bucket or os.getenv('GCS_REPORTS_BUCKET', 'sonic-mind-forge-reports')
        
        self.client = storage.Client(project=self.project_id)
    
    def download_for_analysis(
        self, 
        blob_name: str, 
        bucket_name: Optional[str] = None
    ) -> Tuple[str, callable]:
        """
        Download a file from GCS to a temporary location.
        
        Args:
            blob_name: Name of the blob in GCS
            bucket_name: Optional bucket override
            
        Returns:
            Tuple of (temp_file_path, cleanup_function)
        """
        bucket_name = bucket_name or self.uploads_bucket
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        if not blob.exists():
            raise FileNotFoundError(f"File not found in GCS: gs://{bucket_name}/{blob_name}")
        
        # Create temp file with correct extension
        suffix = Path(blob_name).suffix or '.wav'
        temp_file = tempfile.NamedTemporaryFile(
            suffix=suffix, 
            delete=False
        )
        temp_path = temp_file.name
        temp_file.close()
        
        # Download
        blob.download_to_filename(temp_path)
        
        # Return path and cleanup function
        def cleanup():
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        return temp_path, cleanup
    
    def upload_report(
        self,
        pdf_bytes: bytes,
        report_name: str,
        bucket_name: Optional[str] = None,
        content_type: str = 'application/pdf'
    ) -> str:
        """
        Upload a PDF report to GCS.
        
        Args:
            pdf_bytes: PDF content as bytes
            report_name: Name for the report file
            bucket_name: Optional bucket override
            content_type: MIME type
            
        Returns:
            GCS URI (gs://bucket/path)
        """
        bucket_name = bucket_name or self.reports_bucket
        bucket = self.client.bucket(bucket_name)
        
        # Ensure .pdf extension
        if not report_name.endswith('.pdf'):
            report_name = f"{report_name}.pdf"
        
        blob = bucket.blob(report_name)
        blob.upload_from_string(pdf_bytes, content_type=content_type)
        
        return f"gs://{bucket_name}/{report_name}"
    
    def get_signed_url(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None,
        expiration_minutes: int = 60
    ) -> str:
        """
        Generate a signed URL for temporary access.
        
        Args:
            blob_name: Name of the blob
            bucket_name: Optional bucket override
            expiration_minutes: URL validity in minutes
            
        Returns:
            Signed URL string
        """
        bucket_name = bucket_name or self.reports_bucket
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
        
        return url
    
    def list_uploads(self, prefix: str = '', bucket_name: Optional[str] = None) -> list:
        """
        List files in the uploads bucket.
        
        Args:
            prefix: Optional path prefix filter
            bucket_name: Optional bucket override
            
        Returns:
            List of blob names
        """
        bucket_name = bucket_name or self.uploads_bucket
        bucket = self.client.bucket(bucket_name)
        
        blobs = bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]
    
    def delete_file(self, blob_name: str, bucket_name: Optional[str] = None) -> bool:
        """
        Delete a file from GCS.
        
        Args:
            blob_name: Name of the blob
            bucket_name: Optional bucket override
            
        Returns:
            True if deleted, False if not found
        """
        bucket_name = bucket_name or self.uploads_bucket
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        try:
            blob.delete()
            return True
        except NotFound:
            return False


class LocalStorageHandler:
    """
    Local file system fallback for development/testing.
    Mirrors the GCSHandler interface.
    """
    
    def __init__(
        self,
        uploads_dir: str = './uploads',
        reports_dir: str = './reports'
    ):
        self.uploads_dir = Path(uploads_dir)
        self.reports_dir = Path(reports_dir)
        
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def download_for_analysis(
        self, 
        blob_name: str, 
        bucket_name: Optional[str] = None
    ) -> Tuple[str, callable]:
        """Get path to local file (no actual download needed)."""
        file_path = self.uploads_dir / blob_name
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # No cleanup needed for local files
        return str(file_path), lambda: None
    
    def upload_report(
        self,
        pdf_bytes: bytes,
        report_name: str,
        bucket_name: Optional[str] = None,
        content_type: str = 'application/pdf'
    ) -> str:
        """Save report to local directory."""
        if not report_name.endswith('.pdf'):
            report_name = f"{report_name}.pdf"
        
        output_path = self.reports_dir / report_name
        
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
        
        return f"file://{output_path.absolute()}"
    
    def get_signed_url(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None,
        expiration_minutes: int = 60
    ) -> str:
        """Return local file path as URL."""
        return f"file://{(self.reports_dir / blob_name).absolute()}"
    
    def list_uploads(self, prefix: str = '', bucket_name: Optional[str] = None) -> list:
        """List local upload files."""
        return [f.name for f in self.uploads_dir.glob(f"{prefix}*")]
    
    def delete_file(self, blob_name: str, bucket_name: Optional[str] = None) -> bool:
        """Delete local file."""
        file_path = self.uploads_dir / blob_name
        if file_path.exists():
            file_path.unlink()
            return True
        return False


def get_storage_handler(use_gcs: bool = None):
    """
    Factory function to get appropriate storage handler.

    Priority: GCS > S3 > Local

    Args:
        use_gcs: Force GCS (True) or local (False). Auto-detect if None.

    Returns:
        GCSHandler, S3Handler, or LocalStorageHandler
    """
    if use_gcs is None:
        use_gcs = GCS_AVAILABLE and bool(os.getenv('GCP_PROJECT_ID'))

    if use_gcs:
        return GCSHandler()

    # Try S3-compatible storage if configured
    s3_endpoint = os.getenv('S3_ENDPOINT_URL')
    s3_bucket = os.getenv('S3_BUCKET_NAME')
    if s3_endpoint or s3_bucket:
        try:
            from .s3_handler import S3Handler
            return S3Handler()
        except ImportError:
            pass  # boto3 not installed

    return LocalStorageHandler()
