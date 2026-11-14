"""Small security helpers."""
from urllib.parse import urljoin, urlparse

from flask import request


def is_safe_redirect_target(target):
    """True only for a path on this site.

    The login page redirects to ?next=... after sign-in. Without this check a
    link such as /auth/login?next=https://evil.example would send the user to
    another site right after they typed their password (an "open redirect").
    """
    if not target:
        return False
    # must be a local path. "//host" and "/\host" are read by browsers as another site
    if not target.startswith('/') or target.startswith('//') or '\\' in target:
        return False
    if any(ord(ch) < 32 for ch in target):
        return False
    site = urlparse(request.host_url)
    dest = urlparse(urljoin(request.host_url, target))
    return dest.scheme in ('http', 'https') and dest.netloc == site.netloc
