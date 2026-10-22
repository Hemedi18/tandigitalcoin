from django.apps import AppConfig


class ChainApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chain_api"
    verbose_name = "Tancoin chain API"

    def ready(self) -> None:
        from chain_api.services.node import ensure_initialized

        ensure_initialized()
