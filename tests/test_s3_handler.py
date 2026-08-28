"""
Unit tests for the S3-compatible storage handler.
Uses moto to mock S3 — no AWS credentials required.
"""
import os
import tempfile
import pytest
from moto import mock_aws
from src.s3_handler import S3Handler


@pytest.fixture(autouse=True)
def clear_s3_env():
    """Clear S3 env vars between tests to avoid pollution."""
    for key in list(os.environ):
        if key.startswith("S3_") or key.startswith("AWS_"):
            del os.environ[key]
    yield


@pytest.fixture
def s3_handler():
    """Create an S3 handler pointed at a mock moto endpoint."""
    with mock_aws():
        handler = S3Handler(
            region_name="us-east-1",
            uploads_bucket="test-uploads-bucket",
            reports_bucket="test-reports-bucket",
        )
        # Create both buckets
        handler.client.create_bucket(Bucket="test-uploads-bucket")
        handler.client.create_bucket(Bucket="test-reports-bucket")
        yield handler


class TestS3HandlerConstruction:
    """Test S3Handler initialisation."""

    def test_defaults_from_env(self):
        os.environ["S3_BUCKET_NAME"] = "my-uploads"
        os.environ["S3_REPORTS_BUCKET"] = "my-reports"
        os.environ["S3_REGION"] = "eu-west-1"
        with mock_aws():
            h = S3Handler()
            assert h.uploads_bucket == "my-uploads"
            assert h.reports_bucket == "my-reports"
            assert h.region_name == "eu-west-1"

    def test_explicit_overrides_env(self):
        os.environ["S3_BUCKET_NAME"] = "env-uploads"
        os.environ["S3_REPORTS_BUCKET"] = "env-reports"
        with mock_aws():
            h = S3Handler(
                uploads_bucket="explicit-uploads",
                reports_bucket="explicit-reports",
            )
            assert h.uploads_bucket == "explicit-uploads"
            assert h.reports_bucket == "explicit-reports"


class TestS3UploadReport:
    """Test report uploads to S3."""

    def test_upload_returns_s3_uri(self, s3_handler):
        pdf = b"%PDF-1.4 mock content"
        uri = s3_handler.upload_report(pdf, "my-report")
        assert uri.startswith("s3://")
        assert "my-report.pdf" in uri

    def test_upload_ensures_pdf_extension(self, s3_handler):
        pdf = b"test"
        uri = s3_handler.upload_report(pdf, "report-name")
        assert uri.endswith(".pdf")

    def test_uploaded_object_exists(self, s3_handler):
        pdf = b"hello world report data"
        s3_handler.upload_report(pdf, "report1")
        resp = s3_handler.client.get_object(
            Bucket="test-reports-bucket", Key="report1.pdf"
        )
        assert resp["Body"].read() == pdf


class TestS3DownloadForAnalysis:
    """Test downloading files from S3."""

    def test_download_existing_file(self, s3_handler):
        key = "audio/sample.wav"
        # Upload a test file first
        s3_handler.client.put_object(
            Bucket="test-uploads-bucket",
            Key=key,
            Body=b"fake wav data",
        )
        path, cleanup = s3_handler.download_for_analysis(key)
        try:
            with open(path, "rb") as f:
                assert f.read() == b"fake wav data"
        finally:
            cleanup()
            assert not os.path.exists(path)


class TestS3SignedUrls:
    """Test signed URL generation."""

    def test_generates_http_url(self, s3_handler):
        s3_handler.client.put_object(
            Bucket="test-reports-bucket",
            Key="report.pdf",
            Body=b"data",
        )
        url = s3_handler.get_signed_url("report.pdf")
        assert url.startswith("https://") or url.startswith("http://")
        assert "report.pdf" in url


class TestS3ListUploads:
    """Test file listing."""

    def test_lists_files_with_prefix(self, s3_handler):
        for name in ["file1.wav", "file2.wav", "other.txt"]:
            s3_handler.client.put_object(
                Bucket="test-uploads-bucket",
                Key=name,
                Body=b"data",
            )
        files = s3_handler.list_uploads(prefix="file")
        assert "file1.wav" in files
        assert "file2.wav" in files
        assert "other.txt" not in files

    def test_empty_prefix_returns_all(self, s3_handler):
        s3_handler.client.put_object(
            Bucket="test-uploads-bucket",
            Key="a.wav",
            Body=b"data",
        )
        files = s3_handler.list_uploads()
        assert "a.wav" in files


class TestS3DeleteFile:
    """Test file deletion."""

    def test_deletes_existing(self, s3_handler):
        s3_handler.client.put_object(
            Bucket="test-uploads-bucket",
            Key="to-delete.wav",
            Body=b"data",
        )
        result = s3_handler.delete_file("to-delete.wav")
        assert result is True

    def test_delete_nonexistent(self, s3_handler):
        # S3 delete_object does not fail for nonexistent keys;
        # the handler should return True in both cases (no ClientError)
        result = s3_handler.delete_file("nonexistent.wav")
        assert result is True  # S3 returns 204 for nonexistent deletes
