from django.urls import path

from chain_api import views

urlpatterns = [
    path("api/chain/status/", views.status, name="tancoin_status"),
    path("api/chain/blocks/", views.blocks, name="tancoin_blocks"),
    path("api/chain/block/<str:block_hash>/", views.block_detail, name="tancoin_block"),
    path("api/chain/tx/<str:txid>/", views.transaction_detail, name="tancoin_tx"),
    path("api/chain/utxo/<str:address>/", views.utxos, name="tancoin_utxo"),
    path("api/chain/mempool/", views.mempool_list, name="tancoin_mempool"),
    path("api/wallet/new/", views.wallet_new, name="tancoin_wallet_new"),
    path("api/chain/tx/submit/", views.tx_submit, name="tancoin_tx_submit"),
    path("api/chain/mine/", views.mine, name="tancoin_mine"),
    path("api/chain/price/", views.reference_price, name="tancoin_price"),
    path("api/contracts/", views.contracts, name="tancoin_contracts"),
    path(
        "api/contracts/deploy/", views.contract_deploy, name="tancoin_contract_deploy"
    ),
    path("api/contracts/call/", views.contract_call, name="tancoin_contract_call"),
    path(
        "api/dev/genesis-wallet/", views.genesis_wallet, name="tancoin_genesis_wallet"
    ),
]
