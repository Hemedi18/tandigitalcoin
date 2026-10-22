"""Static URLs with cache-busting so CSS updates apply without a hard refresh."""

from __future__ import annotations

from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(relative_path: str) -> str:
    """
    Return a static file URL with ?v=…

    In DEBUG, v is the newest st_mtime_ns among STATICFILES_DIRS for that path.
    With DEBUG False, v is settings.TANCOIN_ASSET_VERSION or "1" (bump on deploy).
    """
    url = static(relative_path)
    rel = Path(relative_path)
    if settings.DEBUG:
        stamp = 0
        for d in settings.STATICFILES_DIRS:
            full = Path(d) / rel
            try:
                stamp = max(stamp, full.stat().st_mtime_ns)
            except OSError:
                continue
        v = str(stamp) if stamp else "0"
    else:
        v = getattr(settings, "TANCOIN_ASSET_VERSION", None) or "1"
    return f"{url}?v={v}"
