from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from chain_api.services import node
from tancoin_core.wallet import Wallet


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


@require_GET
def status(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True, "chain": node.chain_summary()})


@require_GET
def blocks(request: HttpRequest) -> JsonResponse:
    limit = int(request.GET.get("limit", "20"))
    limit = max(1, min(limit, 500))
    c = node.get_chain()
    tail = c.blocks[-limit:] if c.blocks else []
    return JsonResponse({"ok": True, "blocks": [b.to_dict() for b in tail]})


@require_GET
def block_detail(request: HttpRequest, block_hash: str) -> JsonResponse:
    h = block_hash.lower().removeprefix("0x")
    c = node.get_chain()
    for b in reversed(c.blocks):
        if b.block_hash().hex() == h:
            return JsonResponse({"ok": True, "block": b.to_dict()})
    return _json_error("block not found", 404)


@require_GET
def transaction_detail(_request: HttpRequest, txid: str) -> JsonResponse:
    tid = txid.lower().removeprefix("0x")
    c = node.get_chain()
    for b in reversed(c.blocks):
        for t in b.transactions:
            if t.txid().hex() == tid:
                return JsonResponse({"ok": True, "tx": t.to_dict(), "confirmed": True})
    for t in node.get_mempool():
        if t.txid().hex() == tid:
            return JsonResponse({"ok": True, "tx": t.to_dict(), "confirmed": False})
    return _json_error("transaction not found", 404)


@require_GET
def utxos(request: HttpRequest, address: str) -> JsonResponse:
    try:
        rows = node.get_chain().get_utxos_for_address(address)
    except Exception as e:
        return _json_error(str(e))
    return JsonResponse({"ok": True, "utxos": rows})


@require_GET
def wallet_new(_request: HttpRequest) -> JsonResponse:
    w = Wallet.generate()
    return JsonResponse(
        {
            "ok": True,
            "address": w.address(),
            "wif": w.to_wif(),
            "warning": "Store WIF securely; it grants full spend rights.",
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def tx_submit(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body.decode("utf-8"))
        txd = body.get("transaction") or body.get("tx")
        if not isinstance(txd, dict):
            return _json_error("JSON body must include 'transaction' object")
        txid = node.submit_transaction(txd)
        return JsonResponse({"ok": True, "txid": txid})
    except Exception as e:
        return _json_error(str(e))


@csrf_exempt
@require_http_methods(["POST"])
def mine(request: HttpRequest) -> JsonResponse:
    try:
        miner: Wallet | None = None
        if request.body:
            body = json.loads(request.body.decode("utf-8"))
            wif = body.get("miner_wif")
            if wif:
                miner = Wallet.from_wif(str(wif))
        b = node.mine_block(miner)
        return JsonResponse({"ok": True, "block": b.to_dict()})
    except Exception as e:
        return _json_error(str(e))


@csrf_exempt
@require_http_methods(["POST"])
def reference_price(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body.decode("utf-8"))
        p = float(body.get("reference_price_usd"))
        node.set_reference_price_usd(p)
        return JsonResponse({"ok": True, "reference_price_usd": p})
    except Exception as e:
        return _json_error(str(e))


@require_GET
def mempool_list(_request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"ok": True, "transactions": [t.to_dict() for t in node.get_mempool()]}
    )


@csrf_exempt
@require_http_methods(["POST"])
def contract_deploy(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body.decode("utf-8"))
        wif = body.get("deployer_wif")
        fee = int(body.get("fee_satoshis", 50_000))
        code_hex = body.get("bytecode_hex", "")
        if not wif:
            return _json_error("deployer_wif required")
        bytecode = bytes.fromhex(code_hex.replace("0x", ""))
        if not bytecode:
            return _json_error("bytecode_hex required")
        w = Wallet.from_wif(str(wif))
        tx = node.build_deploy_transaction(w, bytecode, fee)
        txid = node.submit_transaction(tx.to_dict())
        return JsonResponse({"ok": True, "txid": txid, "transaction": tx.to_dict()})
    except Exception as e:
        return _json_error(str(e))


@csrf_exempt
@require_http_methods(["POST"])
def contract_call(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body.decode("utf-8"))
        wif = body.get("caller_wif")
        cid = body.get("contract_id_hex", "")
        calldata_hex = body.get("calldata_hex", "0x")
        fee = int(body.get("fee_satoshis", 50_000))
        if not wif:
            return _json_error("caller_wif required")
        calldata = bytes.fromhex(str(calldata_hex).replace("0x", ""))
        w = Wallet.from_wif(str(wif))
        tx = node.build_call_transaction(w, cid, calldata, fee)
        txid = node.submit_transaction(tx.to_dict())
        return JsonResponse({"ok": True, "txid": txid, "transaction": tx.to_dict()})
    except Exception as e:
        return _json_error(str(e))


@require_GET
def contracts(_request: HttpRequest) -> JsonResponse:
    c = node.get_chain()
    out: list[dict[str, Any]] = []
    for addr, st in c.contracts.items():
        out.append(
            {
                "contract_id_hex": addr.hex(),
                "code_size": len(st.code),
                "storage_keys": len(st.storage),
            }
        )
    return JsonResponse({"ok": True, "contracts": out})


@require_GET
def genesis_wallet(_request: HttpRequest) -> JsonResponse:
    from django.conf import settings

    if not settings.DEBUG:
        return _json_error("disabled when DEBUG is False", 404)
    gw = node.get_genesis_wallet()
    if not gw:
        return _json_error("genesis wallet not available", 404)
    return JsonResponse({"ok": True, "address": gw.address(), "wif": gw.to_wif()})
