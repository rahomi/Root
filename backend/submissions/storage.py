import os
import time
import hmac
import hashlib
import logging
from urllib.parse import urlencode
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def _get_media_root() -> str:
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        raise ImproperlyConfigured("MEDIA_ROOT must be set in settings for local storage.")
    return media_root


def _get_media_url() -> str:
    media_url = getattr(settings, "MEDIA_URL", None)
    if not media_url:
        raise ImproperlyConfigured("MEDIA_URL must be set in settings for local storage.")
    return media_url.rstrip("/")


def _sign_url(path: str, expires_at: int) -> str:
    """
    Generate an HMAC-SHA256 signature for a local signed URL.
    Uses Django's SECRET_KEY as the signing key.
    """
    secret = settings.SECRET_KEY.encode()
    message = f"{path}:{expires_at}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def generate_signed_url(storage_key: str, expires_in: int = 3600) -> str:
    """
    Generate a time-limited signed URL for a local media file.

    URL pattern served by serve_attachment():
        /media/serve/<storage_key>?expires=<timestamp>&sig=<hmac>

    Args:
        storage_key: Relative path stored on FileAttachment.storage_key
                     e.g. 'attachments/2024/uuid/receipt.pdf'
        expires_in:  Seconds until URL expires. Default 3600 (1 hour).

    Returns:
        Signed URL string that serve_attachment() validates before streaming.
    """
    if not storage_key:
        raise ValueError("storage_key must be a non-empty string.")
    if not (1 <= expires_in <= 86400):
        raise ValueError("expires_in must be between 1 and 86400 seconds.")

    expires_at = int(time.time()) + expires_in
    sig = _sign_url(storage_key, expires_at)

    base_url = _get_media_url()
    params = urlencode({"expires": expires_at, "sig": sig})
    return f"{base_url}/serve/{storage_key}?{params}"


def verify_signed_url(storage_key: str, expires_at: str, sig: str) -> bool:
    """
    Verify a signed URL produced by generate_signed_url().
    Call this inside serve_attachment() before streaming the file.

    Returns True only if signature is valid AND the URL has not expired.
    """
    try:
        expires_at_int = int(expires_at)
    except (TypeError, ValueError):
        return False

    if time.time() > expires_at_int:
        return False  # expired

    expected_sig = _sign_url(storage_key, expires_at_int)
    return hmac.compare_digest(expected_sig, sig)  # constant-time comparison


def save_upload(file_obj, storage_key: str) -> str:
    """
    Save an uploaded InMemoryUploadedFile / TemporaryUploadedFile
    to MEDIA_ROOT/<storage_key>. Creates parent directories as needed.

    Args:
        file_obj:    Django uploaded file object.
        storage_key: Relative destination path, e.g.
                     'attachments/2024/05/<uuid>/receipt.pdf'

    Returns:
        storage_key unchanged — store this on FileAttachment.storage_key.
    """
    media_root = _get_media_root()
    abs_path = os.path.join(media_root, storage_key)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    with open(abs_path, "wb") as dest:
        for chunk in file_obj.chunks():
            dest.write(chunk)

    logger.info("Saved upload to local storage: %s", abs_path)
    return storage_key


def delete_object(storage_key: str) -> None:
    """
    Delete a file from local storage.
    Admin / management command use only — not called from normal app flow.
    """
    media_root = _get_media_root()
    abs_path = os.path.join(media_root, storage_key)

    if os.path.exists(abs_path):
        os.remove(abs_path)
        logger.info("Deleted local file: %s", abs_path)
    else:
        logger.warning("delete_object: file not found at %s", abs_path)