"""Wallet GUI + small JSON API used only by the wallet page (CSRF-protected POST)."""

from __future__ import annotations

import base64
import io
import json
from decimal import Decimal
from functools import wraps
from typing import Any

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from chain_api.services import node
from frontend.explorer.services import explorer_data as _explorer_data
from tancoin_core import constants
from tancoin_core import crypto as tancoin_crypto
from tancoin_core.wallet import Wallet

SAT = Decimal(constants.SATOSHIS_PER_COIN)


def _sat_to_tan_str(value: int) -> str:
    return (
        str((Decimal(value) / SAT).quantize(Decimal("0.00000001")))
        .rstrip("0")
        .rstrip(".")
    )


def _address_activity_payload(
    addresses: list[str], *, row_limit: int = 250
) -> dict[str, Any]:
    """Scan the local chain for transactions touching any of the given addresses (P2PKH)."""
    chain = node.get_chain()
    pkhs: set[bytes] = set()
    for raw in addresses:
        a = (raw or "").strip()
        if not a:
            continue
        try:
            pkhs.add(tancoin_crypto.pubkeyhash_from_address(a))
        except ValueError:
            continue
    if not pkhs:
        return {
            "rows": [],
            "summary": {
                "tx_count": 0,
                "total_recv_sat": 0,
                "total_sent_sat": 0,
                "net_sat": 0,
                "total_recv_tan": "0",
                "total_sent_tan": "0",
                "net_tan": "0",
            },
            "line_points": [],
        }

    rows: list[dict[str, Any]] = []
    for height, block in enumerate(chain.blocks, start=1):
        ts = int(block.timestamp)
        bh = block.block_hash().hex()
        for tx in block.transactions:
            recv_sat = 0
            for o in tx.outputs:
                if o.recipient_pubkey_hash in pkhs:
                    recv_sat += int(o.value)
            sent_sat = 0
            if tx.inputs:
                for inp in tx.inputs:
                    po = _explorer_data._find_prev_output(
                        chain, inp.prev_txid, inp.prev_index
                    )
                    if po is not None and po.recipient_pubkey_hash in pkhs:
                        sent_sat += int(po.value)
            if recv_sat == 0 and sent_sat == 0:
                continue
            net_sat = recv_sat - sent_sat
            fee_sat: int | None = None
            if tx.inputs:
                fee_sat = _explorer_data._tx_fee_satoshis(tx, chain)
            tid = tx.txid().hex()
            rows.append(
                {
                    "txid": tid,
                    "txid_short": f"{tid[:10]}…{tid[-6:]}",
                    "height": height,
                    "timestamp": ts,
                    "block_hash": bh,
                    "recv_sat": recv_sat,
                    "sent_sat": sent_sat,
                    "net_sat": net_sat,
                    "fee_sat": fee_sat,
                    "recv_tan": _sat_to_tan_str(recv_sat),
                    "sent_tan": _sat_to_tan_str(sent_sat),
                    "net_tan": str(
                        (Decimal(net_sat) / SAT).quantize(Decimal("0.00000001"))
                    )
                    .rstrip("0")
                    .rstrip("."),
                    "fee_tan": (
                        _sat_to_tan_str(fee_sat) if fee_sat is not None else None
                    ),
                }
            )

    rows.reverse()
    total_recv = sum(r["recv_sat"] for r in rows)
    total_sent = sum(r["sent_sat"] for r in rows)
    net_all = total_recv - total_sent
    summary = {
        "tx_count": len(rows),
        "total_recv_sat": total_recv,
        "total_sent_sat": total_sent,
        "net_sat": net_all,
        "total_recv_tan": _sat_to_tan_str(total_recv),
        "total_sent_tan": _sat_to_tan_str(total_sent),
        "net_tan": (
            _sat_to_tan_str(net_all)
            if net_all >= 0
            else "-" + _sat_to_tan_str(-net_all)
        ),
    }

    display_rows = rows[:row_limit]
    chrono = list(reversed(display_rows))
    mx = max((abs(r["net_sat"]) for r in chrono), default=1)
    line_points: list[dict[str, Any]] = [
        {"net_sat": int(r["net_sat"])} for r in chrono[-48:]
    ]

    return {"rows": display_rows, "summary": summary, "line_points": line_points}


def _require_auth_api(view_func):
    """Wallet JSON APIs must not run for anonymous users (protects WIF in transit)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "ok": False,
                    "error": str(_("Sign in required.")),
                    "auth_required": True,
                },
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def _tan_to_sat(amount_str: str) -> int:
    d = Decimal(amount_str.strip())
    sat = (d * SAT).quantize(Decimal("1"))
    if sat < 0:
        raise ValueError("amount negative")
    if sat > Decimal(2**63 - 1):
        raise ValueError("amount too large")
    return int(sat)


def _read_json(request) -> dict:
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def _wallet_json_error(exc: BaseException) -> str:
    """Map low-level crypto errors to clearer JSON `error` strings (gettext for locale)."""
    hints: dict[str, str] = {
        "invalid base58": _(
            "Invalid Base58: your WIF or address contains a wrong character, an accidental space, or an incomplete copy. "
            "Use only Base58 letters and digits (not 0, O, I, or l). Paste one full line with no line breaks in the middle."
        ),
        "invalid WIF length": _(
            "This private key (WIF) is not the right length for this network. Export or paste the WIF from this wallet or a compatible backup."
        ),
        "checksum mismatch": _(
            "Receiver address checksum failed: there is likely a typo. Compare the address character by character with the recipient."
        ),
        "address too short": _("Receiver address looks too short or incomplete."),
        "bad address length": _(
            "Receiver address format is not valid for this network."
        ),
    }
    msg = str(exc).strip()
    if msg in hints:
        return hints[msg]
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        cm = str(cause).strip()
        if cm in hints:
            return hints[cm]
    return msg


class WalletLoginView(LoginView):
    template_name = "wallet_gui/login.html"
    redirect_authenticated_user = True


class WalletLogoutView(LogoutView):
    next_page = reverse_lazy("wallet_gui:app")
    http_method_names = ["post", "options"]


@require_http_methods(["GET", "POST"])
def account_register(request):
    """Create a Django user then sign them in (local db.sqlite3)."""
    if request.user.is_authenticated:
        return redirect("wallet_gui:app")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("wallet_gui:app")
    else:
        form = UserCreationForm()
    return render(request, "wallet_gui/register.html", {"form": form})


def _wallet_boot_json(request):
    """URLs + i18n for wallet_gui.js (keeps Django out of inline <script> for valid JS tooling)."""
    ns = None
    if request.user.is_authenticated:
        ns = f"tancoin_keyring_u{request.user.pk}"
    faucet_enabled = settings.DEBUG
    login = reverse("wallet_gui:account_login")
    app_path = reverse("wallet_gui:app")
    urls = {
        "create": reverse("wallet_gui:api_create"),
        "importKey": reverse("wallet_gui:api_import"),
        "keyInfo": reverse("wallet_gui:api_key_info"),
        "qrPng": reverse("wallet_gui:api_qr_png"),
        "balance": reverse("wallet_gui:api_balance"),
        "send": reverse("wallet_gui:api_send"),
        "activity": reverse("wallet_gui:api_wallet_activity"),
        "mine": reverse("wallet_gui:api_mine"),
        "chainStatus": reverse("tancoin_status"),
        "chainMempool": reverse("tancoin_mempool"),
        "login": f"{login}?next={app_path}",
        "faucet": reverse("wallet_gui:api_faucet") if faucet_enabled else None,
    }
    i18n = {
        "show": _("Show"),
        "hide": _("Hide"),
        "forgetConfirm": _(
            "Remove all keys from this browser? Export each WIF first if you need them later."
        ),
        "utxoLabel": _("UTXOs"),
        "privExif": _(
            "JPEG metadata (EXIF) often includes device or location. Strip metadata before sharing anywhere public."
        ),
        "privLarge": _(
            "Large images are unnecessary for a local avatar and can make fingerprinting easier if you reuse the same file elsewhere."
        ),
        "privLocal": _(
            "This page does not upload your image to the server; checks run only in your browser."
        ),
        "privFace": _(
            "Using a real face photo can reduce anonymity if the same image appears on social networks."
        ),
        "primary": _("Primary"),
        "setPrimary": _("Set primary"),
        "remove": _("Remove"),
        "copyAddr": _("Copy address"),
        "copyPub": _("Copy public key"),
        "removeOne": _("Remove this key from the list?"),
        "memberSince": _("Member since"),
        "publicKey": _("Public key"),
        "addressLbl": _("Address"),
        "copyPubAddr": _("Copy public address"),
        "primaryCard": _("Primary card"),
        "identityCard": _("Identity card"),
        "wifRequired": _("WIF is required."),
        "sendHintKeys": _(
            "Amounts are in TAN. Pick a saved signing key; the WIF field fills automatically. Paste a different WIF to override."
        ),
        "signInRequired": _("Sign in required."),
        "fundCopyNoKey": _("Add a key first to copy a receive address."),
        "historyTitle": _("Your on-chain history"),
        "historyLead": _(
            "Line chart: net amount per transaction in time order (oldest → newest on this node). Green = net in, coral = net out. Table links to the explorer."
        ),
        "historyLineAria": _("Line chart of net amount per matching transaction"),
        "historyRefresh": _("Refresh history"),
        "historyEmpty": _("No matching transactions on this node yet."),
        "historyColWhen": _("When (UTC)"),
        "historyColTx": _("Transaction"),
        "historyColBlock": _("Block"),
        "historyColRecv": _("In (TAN)"),
        "historyColSent": _("Out (TAN)"),
        "historyColNet": _("Net (TAN)"),
        "historyColFee": _("Fee (TAN)"),
        "historySummaryTx": _("Transactions found"),
        "historySummaryIn": _("Total received (TAN)"),
        "historySummaryOut": _("Total sent (TAN)"),
        "historySummaryNet": _("Net flow (TAN)"),
        "dashOverviewOption": _("All keys — overview"),
        "keyAccountLead": _("Balances and address for this saved key on this node."),
        "minerNoPending": _("No pending transactions."),
    }
    return {"keyringNs": ns, "urls": urls, "i18n": i18n}


@ensure_csrf_cookie
@require_http_methods(["GET", "HEAD"])
def wallet_app(request):
    """Single-page wallet shell (animations + fetch to /wallet/api/*)."""
    return render(
        request,
        "wallet_gui/app.html",
        {
            "debug": settings.DEBUG,
            "faucet_enabled": settings.DEBUG,
            "wallet_boot": _wallet_boot_json(request),
            "wallet_buy_url": getattr(settings, "WALLET_EXTERNAL_BUY_URL", ""),
            "wallet_cashout_partner_url": getattr(
                settings, "WALLET_EXTERNAL_CASHOUT_URL", ""
            ),
        },
    )


@require_POST
@_require_auth_api
def api_create_wallet(request):
    """Generate a new keypair (server-side for demo; production may prefer client-side generation)."""
    try:
        w = Wallet.generate()
        pub = w.pubkey_serialized()
        return JsonResponse(
            {
                "ok": True,
                "address": w.address(),
                "wif": w.to_wif(),
                "pubkey_hex": pub.hex(),
                "pubkey_hash_hex": w.pubkey_hash().hex(),
                "message": _("New wallet created. Save your WIF in a safe place."),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_import_wallet(request):
    """Resolve WIF to address (does not store the secret on the server)."""
    try:
        data = _read_json(request)
        wif = (data.get("wif") or "").strip()
        if not wif:
            return JsonResponse({"ok": False, "error": "wif required"}, status=400)
        w = Wallet.from_wif(wif)
        pub = w.pubkey_serialized()
        return JsonResponse(
            {
                "ok": True,
                "address": w.address(),
                "pubkey_hex": pub.hex(),
                "pubkey_hash_hex": w.pubkey_hash().hex(),
                "message": _("Wallet imported. You can use Balance or Send."),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_qr_png(request):
    """Return a small PNG QR code as base64 (for wallet card back). Text must be short."""
    try:
        import segno

        data = _read_json(request)
        text = (data.get("text") or "").strip()
        if not text or len(text) > 4096:
            return JsonResponse(
                {"ok": False, "error": "text required (max 4096 chars)"}, status=400
            )
        qr = segno.make(text, error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=4, border=2)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return JsonResponse({"ok": True, "png_base64": b64})
    except ImportError:
        return JsonResponse(
            {"ok": False, "error": "QR library unavailable"}, status=503
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_key_info(request):
    """Return address and public key material for a WIF (does not persist the secret)."""
    try:
        data = _read_json(request)
        wif = (data.get("wif") or "").strip()
        if not wif:
            return JsonResponse({"ok": False, "error": "wif required"}, status=400)
        w = Wallet.from_wif(wif)
        pub = w.pubkey_serialized()
        return JsonResponse(
            {
                "ok": True,
                "address": w.address(),
                "pubkey_hex": pub.hex(),
                "pubkey_hash_hex": w.pubkey_hash().hex(),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_balance(request):
    """Sum UTXOs for an address."""
    try:
        data = _read_json(request)
        addr = (data.get("address") or "").strip()
        if not addr:
            return JsonResponse({"ok": False, "error": "address required"}, status=400)
        c = node.get_chain()
        rows = c.get_utxos_for_address(addr)
        total = sum(r["value"] for r in rows)
        return JsonResponse(
            {
                "ok": True,
                "address": addr,
                "satoshis": total,
                "tan": str(Decimal(total) / SAT),
                "utxo_count": len(rows),
                "message": _("Balance calculated."),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_wallet_activity(request):
    """Return confirmed on-chain rows for addresses in this browser session (server scan)."""
    try:
        data = _read_json(request)
        addrs = data.get("addresses")
        if not isinstance(addrs, list):
            return JsonResponse(
                {
                    "ok": False,
                    "error": _(
                        'Send a JSON object with an "addresses" array of base58 addresses.'
                    ),
                },
                status=400,
            )
        clean = [str(x).strip() for x in addrs[:64] if str(x).strip()]
        if not clean:
            return JsonResponse(
                {"ok": False, "error": _("At least one address is required.")},
                status=400,
            )
        payload = _address_activity_payload(clean)
        return JsonResponse(
            {
                "ok": True,
                "rows": payload["rows"],
                "summary": payload["summary"],
                "line_points": payload["line_points"],
                "message": _("On-chain activity for your addresses (this node)."),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_mine(request):
    """Create a candidate block from the mempool and run proof-of-work; coinbase pays the miner key."""
    try:
        data = _read_json(request)
        wif = (data.get("from_wif") or "").strip()
        if not wif:
            return JsonResponse(
                {
                    "ok": False,
                    "error": _(
                        "Choose a signing key (WIF) so the coinbase reward is credited to that address."
                    ),
                },
                status=400,
            )
        miner = Wallet.from_wif(wif)
        b = node.mine_block(miner)
        c = node.get_chain()
        return JsonResponse(
            {
                "ok": True,
                "block": b.to_dict(),
                "block_hash": b.block_hash().hex(),
                "height": c.height,
                "miner_address": miner.address(),
                "message": _("Block mined; mempool cleared on this node."),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_send(request):
    """Build, sign, submit transfer; optional auto-mine."""
    try:
        data = _read_json(request)
        wif = (data.get("from_wif") or "").strip()
        to_addr = (data.get("to_address") or "").strip()
        amount_tan = str(data.get("amount_tan") or "").strip()
        fee_tan = str(data.get("fee_tan") or "0.0005").strip()
        do_mine = bool(data.get("mine", True))
        if not wif or not to_addr or not amount_tan:
            return JsonResponse(
                {"ok": False, "error": "from_wif, to_address, amount_tan required"},
                status=400,
            )
        amount_sat = _tan_to_sat(amount_tan)
        fee_sat = _tan_to_sat(fee_tan)
        sender = Wallet.from_wif(wif)
        c = node.get_chain()
        utxos = c.get_utxos_for_address(sender.address())
        if not utxos:
            return JsonResponse(
                {"ok": False, "error": "no UTXOs for this wallet"}, status=400
            )
        sorted_utxos = sorted(utxos, key=lambda x: x["value"], reverse=True)
        selected_refs: list[tuple[bytes, int]] = []
        total_in = 0
        target_sat = amount_sat + fee_sat
        for u in sorted_utxos:
            txid = bytes.fromhex(u["txid"])
            idx = int(u["index"])
            prev = c.utxo.get((txid, idx))
            if not prev:
                continue
            selected_refs.append((txid, idx))
            total_in += prev.value
            if total_in >= target_sat:
                break
        if total_in < target_sat or not selected_refs:
            return JsonResponse(
                {
                    "ok": False,
                    "error": f"not enough funds: need {target_sat} sat, have {total_in}",
                },
                status=400,
            )
        change = total_in - target_sat
        tx = c.create_transfer(sender, to_addr, amount_sat, selected_refs, change)
        txid_hex = node.submit_transaction(tx.to_dict())
        block_hash = None
        if do_mine:
            b = node.mine_block(sender)
            block_hash = b.block_hash().hex()
        return JsonResponse(
            {
                "ok": True,
                "txid": txid_hex,
                "mined": do_mine,
                "block_hash": block_hash,
                "message": (
                    _("Payment sent and confirmed in a new block.")
                    if do_mine
                    else _("Payment submitted. Wait for a miner to confirm it.")
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)


@require_POST
@_require_auth_api
def api_faucet(request):
    """DEBUG: send test TAN from genesis wallet to any address, then mine one block."""
    if not settings.DEBUG:
        return JsonResponse({"ok": False, "error": "Faucet only in DEBUG"}, status=403)
    try:
        data = _read_json(request)
        addr = (data.get("address") or "").strip()
        amount_tan = str(data.get("amount_tan") or "2").strip()
        if not addr:
            return JsonResponse({"ok": False, "error": "address required"}, status=400)
        amount_sat = _tan_to_sat(amount_tan)
        fee_sat = 50_000  # implicit fee space from genesis UTXO split
        gw = node.get_genesis_wallet()
        if not gw:
            return JsonResponse({"ok": False, "error": "no genesis wallet"}, status=503)
        c = node.get_chain()
        utxos = c.get_utxos_for_address(gw.address())
        if not utxos:
            return JsonResponse(
                {"ok": False, "error": "genesis has no UTXO"}, status=503
            )
        sorted_utxos = sorted(utxos, key=lambda x: x["value"], reverse=True)
        selected_refs: list[tuple[bytes, int]] = []
        total_in = 0
        target_sat = amount_sat + fee_sat
        for u in sorted_utxos:
            txid = bytes.fromhex(u["txid"])
            idx = int(u["index"])
            prev = c.utxo.get((txid, idx))
            if not prev:
                continue
            selected_refs.append((txid, idx))
            total_in += prev.value
            if total_in >= target_sat:
                break
        if total_in < target_sat or not selected_refs:
            return JsonResponse(
                {"ok": False, "error": "genesis funds too low for this amount"},
                status=400,
            )
        change = total_in - target_sat
        tx = c.create_transfer(gw, addr, amount_sat, selected_refs, change)
        txid_hex = node.submit_transaction(tx.to_dict())
        b = node.mine_block(gw)
        return JsonResponse(
            {
                "ok": True,
                "txid": txid_hex,
                "block_hash": b.block_hash().hex(),
                "message": _(
                    "Test coins sent from the genesis wallet. Debug mode only."
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"ok": False, "error": _wallet_json_error(e)}, status=400)
