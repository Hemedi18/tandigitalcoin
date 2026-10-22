from django.apps import AppConfig


class ExplorerConfig(AppConfig):
    """Public blockchain explorer (HTML): blocks, transactions, addresses."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "frontend.explorer"
    label = "frontend_explorer"
    verbose_name = "Frontend (explorer)"
