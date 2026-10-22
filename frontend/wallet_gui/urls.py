from django.urls import path

from frontend.wallet_gui import views

app_name = "wallet_gui"

urlpatterns = [
    path("", views.wallet_app, name="app"),
    path("account/login/", views.WalletLoginView.as_view(), name="account_login"),
    path("account/logout/", views.WalletLogoutView.as_view(), name="account_logout"),
    path("account/register/", views.account_register, name="account_register"),
    path("api/create/", views.api_create_wallet, name="api_create"),
    path("api/import/", views.api_import_wallet, name="api_import"),
    path("api/key-info/", views.api_key_info, name="api_key_info"),
    path("api/qr-png/", views.api_qr_png, name="api_qr_png"),
    path("api/balance/", views.api_balance, name="api_balance"),
    path("api/activity/", views.api_wallet_activity, name="api_wallet_activity"),
    path("api/mine/", views.api_mine, name="api_mine"),
    path("api/send/", views.api_send, name="api_send"),
    path("api/faucet/", views.api_faucet, name="api_faucet"),
]
