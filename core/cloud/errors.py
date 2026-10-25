"""
Typed errors for the cloud layer.

Each error carries an HTTP status (used by the API layer) and a user-facing message,
so providers can raise precise failures and the UI can show something useful.
"""

from __future__ import annotations

from typing import Optional


class CloudError(Exception):
    """Base class. ``hint`` is an optional next step for the user."""

    status_code = 500
    code = "cloud_error"

    def __init__(self, message: str, *, hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def user_message(self) -> str:
        return f"{self.message} {self.hint}".strip() if self.hint else self.message


class ConfigError(CloudError):
    """Missing or invalid local configuration (e.g. no credentials saved)."""

    status_code = 400
    code = "not_configured"


class NotSupported(CloudError):
    """The provider doesn't offer this operation (e.g. training on Together)."""

    status_code = 400
    code = "not_supported"


class AuthError(CloudError):
    """Credentials were rejected by the provider."""

    status_code = 401
    code = "auth_failed"


class QuotaError(CloudError):
    """Billing, credit or quota problem on the provider account."""

    status_code = 402
    code = "quota_exceeded"


class CapacityError(CloudError):
    """No GPU of the requested type is available right now."""

    status_code = 409
    code = "no_capacity"


class HostKeyError(CloudError):
    """SSH host key is unknown or has changed."""

    status_code = 409
    code = "host_key"

    def __init__(self, message: str, *, fingerprint: Optional[str] = None, changed: bool = False,
                 hint: Optional[str] = None):
        super().__init__(message, hint=hint)
        self.fingerprint = fingerprint
        self.changed = changed


class RemoteExecutionError(CloudError):
    """The remote job failed (bad dataset, out of memory, crash, exceeded max runtime…)."""

    status_code = 502
    code = "remote_failed"


class TransientError(CloudError):
    """Temporary failure (network, 5xx, rate limit). Safe to retry idempotent calls."""

    status_code = 503
    code = "transient"

    def __init__(self, message: str, *, retry_after: Optional[float] = None, hint: Optional[str] = None):
        super().__init__(message, hint=hint)
        self.retry_after = retry_after


class SecretStoreError(CloudError):
    """Stored secrets can't be read or written."""

    status_code = 500
    code = "secret_store"
