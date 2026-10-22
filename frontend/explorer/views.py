"""
HTML explorer views: read-only presentation of public chain state.
Templates extend ``common/base.html``; styles in ``static/css/explorer.css``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render

from tancoin_core.crypto import pubkeyhash_from_address

from chain_api.services import node
from frontend.explorer.services import explorer_data


def home(request):
    """Dashboard: network stats, chart, latest blocks & transactions."""
    chain = node.get_chain()
    summary = node.chain_summary()
    start = max(0, chain.height - 12)
    recent_blocks = [(h + 1, chain.blocks[h]) for h in range(start, chain.height)]
    recent_blocks.reverse()
    feed, _ = explorer_data.paginate_tx_feed(1, 15)
    chart = explorer_data.block_chart_data(24)
    interval_chart = explorer_data.block_interval_chart_data(24)
    outputs_chart = explorer_data.block_outputs_chart_data(24)
    return render(
        request,
        "explorer/home.html",
        {
            "summary": summary,
            "recent_blocks": recent_blocks,  # list of (height, block)
            "recent_txs": feed,
            "block_chart": chart,
            "interval_chart": interval_chart,
            "outputs_chart": outputs_chart,
            "chain": chain,
        },
    )


def home_live_json(request):
    """JSON snapshot for home dashboard auto-refresh (no-cache)."""
    chain = node.get_chain()
    summary = node.chain_summary()
    chart = explorer_data.block_chart_data(24)
    interval_chart = explorer_data.block_interval_chart_data(24)
    outputs_chart = explorer_data.block_outputs_chart_data(24)
    start = max(0, chain.height - 10)
    recent_blocks = []
    for h in range(start, chain.height):
        blk = chain.blocks[h]
        hx = blk.block_hash().hex()
        recent_blocks.append(
            {
                "height": h + 1,
                "hash": hx,
                "hash_short": f"{hx[:8]}…{hx[-6:]}",
                "txs": len(blk.transactions),
                "ts": blk.timestamp,
            }
        )
    recent_blocks.reverse()
    feed, _ = explorer_data.paginate_tx_feed(1, 12)
    recent_txs = []
    for row in feed:
        fee = None
        if row.get("fee_satoshis") is not None:
            fee = explorer_data.satoshi_to_tan_str(row["fee_satoshis"])
        tid = row["txid"]
        recent_txs.append(
            {
                "txid": tid,
                "txid_short": f"{tid[:10]}…{tid[-6:]}",
                "mempool": row["mempool"],
                "block_height": row["block_height"],
                "fee_tan": fee,
            }
        )
    tip = summary["tip"]
    tip_short = f"{tip[:10]}…{tip[-4:]}" if len(tip) > 16 else tip
    payload = {
        "height": summary["height"],
        "mempool": summary["mempool_count"],
        "tip_short": tip_short,
        "reference_price_usd": summary["reference_price_usd"],
        "initial_difficulty_bits": summary["initial_difficulty_bits"],
        "block_chart": chart,
        "interval_chart": interval_chart,
        "outputs_chart": outputs_chart,
        "recent_blocks": recent_blocks,
        "recent_txs": recent_txs,
    }
    resp = JsonResponse(payload)
    resp["Cache-Control"] = "no-store"
    return resp


def blocks_list(request):
    """All blocks, newest first (paginated)."""
    chain = node.get_chain()
    rows: list[dict[str, Any]] = []
    for idx in range(chain.height - 1, -1, -1):
        blk = chain.blocks[idx]
        ma = explorer_data.miner_address_from_block(blk)
        if ma and len(ma) > 18:
            mshort = f"{ma[:10]}…{ma[-6:]}"
        elif ma:
            mshort = ma
        else:
            mshort = "—"
        rows.append(
            {
                "height": idx + 1,
                "block": blk,
                "miner_address": ma or "",
                "miner_short": mshort,
            }
        )
    paginator = Paginator(rows, 25)
    page = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "explorer/blocks_list.html",
        {"page_obj": page, "paginator": paginator, "chain": chain},
    )


def block_detail(request, block_hash: str):
    """Single block with all contained transactions."""
    h = block_hash.lower().removeprefix("0x")
    chain = node.get_chain()
    for height, block in enumerate(chain.blocks, start=1):
        if block.block_hash().hex() == h:
            prev_ts = None
            if height > 1:
                prev_ts = int(chain.blocks[height - 2].timestamp)
            interval_after_prev_s = None
            if prev_ts is not None:
                interval_after_prev_s = max(0, int(block.timestamp) - prev_ts)
            next_height = None
            next_hash_hex = None
            if height < chain.height:
                nb = chain.blocks[height]
                next_height = height + 1
                next_hash_hex = nb.block_hash().hex()
            txs = block.transactions
            n_tx = len(txs)
            n_coinbase = sum(1 for tx in txs if len(tx.inputs) == 0)
            n_transfer = n_tx - n_coinbase
            total_outputs = sum(len(tx.outputs) for tx in txs)
            total_value_sat = sum(o.value for tx in txs for o in tx.outputs)
            tx_rows = [
                {
                    "tx": tx,
                    "out_n": len(tx.outputs),
                    "out_value_sat": sum(o.value for o in tx.outputs),
                }
                for tx in txs
            ]
            block_json = json.dumps(block.to_dict(), indent=2)
            miner_addr = explorer_data.miner_address_from_block(block)
            if miner_addr and len(miner_addr) > 18:
                miner_short = f"{miner_addr[:10]}…{miner_addr[-6:]}"
            elif miner_addr:
                miner_short = miner_addr
            else:
                miner_short = None
            return render(
                request,
                "explorer/block_detail.html",
                {
                    # Not named "block": Django injects `block` as the {% block %} node inside extended templates.
                    "chain_block": block,
                    "height": height,
                    "chain": chain,
                    "interval_after_prev_s": interval_after_prev_s,
                    "next_height": next_height,
                    "next_hash_hex": next_hash_hex,
                    "n_tx": n_tx,
                    "n_coinbase": n_coinbase,
                    "n_transfer": n_transfer,
                    "total_outputs": total_outputs,
                    "total_value_sat": total_value_sat,
                    "tx_rows": tx_rows,
                    "block_json": block_json,
                    "miner_address": miner_addr,
                    "miner_short": miner_short,
                },
            )
    raise Http404("Block not found")


def transactions_list(request):
    """Public feed of all transactions (chain + mempool), paginated."""
    page_num = max(1, int(request.GET.get("page") or 1))
    per_page = 35
    slice_rows, total = explorer_data.paginate_tx_feed(page_num, per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page_num = min(page_num, total_pages)
    slice_rows, total = explorer_data.paginate_tx_feed(page_num, per_page)
    return render(
        request,
        "explorer/transactions_list.html",
        {
            "rows": slice_rows,
            "total_tx": total,
            "page": page_num,
            "total_pages": total_pages,
            "has_prev": page_num > 1,
            "has_next": page_num < total_pages,
        },
    )


def transaction_detail(request, txid: str):
    """One transaction with graphical input/output flow."""
    info = explorer_data.find_transaction(txid)
    if not info:
        raise Http404("Transaction not found")
    tx = info["tx"]
    chain = node.get_chain()
    inputs = explorer_data.enrich_inputs_for_display(tx, chain)
    outputs = explorer_data.enrich_outputs_for_display(tx)
    total_in = sum(i["amount_satoshis"] or 0 for i in inputs)
    total_out = sum(o["amount_satoshis"] for o in outputs)
    if not tx.inputs:
        fee = 0
    else:
        fee = total_in - total_out
    return render(
        request,
        "explorer/transaction_detail.html",
        {
            "info": info,
            "tx": tx,
            "tx_json": json.dumps(tx.to_dict(), indent=2),
            "inputs": inputs,
            "outputs": outputs,
            "total_in": total_in,
            "total_out": total_out,
            "fee": fee,
        },
    )


def address_detail(request, address: str):
    """Address: UTXO set + received transaction history (public)."""
    chain = node.get_chain()
    try:
        utxos = chain.get_utxos_for_address(address)
    except Exception as exc:
        return render(
            request,
            "explorer/address_detail.html",
            {"error": str(exc), "address": address},
        )
    history = explorer_data.txs_touching_address(address)
    return render(
        request,
        "explorer/address_detail.html",
        {"address": address, "utxos": utxos, "history": history, "chain": chain},
    )


def api_help(request):
    """In-browser pointer to JSON API routes (complements /docs/)."""
    return render(request, "explorer/api_help.html", {})


def participate(request):
    """How to pay, mine, and manage a wallet — short guide with links to the full doc."""
    return render(request, "explorer/participate.html", {})


def search_redirect(request):
    """Global explorer search: txid (64 hex), block hash (64 hex), or Base58 address."""
    q = (request.GET.get("q") or "").strip()
    if not q:
        return redirect("explorer:home")
    q_hex = q.lower().removeprefix("0x")
    if re.fullmatch(r"[0-9a-f]{64}", q_hex):
        if explorer_data.find_transaction(q_hex):
            return redirect("explorer:transaction", txid=q_hex)
        chain = node.get_chain()
        for b in chain.blocks:
            if b.block_hash().hex() == q_hex:
                return redirect("explorer:block", block_hash=q_hex)
        return redirect("explorer:home")
    try:
        pubkeyhash_from_address(q)
    except ValueError:
        return redirect("explorer:home")
    return redirect("explorer:address", address=q)


def charts(request):
    """Deep chain, block-window, and mempool analytics with bar charts."""
    summary = node.chain_summary()
    analytics = explorer_data.charts_analytics(
        120, top_blocks_limit=30, comparison_strip_n=48
    )
    n_bars = 72
    block_chart = explorer_data.block_chart_data(n_bars)
    interval_chart = explorer_data.block_interval_chart_data(n_bars)
    outputs_chart = explorer_data.block_outputs_chart_data(n_bars)
    win = analytics["window_rows"]
    fee_chart = [
        {
            "height": r["height"],
            "bar_pct": r["fee_bar_pct"],
            "fee_sat": r["fee_sum_sat"],
        }
        for r in win[-n_bars:]
    ]
    recent_tx_feed, _ = explorer_data.paginate_tx_feed(1, 80)
    return render(
        request,
        "explorer/charts.html",
        {
            "summary": summary,
            "analytics": analytics,
            "block_chart": block_chart,
            "interval_chart": interval_chart,
            "outputs_chart": outputs_chart,
            "fee_chart": fee_chart,
            "recent_tx_feed": recent_tx_feed,
        },
    )


def charts_live_json(request):
    """JSON snapshot for charts page auto-refresh (no-cache)."""
    payload = explorer_data.charts_live_snapshot()
    resp = JsonResponse(payload)
    resp["Cache-Control"] = "no-store"
    return resp


def mempool(request):
    """Pending transactions on this node (mempool)."""
    chain = node.get_chain()
    summary = node.chain_summary()
    rows: list[dict[str, Any]] = []
    for tx in node.get_mempool():
        tid = tx.txid().hex()
        fee = explorer_data._tx_fee_satoshis(tx, chain) if tx.inputs else None
        rows.append(
            {
                "txid": tid,
                "tx": tx,
                "input_count": len(tx.inputs),
                "output_count": len(tx.outputs),
                "fee_sat": fee,
            }
        )
    return render(
        request,
        "explorer/mempool.html",
        {"rows": rows, "summary": summary},
    )
