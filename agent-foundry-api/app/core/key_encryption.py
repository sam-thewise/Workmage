"""Encryption for BYOK keys at rest."""
import base64
import hashlib

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

SIGNER_KEY_SALT = b"agent-foundry-signer-keys"


def _get_fernet() -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"agent-foundry-llm-keys",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(
        kdf.derive(settings.SECRET_KEY.encode() or b"dev")
    )
    return Fernet(key)


def _get_signer_fernet() -> Fernet:
    """Fernet for signer keys; separate from LLM keys. Uses SIGNER_ENCRYPTION_KEY if set else SECRET_KEY + salt."""
    if getattr(settings, "SIGNER_ENCRYPTION_KEY", None) and settings.SIGNER_ENCRYPTION_KEY.strip():
        raw = base64.urlsafe_b64decode(settings.SIGNER_ENCRYPTION_KEY.strip().encode())
        return Fernet(raw)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SIGNER_KEY_SALT,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(
        kdf.derive(settings.SECRET_KEY.encode() or b"dev")
    )
    return Fernet(key)


def encrypt_api_key(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


def encrypt_signer_key(plain: str) -> str:
    """Encrypt a signer private key for storage in agent_wallet_signer_keys."""
    return _get_signer_fernet().encrypt(plain.encode()).decode()


def decrypt_signer_key(encrypted: str) -> str:
    """Decrypt a signer private key from agent_wallet_signer_keys."""
    return _get_signer_fernet().decrypt(encrypted.encode()).decode()
