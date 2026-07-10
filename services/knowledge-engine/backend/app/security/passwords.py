"""Password hashing helpers for local credentials."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


_ALGORITHM = "scrypt"
_N = 2**14
_R = 8
_P = 1
_KEY_LENGTH = 64
_SALT_LENGTH = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_LENGTH)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_N,
        r=_R,
        p=_P,
        dklen=_KEY_LENGTH,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{_ALGORITHM}${_N}${_R}${_P}${salt_b64}${digest_b64}"


def verify_password(password: str, encoded_password: str) -> bool:
    try:
        algorithm, raw_n, raw_r, raw_p, salt_b64, digest_b64 = encoded_password.split(
            "$",
            5,
        )
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False
    try:
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected_digest = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        computed_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(expected_digest),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed_digest, expected_digest)
