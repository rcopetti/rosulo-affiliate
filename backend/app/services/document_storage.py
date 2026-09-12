import base64
import hashlib
import uuid
from dataclasses import dataclass

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


@dataclass(frozen=True)
class EncryptedDocument:
    ciphertext: bytes
    nonce: bytes


def _encryption_key() -> bytes:
    if not settings.documents_encryption_key:
        raise RuntimeError("DOCUMENTS_ENCRYPTION_KEY is not configured")
    try:
        key = base64.urlsafe_b64decode(settings.documents_encryption_key)
    except Exception as exc:
        raise RuntimeError("DOCUMENTS_ENCRYPTION_KEY must be URL-safe base64") from exc
    if len(key) not in (16, 24, 32):
        raise RuntimeError("DOCUMENTS_ENCRYPTION_KEY must decode to 16, 24, or 32 bytes")
    return key


def encrypt_document(content: bytes, document_id: uuid.UUID) -> EncryptedDocument:
    nonce = hashlib.sha256(document_id.bytes).digest()[:12]
    ciphertext = AESGCM(_encryption_key()).encrypt(nonce, content, document_id.bytes)
    return EncryptedDocument(ciphertext=ciphertext, nonce=nonce)


def decrypt_document(content: bytes, document_id: uuid.UUID) -> bytes:
    nonce = hashlib.sha256(document_id.bytes).digest()[:12]
    return AESGCM(_encryption_key()).decrypt(nonce, content, document_id.bytes)


def _s3_client():
    return boto3.client("s3", region_name=settings.documents_s3_region)


def put_document(document_id: uuid.UUID, content: bytes) -> str:
    if not settings.documents_s3_bucket:
        raise RuntimeError("DOCUMENTS_S3_BUCKET is not configured")
    encrypted = encrypt_document(content, document_id)
    key = f"affiliate-documents/{document_id}.bin"
    _s3_client().put_object(
        Bucket=settings.documents_s3_bucket,
        Key=key,
        Body=encrypted.ciphertext,
        ContentType="application/octet-stream",
        ServerSideEncryption="AES256",
        Metadata={"encryption": "aes-gcm", "document-id": str(document_id)},
    )
    return key


def get_document(key: str, document_id: uuid.UUID) -> bytes:
    if not settings.documents_s3_bucket:
        raise RuntimeError("DOCUMENTS_S3_BUCKET is not configured")
    response = _s3_client().get_object(Bucket=settings.documents_s3_bucket, Key=key)
    return decrypt_document(response["Body"].read(), document_id)
