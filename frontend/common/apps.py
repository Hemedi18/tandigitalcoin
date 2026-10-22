from django.apps import AppConfig


class FrontendCommonConfig(AppConfig):
    """Shared base templates and global layout hooks (no URL routes)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "frontend.common"
    label = "frontend_common"
    verbose_name = "Frontend (common layout)"
