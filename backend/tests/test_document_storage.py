import base64
import uuid

from app.core.config import settings
from app.services.document_storage import decrypt_document, encrypt_document


def test_document_encryption_round_trip(monkeypatch):
    key = base64.urlsafe_b64encode(b"0" * 32).decode()
    monkeypatch.setattr(settings, "documents_encryption_key", key)
    document_id = uuid.uuid4()
    encrypted = encrypt_document(b"private tax document", document_id)

    assert encrypted.ciphertext != b"private tax document"
    assert decrypt_document(encrypted.ciphertext, document_id) == b"private tax document"
