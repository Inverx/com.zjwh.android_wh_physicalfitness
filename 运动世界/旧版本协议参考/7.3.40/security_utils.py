"""Small, dependency-free helpers for safe diagnostics and logging."""

import logging
import re
from typing import Any


SENSITIVE_KEYS = {
    "password", "passwd", "token", "authorization", "imei", "deviceid",
    "account", "username", "uid",
    "customdeviceid", "androidid", "wifimac", "blmac",
}


def mask_secret(value: Any, keep: int = 4) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    if len(text) <= keep * 2:
        return "*" * len(text)
    return f"{text[:keep]}…{text[-keep:]}"


def redact_data(value: Any) -> Any:
    """Recursively redact common credential and device-identity fields."""
    if isinstance(value, dict):
        return {
            key: mask_secret(item) if str(key).lower() in SENSITIVE_KEYS
            else redact_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    return value


_SECRET_TEXT_RE = re.compile(
    r"(?i)(\b(?:token|password|passwd|authorization|imei|device[_-]?id|"
    r"custom[_-]?device[_-]?id|account|username|uid)\b\s*[=:]\s*)([^\s,;&]+)"
)


def redact_text(value: Any) -> str:
    """Redact common ``key=value`` secrets in arbitrary log text."""
    text = "" if value is None else str(value)
    return _SECRET_TEXT_RE.sub(lambda match: match.group(1) + mask_secret(match.group(2)), text)


class RedactingFilter(logging.Filter):
    """Ensure formatted log messages never expose credential/device fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def install_redaction_filter(logger: logging.Logger) -> None:
    """Install the filter once on a logger used by a client module."""
    if not any(isinstance(item, RedactingFilter) for item in logger.filters):
        logger.addFilter(RedactingFilter())
