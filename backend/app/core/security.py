from cryptography.fernet import Fernet
from .config import settings
import base64
import hashlib


def get_encryption_key() -> bytes:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_value(value: str) -> str:
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_value.encode()).decode()


def mask_api_key(api_key: str) -> str:
    if not api_key or len(api_key) < 8:
        return "********"
    return f"********{api_key[-4:]}"
