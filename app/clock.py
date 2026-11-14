"""Time helpers.

Train times are stored as Chennai local time. A hosted server usually runs on
UTC, so "today" and "now" must be taken in the service's own timezone and not
from the server clock.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def local_now():
    """Current time in the service timezone, without tzinfo (same form as the DB columns)."""
    tz = ZoneInfo(current_app.config.get('APP_TIMEZONE', 'Asia/Kolkata'))
    return datetime.now(tz).replace(tzinfo=None)


def local_today():
    return local_now().date()


def utcnow():
    """UTC timestamp for created-at style columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
