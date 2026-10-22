from django.apps import AppConfig


class DocumentationConfig(AppConfig):
    """Human-readable documentation (HTML) — modular from explorer UI."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "frontend.documentation"
    label = "frontend_documentation"
    verbose_name = "Frontend (documentation)"
