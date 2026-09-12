"""
A small, dependency-light encrypted-at-rest text field.

Passport numbers and similar identifiers get encrypted with Fernet
(AES-128-CBC + HMAC) before they touch the database, and decrypted
transparently when a model instance is loaded. The key comes from
FIELD_ENCRYPTION_KEY in the environment — never hardcode it.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models
from decouple import config


def _get_fernet():
    key = config('FIELD_ENCRYPTION_KEY', default=None)
    if not key:
        raise RuntimeError(
            'FIELD_ENCRYPTION_KEY is not set. Generate one with '
            '`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` '
            'and put it in your .env file. Without it, sensitive fields cannot be stored.'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedCharField(models.CharField):
    """Stores CharField values encrypted at rest, transparent in Python."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 500)
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        f = _get_fernet()
        return f.encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        f = _get_fernet()
        try:
            return f.decrypt(value.encode()).decode()
        except InvalidToken:
            return value