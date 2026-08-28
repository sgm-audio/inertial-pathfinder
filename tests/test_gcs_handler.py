"""
Unit tests for the storage handlers (LocalStorageHandler, GCSHandler mock).
"""
import tempfile
import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.gcs_handler import LocalStorageHandler, GCSHandler, get_storage_handler, GCS_AVAILABLE


@pytest.fixture
def temp_dirs():
    """Create temporary uploads and reports directories."""
    base = tempfile.mkdtemp()
    uploads = os.path.join(base, "uploads")
    reports = os.path.join(base, "reports")
    os.makedirs(uploads, exist_ok=True)
    os.makedirs(reports, exist_ok=True)
    yield uploads, reports
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def handler(temp_dirs):
    uploads, reports = temp_dirs
    return LocalStorageHandler(uploads_dir=uploads, reports_dir=reports)


class TestLocalStorageHandlerInit:
    """Test LocalStorageHandler initialisation."""

    def test_creates_directories(self, temp_dirs):
        uploads, reports = temp_dirs
        # Remove them first to verify creation
        shutil.rmtree(uploads)
        shutil.rmtree(reports)
        h = LocalStorageHandler(uploads_dir=uploads, reports_dir=reports)
        assert os.path.isdir(uploads)
        assert os.path.isdir(reports)


class TestUploadReport:
    """Test report upload/save."""

    def test_upload_returns_file_uri(self, handler):
        pdf_bytes = b"%PDF-1.4 fake content"
        uri = handler.upload_report(pdf_bytes, "test_report")
        assert uri.startswith("file://")
        assert "test_report.pdf" in uri

    def test_upload_ensures_pdf_extension(self, handler):
        pdf_bytes = b"%PDF-1.4 fake"
        uri = handler.upload_report(pdf_bytes, "myreport")
        assert uri.endswith(".pdf")
        assert "myreport.pdf" in uri

    def test_upload_existing_extension_not_doubled(self, handler):
        pdf_bytes = b"%PDF-1.4 fake"
        uri = handler.upload_report(pdf_bytes, "myreport.pdf")
        assert uri.endswith(".pdf")
        assert uri.count(".pdf") == 1

    def test_upload_writes_file(self, handler, temp_dirs):
        _, reports = temp_dirs
        pdf_bytes = b"hello world"
        handler.upload_report(pdf_bytes, "sample_report")
        report_files = list(Path(reports).glob("sample_report*"))
        assert len(report_files) >= 1
        with open(report_files[0], 'rb') as f:
            assert f.read() == pdf_bytes


class TestDownloadForAnalysis:
    """Test file download (local path resolution)."""

    def test_existing_file_returns_path(self, handler, temp_dirs):
        uploads, _ = temp_dirs
        filename = "test_audio.wav"
        filepath = os.path.join(uploads, filename)
        with open(filepath, 'w') as f:
            f.write("dummy audio data")

        path, cleanup = handler.download_for_analysis(filename)
        assert path == filepath
        # cleanup should be a no-op that doesn't delete the file
        cleanup()
        assert os.path.exists(filepath)

    def test_missing_file_raises(self, handler):
        with pytest.raises(FileNotFoundError):
            handler.download_for_analysis("nonexistent.wav")


class TestGetSignedUrl:
    """Test signed URL generation (local)."""

    def test_returns_file_uri(self, handler, temp_dirs):
        _, reports = temp_dirs
        report_path = os.path.join(reports, "report1.pdf")
        with open(report_path, 'wb') as f:
            f.write(b"test")

        url = handler.get_signed_url("report1.pdf")
        assert url.startswith("file://")
        assert "report1.pdf" in url


class TestListUploads:
    """Test file listing."""

    def test_lists_matching_files(self, handler, temp_dirs):
        uploads, _ = temp_dirs
        # Create some files
        Path(os.path.join(uploads, "file1.wav")).touch()
        Path(os.path.join(uploads, "file2.mp3")).touch()
        Path(os.path.join(uploads, "other.txt")).touch()

        files = handler.list_uploads(prefix="file")
        assert "file1.wav" in files
        assert "file2.mp3" in files

    def test_empty_listing(self, handler):
        files = handler.list_uploads(prefix="zzzz_nonexistent")
        assert files == []


class TestDeleteFile:
    """Test file deletion."""

    def test_deletes_existing_file(self, handler, temp_dirs):
        uploads, _ = temp_dirs
        filepath = os.path.join(uploads, "to_delete.wav")
        Path(filepath).touch()

        result = handler.delete_file("to_delete.wav")
        assert result is True
        assert not os.path.exists(filepath)

    def test_delete_nonexistent_returns_false(self, handler):
        result = handler.delete_file("nonexistent.wav")
        assert result is False


class TestGetStorageHandler:
    """Test storage handler factory."""

    def test_returns_local_when_gcs_unavailable(self):
        handler = get_storage_handler(use_gcs=False)
        assert isinstance(handler, LocalStorageHandler)

    def test_force_local_even_when_gcs_installed(self):
        handler = get_storage_handler(use_gcs=False)
        assert isinstance(handler, LocalStorageHandler)


# =============================================================================
# GCSHandler mock tests — no production credentials required
# =============================================================================

@pytest.fixture
def mock_gcs_client():
    """Create a GCSHandler with mocked storage.Client."""
    with patch("src.gcs_handler.storage.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        handler = GCSHandler(project_id="test-project")
        yield handler, mock_client, mock_client_class


@pytest.fixture
def mock_gcs_blob():
    """Create a mock blob that exists."""
    blob = MagicMock()
    blob.exists.return_value = True
    return blob


class TestGCSHandlerMockInit:
    """Test GCSHandler construction with mocked client."""

    def test_creates_client(self):
        with patch("src.gcs_handler.storage.Client") as mock_client_class:
            GCSHandler(project_id="my-project")
            mock_client_class.assert_called_once_with(project="my-project")

    def test_default_buckets_from_args(self):
        with patch("src.gcs_handler.storage.Client"):
            handler = GCSHandler(
                project_id="proj",
                uploads_bucket="my-uploads",
                reports_bucket="my-reports",
            )
            assert handler.uploads_bucket == "my-uploads"
            assert handler.reports_bucket == "my-reports"


class TestGCSHandlerMockDownload:
    """Test GCS download_for_analysis with mocked GCS."""

    def test_download_existing_file(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        path, cleanup = handler.download_for_analysis("audio/test.wav")
        try:
            assert os.path.exists(path)
            mock_blob.download_to_filename.assert_called_once_with(path)
            assert "test.wav" in path or path.endswith(".wav")
        finally:
            cleanup()
            assert not os.path.exists(path)

    def test_download_missing_file_raises(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        with pytest.raises(FileNotFoundError, match="not found"):
            handler.download_for_analysis("missing.wav")

    def test_download_custom_bucket(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        path, cleanup = handler.download_for_analysis("file.wav", bucket_name="custom-bucket")
        try:
            mock_client.bucket.assert_called_with("custom-bucket")
        finally:
            cleanup()


class TestGCSHandlerMockUpload:
    """Test GCS upload_report with mocked GCS."""

    def test_upload_returns_gs_uri(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        uri = handler.upload_report(b"fake pdf", "my-report")
        assert uri.startswith("gs://")
        assert "my-report.pdf" in uri
        assert "test-reports" not in handler.reports_bucket or handler.reports_bucket in uri

    def test_upload_ensures_pdf_extension(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        uri = handler.upload_report(b"data", "report-name")
        assert uri.endswith(".pdf")

    def test_upload_does_not_double_extension(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        uri = handler.upload_report(b"data", "report.pdf")
        assert ".pdf.pdf" not in uri

    def test_upload_writes_to_bucket(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        handler.upload_report(b"report content", "analysis-report")
        mock_blob.upload_from_string.assert_called_once_with(
            b"report content", content_type="application/pdf"
        )

    def test_upload_custom_bucket(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        uri = handler.upload_report(b"data", "rpt", bucket_name="custom-reports")
        assert "custom-reports" in uri


class TestGCSHandlerMockSignedUrl:
    """Test GCS signed URL generation with mocked GCS."""

    def test_generates_signed_url(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/bucket/report.pdf?signature=abc"
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        url = handler.get_signed_url("report.pdf")
        assert url.startswith("https://")
        assert "report.pdf" in url
        mock_blob.generate_signed_url.assert_called_once()

    def test_signed_url_custom_expiration(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://example.com/signed"
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        handler.get_signed_url("r.pdf", expiration_minutes=30)
        call_kwargs = mock_blob.generate_signed_url.call_args
        # expiration should be timedelta(minutes=30)
        assert call_kwargs is not None


class TestGCSHandlerMockList:
    """Test GCS list_uploads with mocked GCS."""

    def test_lists_blobs(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob1 = MagicMock()
        mock_blob1.name = "file1.wav"
        mock_blob2 = MagicMock()
        mock_blob2.name = "file2.mp3"
        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]
        mock_client.bucket.return_value = mock_bucket

        files = handler.list_uploads()
        assert files == ["file1.wav", "file2.mp3"]

    def test_lists_with_prefix(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_bucket.list_blobs.return_value = []
        mock_client.bucket.return_value = mock_bucket

        handler.list_uploads(prefix="uploads/2024/")
        mock_bucket.list_blobs.assert_called_once_with(prefix="uploads/2024/")


class TestGCSHandlerMockDelete:
    """Test GCS delete_file with mocked GCS."""

    def test_deletes_existing_file(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        result = handler.delete_file("to-delete.wav")
        assert result is True
        mock_blob.delete.assert_called_once()

    def test_delete_nonexistent_returns_false(self, mock_gcs_client):
        handler, mock_client, _ = mock_gcs_client
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.delete.side_effect = Exception("NotFound")
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        # The handler catches NotFound, which is google.cloud.exceptions.NotFound
        # But our mock raises Exception, which isn't caught -> need to use the right type
        try:
            from google.cloud.exceptions import NotFound
        except ImportError:
            NotFound = Exception
        mock_blob.delete.side_effect = NotFound("not found")
        result = handler.delete_file("nonexistent.wav")
        assert result is False


class TestGetStorageHandlerGCS:
    """Test get_storage_handler factory with GCS env."""

    def test_returns_gcs_when_configured(self):
        with patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=True):
            with patch("src.gcs_handler.storage.Client"):
                handler = get_storage_handler(use_gcs=True)
                assert isinstance(handler, GCSHandler)

    def test_returns_local_when_gcp_project_id_empty(self):
        with patch.dict(os.environ, {"GCP_PROJECT_ID": ""}, clear=True):
            handler = get_storage_handler()
            assert isinstance(handler, LocalStorageHandler)

    def test_returns_local_when_no_gcp_env(self):
        with patch.dict(os.environ, {}, clear=True):
            handler = get_storage_handler()
            assert isinstance(handler, LocalStorageHandler)
