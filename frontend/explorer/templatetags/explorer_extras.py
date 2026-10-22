"""Template filters for amounts and hashes (explorer templates)."""

from django import template

from frontend.explorer.services.explorer_data import satoshi_to_tan_str

register = template.Library()


@register.filter
def tan_amount(value) -> str:
    """Format integer satoshis as TAN with up to 8 decimals."""
    if value is None:
        return "—"
    return satoshi_to_tan_str(int(value))


@register.filter
def short_hash(value: str, n: int = 10) -> str:
    """Truncate long hex for tables."""
    s = str(value)
    if len(s) <= n + 4:
        return s
    return s[: n // 2] + "…" + s[-(n // 2) :]
