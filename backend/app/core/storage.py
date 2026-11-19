"""S3-compatible object storage (AWS S3 in prod, MinIO locally)."""
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config

from .config import get_settings


@lru_cache
def _client(public: bool = False):
    s = get_settings()
    endpoint = (s.s3_public_endpoint_url if public else None) or s.s3_endpoint_url
    return boto3.client("s3", endpoint_url=endpoint, region_name=s.aws_region,
                        config=Config(signature_version="s3v4"))


def upload_file(local_path: str | Path, key: str, content_type: str | None = None) -> str:
    extra = {"ContentType": content_type} if content_type else None
    _client().upload_file(str(local_path), get_settings().s3_bucket, key, ExtraArgs=extra)
    return key


def download_file(key: str, local_path: str | Path) -> Path:
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    _client().download_file(get_settings().s3_bucket, key, str(local_path))
    return local_path


def put_bytes(key: str, data: bytes, content_type: str = "application/json") -> str:
    _client().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type)
    return key


def get_bytes(key: str) -> bytes:
    return _client().get_object(Bucket=get_settings().s3_bucket, Key=key)["Body"].read()


def presigned_get(key: str, expires: int = 3600) -> str:
    return _client(public=True).generate_presigned_url(
        "get_object", Params={"Bucket": get_settings().s3_bucket, "Key": key}, ExpiresIn=expires)


def presigned_put(key: str, content_type: str, expires: int = 3600) -> str:
    """Browser uploads multi-GB sources straight to storage, bypassing the API."""
    return _client(public=True).generate_presigned_url(
        "put_object", Params={"Bucket": get_settings().s3_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires)
