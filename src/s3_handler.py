"""
Sonic Mind Forge - S3-Compatible Storage Handler

Cloud-provider-agnostic storage supporting:
- AWS S3
- MinIO (self-hosted)
- Cloudflare R2
- Backblaze B2
- Any S3-compatible object store

Usage:
    export S3_ENDPOINT_URL=https://s3.amazonaws.com
    export S3_BUCKET_NAME=sonic-mind-forge-uploads
    export S3_REPORTS_BUCKET=sonic-mind-forge-reports
    export S3_REGION=us-east-1
    # For AWS: uses default credential chain (env, ~/.aws/credentials, IAM)
    # For MinIO: also set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
"""

import os
import tempfile
from typing import Optional, Tuple
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


class S3Handler:
    """
    Handle file operations with any S3-compatible object store.
    Mirrors the GCSHandler interface for drop-in replacement.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        uploads_bucket: Optional[str] = None,
        reports_bucket: Optional[str] = None,
    ):
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.region_name = region_name or os.getenv("S3_REGION", "us-east-1")
        self.uploads_bucket = uploads_bucket or os.getenv(
            "S3_BUCKET_NAME", "sonic-mind-forge-uploads"
        )
        self.reports_bucket = reports_bucket or os.getenv(
            "S3_REPORTS_BUCKET", "sonic-mind-forge-reports"
        )

        session = boto3.Session(region_name=self.region_name)
        self.client = session.client(
            "s3",
            endpoint_url=self.endpoint_url if self.endpoint_url else None,
        )

    def download_for_analysis(
        self, blob_name: str, bucket_name: Optional[str] = None
    ) -> Tuple[str, callable]:
        bucket = bucket_name or self.uploads_bucket
        suffix = Path(blob_name).suffix or ".wav"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        tmp.close()

        self.client.download_file(bucket, blob_name, tmp_path)

        def cleanup():
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return tmp_path, cleanup

    def upload_report(
        self,
        pdf_bytes: bytes,
        report_name: str,
        bucket_name: Optional[str] = None,
        content_type: str = "application/pdf",
    ) -> str:
        bucket = bucket_name or self.reports_bucket
        if not report_name.endswith(".pdf"):
            report_name = f"{report_name}.pdf"
        self.client.put_object(
            Bucket=bucket,
            Key=report_name,
            Body=pdf_bytes,
            ContentType=content_type,
        )
        return f"s3://{bucket}/{report_name}"

    def get_signed_url(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None,
        expiration_minutes: int = 60,
    ) -> str:
        bucket = bucket_name or self.reports_bucket
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": blob_name},
            ExpiresIn=expiration_minutes * 60,
        )
        return url

    def list_uploads(
        self, prefix: str = "", bucket_name: Optional[str] = None
    ) -> list:
        bucket = bucket_name or self.uploads_bucket
        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        names = []
        for page in pages:
            for obj in page.get("Contents", []):
                names.append(obj["Key"])
        return names

    def delete_file(
        self, blob_name: str, bucket_name: Optional[str] = None
    ) -> bool:
        bucket = bucket_name or self.uploads_bucket
        try:
            self.client.delete_object(Bucket=bucket, Key=blob_name)
            return True
        except ClientError:
            return False
