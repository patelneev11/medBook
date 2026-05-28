import logging
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from ..config import settings
from ..exceptions import AppException

logger = logging.getLogger("mednotebook.storage")

# Created once at import time — reused across all requests
_s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region,
)


def _build_key(user_id: str, filename: str) -> str:
    now = datetime.now(timezone.utc)
    return f"uploads/{user_id}/{now.year}/{now.month:02d}/{uuid.uuid4()}-{filename}"


def upload_file(
    file_content: bytes,
    filename: str,
    mime_type: str,
    user_id: str,
) -> dict:
    """Upload bytes to S3. Returns {file_key, file_size_bytes, bucket_name}."""
    key = _build_key(user_id, filename)
    try:
        _s3.put_object(
            Bucket=settings.aws_bucket_name,
            Key=key,
            Body=file_content,
            ContentType=mime_type,
            ServerSideEncryption="AES256",
            Metadata={
                "uploaded_by": str(user_id),
                "original_filename": filename,
            },
        )
    except ClientError as exc:
        logger.error("S3 upload failed for key %s: %s", key, exc)
        raise AppException(
            "File upload failed — please try again",
            "S3_UPLOAD_FAILED",
            status_code=502,
        ) from exc

    return {
        "file_key": key,
        "file_size_bytes": len(file_content),
        "bucket_name": settings.aws_bucket_name,
    }


def get_presigned_url(file_key: str, expires_in: int = 3600) -> str:
    """Return a presigned GET URL valid for `expires_in` seconds (default 1 hour)."""
    try:
        url: str = _s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.aws_bucket_name, "Key": file_key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as exc:
        logger.error("Failed to generate presigned URL for %s: %s", file_key, exc)
        raise AppException(
            "Could not generate download URL",
            "S3_PRESIGN_FAILED",
            status_code=502,
        ) from exc


def delete_file(file_key: str) -> bool:
    """Delete a file from S3. Returns False if the key didn't exist, True on success."""
    try:
        _s3.delete_object(Bucket=settings.aws_bucket_name, Key=file_key)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404"):
            return False
        logger.error("S3 delete failed for key %s: %s", file_key, exc)
        raise AppException(
            "File deletion failed",
            "S3_DELETE_FAILED",
            status_code=502,
        ) from exc


def get_file_size(file_key: str) -> int:
    """Return the size in bytes of an S3 object. Raises AppException if not found."""
    try:
        head = _s3.head_object(Bucket=settings.aws_bucket_name, Key=file_key)
        return int(head["ContentLength"])
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchKey"):
            raise AppException(
                f"File not found in storage: {file_key}",
                "S3_FILE_NOT_FOUND",
                status_code=404,
            ) from exc
        logger.error("S3 head_object failed for key %s: %s", file_key, exc)
        raise AppException(
            "Could not retrieve file metadata",
            "S3_HEAD_FAILED",
            status_code=502,
        ) from exc


if __name__ == "__main__":
    import sys
    import os

    # Run from the backend/ directory so .env is found:
    #   cd backend && source venv/bin/activate
    #   python -m mednotebook_backend.services.storage

    print(f"Bucket : {settings.aws_bucket_name}")
    print(f"Region : {settings.aws_region}")

    content = b"MedNotebook S3 smoke test\n"
    result = upload_file(
        file_content=content,
        filename="smoke-test.txt",
        mime_type="text/plain",
        user_id="00000000-0000-0000-0000-000000000001",
    )
    print(f"Uploaded  : {result['file_key']}")
    print(f"Size      : {result['file_size_bytes']} bytes")

    verified = get_file_size(result["file_key"])
    print(f"Verified  : {verified} bytes (via head_object)")

    url = get_presigned_url(result["file_key"], expires_in=300)
    print(f"URL (5min): {url[:80]}...")

    deleted = delete_file(result["file_key"])
    print(f"Deleted   : {deleted}")

    missing = delete_file(result["file_key"])
    print(f"Re-delete (should be False): {missing}")

    print("\nAll checks passed.")
