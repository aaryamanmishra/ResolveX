"""Object Storage Provider Protocol and Adapters for ResolveX AI.

PRD §5.3, §8.2 & §12.2: Private bucket storage for multimodal evidence assets
(receipt screenshots, bank statements, voice notes).
- SpacesStorageProvider: DigitalOcean Spaces / S3-compatible private bucket storage.
- MemoryStorageProvider: In-memory zero-dependency storage for local development and Demo Mode.
"""

import logging
import time
from typing import Any, Protocol, runtime_checkable

from backend.app.config import settings

logger = logging.getLogger("resolvex.storage")


@runtime_checkable
class StorageProvider(Protocol):
    """Protocol for private evidence object storage."""

    @property
    def provider_name(self) -> str:
        """Name of storage provider."""
        ...

    def generate_presigned_upload_url(
        self,
        tenant_id: str,
        storage_key: str,
        mime_type: str,
        expires_in_seconds: int = 900,
    ) -> dict[str, Any]:
        """Generate a short-lived presigned URL for direct secure client upload."""
        ...

    def generate_presigned_download_url(
        self,
        tenant_id: str,
        storage_key: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        """Generate a short-lived presigned URL for reading private evidence."""
        ...

    def store_bytes(
        self,
        tenant_id: str,
        storage_key: str,
        data: bytes,
        mime_type: str,
    ) -> None:
        """Store raw bytes into the private tenant-isolated storage."""
        ...

    def get_bytes(
        self,
        tenant_id: str,
        storage_key: str,
    ) -> bytes:
        """Retrieve raw bytes from storage."""
        ...

    def delete_bytes(
        self,
        tenant_id: str,
        storage_key: str,
    ) -> bool:
        """Delete object from storage."""
        ...


class MemoryStorageProvider:
    """In-memory, zero-dependency storage provider for Demo Mode and testing.

    Ensures local development and automated tests run without external Spaces / S3 credentials.
    """

    def __init__(self) -> None:
        # Keyed by (tenant_id, storage_key) -> (data, mime_type)
        self._objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    @property
    def provider_name(self) -> str:
        return "memory"

    def generate_presigned_upload_url(
        self,
        tenant_id: str,
        storage_key: str,
        mime_type: str,
        expires_in_seconds: int = 900,
    ) -> dict[str, Any]:
        expires_at = int(time.time()) + expires_in_seconds
        upload_url = (
            f"http://localhost:8000/api/v1/evidence/upload-direct/{tenant_id}/{storage_key}"
        )
        return {
            "upload_url": upload_url,
            "method": "PUT",
            "storage_key": storage_key,
            "mime_type": mime_type,
            "expires_at": expires_at,
            "headers": {"Content-Type": mime_type},
        }

    def generate_presigned_download_url(
        self,
        tenant_id: str,
        storage_key: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        expires_at = int(time.time()) + expires_in_seconds
        return f"http://localhost:8000/api/v1/evidence/download-direct/{tenant_id}/{storage_key}?expires={expires_at}"

    def store_bytes(
        self,
        tenant_id: str,
        storage_key: str,
        data: bytes,
        mime_type: str,
    ) -> None:
        self._objects[(tenant_id, storage_key)] = (data, mime_type)

    def get_bytes(
        self,
        tenant_id: str,
        storage_key: str,
    ) -> bytes:
        key = (tenant_id, storage_key)
        if key not in self._objects:
            raise KeyError(f"Storage object '{storage_key}' not found in tenant '{tenant_id}'")
        return self._objects[key][0]

    def delete_bytes(
        self,
        tenant_id: str,
        storage_key: str,
    ) -> bool:
        key = (tenant_id, storage_key)
        if key in self._objects:
            del self._objects[key]
            return True
        return False

    def clear(self) -> None:
        """Reset storage for test fixtures."""
        self._objects.clear()


class SpacesStorageProvider:
    """DigitalOcean Spaces / S3-compatible private object storage provider.

    PRD §12.2: Stores evidence artifacts privately in DigitalOcean Spaces.
    Requires SPACES_ACCESS_KEY and SPACES_SECRET_KEY.
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        bucket_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url or settings.SPACES_ENDPOINT
        self.bucket_name = bucket_name or settings.SPACES_BUCKET
        self.access_key = access_key or settings.SPACES_ACCESS_KEY
        self.secret_key = secret_key or settings.SPACES_SECRET_KEY

    @property
    def provider_name(self) -> str:
        return "spaces"

    def _get_client(self) -> Any:
        import boto3

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def generate_presigned_upload_url(
        self,
        tenant_id: str,
        storage_key: str,
        mime_type: str,
        expires_in_seconds: int = 900,
    ) -> dict[str, Any]:
        scoped_key = f"{tenant_id}/{storage_key}"
        client = self._get_client()
        url = client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": scoped_key,
                "ContentType": mime_type,
            },
            ExpiresIn=expires_in_seconds,
        )
        return {
            "upload_url": url,
            "method": "PUT",
            "storage_key": storage_key,
            "mime_type": mime_type,
            "expires_in": expires_in_seconds,
            "headers": {"Content-Type": mime_type},
        }

    def generate_presigned_download_url(
        self,
        tenant_id: str,
        storage_key: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        scoped_key = f"{tenant_id}/{storage_key}"
        client = self._get_client()
        url: str = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket_name, "Key": scoped_key},
            ExpiresIn=expires_in_seconds,
        )
        return url

    def store_bytes(
        self,
        tenant_id: str,
        storage_key: str,
        data: bytes,
        mime_type: str,
    ) -> None:
        scoped_key = f"{tenant_id}/{storage_key}"
        client = self._get_client()
        client.put_object(
            Bucket=self.bucket_name,
            Key=scoped_key,
            Body=data,
            ContentType=mime_type,
        )

    def get_bytes(
        self,
        tenant_id: str,
        storage_key: str,
    ) -> bytes:
        scoped_key = f"{tenant_id}/{storage_key}"
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket_name, Key=scoped_key)
        data: bytes = response["Body"].read()
        return data

    def delete_bytes(
        self,
        tenant_id: str,
        storage_key: str,
    ) -> bool:
        scoped_key = f"{tenant_id}/{storage_key}"
        client = self._get_client()
        client.delete_object(Bucket=self.bucket_name, Key=scoped_key)
        return True


# Factory router
def get_storage_provider() -> StorageProvider:
    """Retrieve active storage provider based on configuration."""
    if not settings.DEMO_MODE and settings.SPACES_ACCESS_KEY and settings.SPACES_SECRET_KEY:
        return SpacesStorageProvider()
    return default_memory_storage


default_memory_storage = MemoryStorageProvider()
