"""One shared password, and a signed cookie that remembers it.

PTSA volunteers come and go every year. Individual accounts would mean someone
administering them -- adding the new secretary in September, removing last
year's in June -- and that someone is a volunteer too. The first time nobody
does it, either a person who should be able to fix a date cannot, or an account
that should have gone stays live. A single password that gets handed over with
the rest of the role is honest about how this group actually works.

What makes it safe enough is not the password. It is that every change is
committed, attributed, and revertible in about ten seconds, that publishing is
a separate deliberate press, and that the worst case -- someone editing a
school calendar they should not -- is undone before most people would see it.

Two things this deliberately does not do:

- It does not store the password. Only an argon2 hash, from the environment,
  so the running container never holds the plaintext and neither does the repo.
- It does not tie the session to the password's current value... except that it
  does, by keying the signature on the hash. Rotating the password logs
  everyone out, which is the entire point of rotating it.
"""

from __future__ import annotations

import hmac
import os
import secrets
import time
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

COOKIE_NAME = "ptsa_session"
#: Long enough that nobody is logged out mid-edit, short enough that a borrowed
#: laptop is not a standing invitation.
SESSION_MAX_AGE = 30 * 24 * 3600

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """For generating the value to put in the environment. Not used at runtime."""
    return _hasher.hash(plain)


@dataclass
class Auth:
    """Checks the shared password and mints session cookies."""

    password_hash: str
    secret: str

    @classmethod
    def from_env(cls) -> "Auth":
        password_hash = os.environ.get("EDITOR_PASSWORD_HASH", "").strip()
        if not password_hash:
            raise RuntimeError(
                "EDITOR_PASSWORD_HASH is not set. Generate one with:\n"
                "    python -c \"from web.auth import hash_password; "
                "print(hash_password('your password'))\""
            )
        # Derived from the password hash rather than configured separately, so
        # there is one secret to manage instead of two -- and so changing the
        # password invalidates every existing session, which is what someone
        # changing it after a leak is trying to achieve.
        secret = os.environ.get("SESSION_SECRET") or password_hash
        return cls(password_hash=password_hash, secret=secret)

    @property
    def _serializer(self) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(self.secret, salt="ptsa-calendar-editor")

    def check(self, password: str) -> bool:
        """True if this is the shared password.

        argon2 is deliberately slow, which is most of the defence: it makes
        guessing at the password over the network hopeless even though there is
        only one of them and it is probably not long.
        """
        try:
            return bool(_hasher.verify(self.password_hash, password or ""))
        except (VerifyMismatchError, VerificationError):
            return False

    def issue(self, name: str = "") -> str:
        return self._serializer.dumps({"name": name, "at": int(time.time())})

    def read(self, token: str | None) -> dict | None:
        """The session this cookie carries, or None if it is not ours or is old."""
        if not token:
            return None
        try:
            return self._serializer.loads(token, max_age=SESSION_MAX_AGE)
        except BadSignature:
            return None


class LoginRateLimit:
    """A short delay-and-refuse after repeated wrong passwords.

    argon2 already makes each guess expensive; this stops one IP from having
    unlimited cheap tries anyway, and it costs nothing to a person who
    mistyped once. In memory on purpose -- a restart clearing it is fine, and a
    volunteer PTSA tool does not need a Redis to hold five integers.
    """

    def __init__(self, limit: int = 8, window: int = 900):
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}

    def blocked(self, key: str) -> bool:
        now = time.time()
        recent = [t for t in self._hits.get(key, []) if now - t < self.window]
        self._hits[key] = recent
        return len(recent) >= self.limit

    def record_failure(self, key: str) -> None:
        self._hits.setdefault(key, []).append(time.time())

    def clear(self, key: str) -> None:
        self._hits.pop(key, None)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def new_secret() -> str:
    return secrets.token_urlsafe(32)
