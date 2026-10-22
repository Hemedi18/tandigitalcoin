from django.apps import AppConfig


class WalletGuiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "frontend.wallet_gui"
    label = "frontend_wallet_gui"
    verbose_name = "Frontend (wallet GUI)"
