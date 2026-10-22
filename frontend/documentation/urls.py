from django.urls import path

from frontend.documentation import views

app_name = "documentation"

urlpatterns = [
    path("", views.hub, name="hub"),
    path("picture-guide/", views.visual_guide, name="visual_guide"),
    path("using-system/", views.using_system, name="using_system"),
    path("developer-api/", views.developer_api, name="developer_api"),
    path("smart-contracts/", views.smart_contracts, name="smart_contracts"),
    path("wallets/", views.wallet_architecture, name="wallet_architecture"),
    path("wallets-security/", views.wallets_security, name="wallets_security"),
    path(
        "features-architecture/",
        views.features_architecture,
        name="features_architecture",
    ),
    path(
        "payments-mining-wallet/", views.user_guide_payments, name="user_guide_payments"
    ),
]
