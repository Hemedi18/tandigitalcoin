"""Explorer URLconf — keep paths shallow for public sharing."""

from django.urls import path
from django.views.generic import RedirectView

from frontend.explorer import views

app_name = "explorer"

urlpatterns = [
    path("search/", views.search_redirect, name="search"),
    path("live/", views.home_live_json, name="live"),
    path("", views.home, name="home"),
    path("blocks/", views.blocks_list, name="blocks"),
    path("block/<str:block_hash>/", views.block_detail, name="block"),
    path("transactions/", views.transactions_list, name="transactions"),
    path("mempool/", views.mempool, name="mempool"),
    path("tx/<str:txid>/", views.transaction_detail, name="transaction"),
    path("address/<str:address>/", views.address_detail, name="address"),
    path("api-help/", views.api_help, name="api_help"),
    path("participate/", views.participate, name="participate"),
    path("charts/", views.charts, name="charts"),
    path("charts/live/", views.charts_live_json, name="charts_live"),
    path(
        "reports/",
        RedirectView.as_view(pattern_name="explorer:charts", permanent=True),
    ),
]
