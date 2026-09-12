"""
All Supabase Storage calls go through this module, so upload views never
touch the supabase client directly.
"""

import mimetypes
import uuid

from django.conf import settings
from supabase import create_client


class StorageError(Exception):
    """Raised when Supabase Storage rejects an upload, fetch, or delete."""


def _client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise StorageError(
            'Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY '
            'in your .env file before uploading documents.'
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def build_path(user_id, document_type_id, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    unique = uuid.uuid4().hex[:12]
    return f'{user_id}/{document_type_id}/{unique}.{ext}'


def upload(file_obj, path):
    content_type = file_obj.content_type or mimetypes.guess_type(path)[0] or 'application/octet-stream'
    client = _client()
    file_bytes = file_obj.read()
    try:
        client.storage.from_(settings.SUPABASE_BUCKET).upload(
            path,
            file_bytes,
            file_options={'content-type': content_type, 'upsert': 'true'},
        )
    except Exception as exc:
        raise StorageError(f'Could not upload file: {exc}') from exc
    return content_type, len(file_bytes)


def signed_url(path, expires_in=None):
    client = _client()
    ttl = expires_in or settings.SUPABASE_SIGNED_URL_TTL
    try:
        result = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(path, ttl)
    except Exception as exc:
        raise StorageError(f'Could not create a signed URL: {exc}') from exc
    return result.get('signedURL') or result.get('signed_url')


def delete(path):
    client = _client()
    try:
        client.storage.from_(settings.SUPABASE_BUCKET).remove([path])
    except Exception as exc:
        raise StorageError(f'Could not delete file: {exc}') from exc