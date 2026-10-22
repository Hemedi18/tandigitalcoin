"""
Aggregate chain + mempool into structures for HTML templates.
All reads go through the same in-process node as the JSON API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext as _

from chain_api.services import node
from tancoin_core import constants
from tancoin_core.block import Block
from tancoin_core.crypto import address_from_pubkey_hash
from tancoin_core.transaction import OutputKind, Transaction


def _pkh_to_display_address(pkh: bytes) -> str:
    """Base58Check for 20-byte identifiers (UTXO recipients / contract ids)."""
    try:
        return address_from_pubkey_hash(pkh)
    except Exception:
        return pkh.hex()


def miner_address_from_block(block: Block) -> str | None:
    """Reward address from the first transaction (coinbase): first output recipient."""
    txs = block.transactions
    if not txs:
        return None
    cb = txs[0]
    if cb.inputs:
        return None
    outs = cb.outputs
    if not outs:
        return None
    try:
        return _pkh_to_display_address(outs[0].recipient_pubkey_hash)
    except Exception:
        return None


def satoshi_to_tan_str(value: int) -> str:
    return f"{value / constants.SATOSHIS_PER_COIN:.8f}".rstrip("0").rstrip(".")


def _chart_bar_pct(value: int, max_hint: int) -> int:
    """Bar height 4–100%; matches ``frontend/static/js/explorer.js`` ``pct()``."""
    if not max_hint or max_hint <= 0:
        return 4
    p = round((int(value) / int(max_hint)) * 100)
    return min(100, max(4, p))


@dataclass
class TxListRow:
    txid: str
    block_height: int | None
    block_hash: str | None
    block_timestamp: int | None
    tx_index: int | None
    is_coinbase: bool
    mempool: bool
    fee_satoshis: int | None
    output_count: int
    input_count: int


def _find_prev_output(chain, prev_txid: bytes, prev_index: int):
    """Historical output (UTXO set no longer contains spent coins)."""
    for b in chain.blocks:
        for t in b.transactions:
            if t.txid() == prev_txid and prev_index < len(t.outputs):
                return t.outputs[prev_index]
    return None


def _tx_fee_satoshis(tx: Transaction, chain) -> int | None:
    if not tx.inputs:
        return 0
    in_sum = 0
    for inp in tx.inputs:
        po = _find_prev_output(chain, inp.prev_txid, inp.prev_index)
        if po is None:
            return None
        in_sum += po.value
    return in_sum - sum(o.value for o in tx.outputs)


def build_tx_feed() -> list[dict[str, Any]]:
    """Newest activity first: mempool txs, then blocks from tip to genesis."""
    chain = node.get_chain()
    rows: list[dict[str, Any]] = []
    for tx in node.get_mempool():
        rows.append(
            {
                "tx": tx,
                "txid": tx.txid().hex(),
                "block_height": None,
                "block_hash": None,
                "block_timestamp": None,
                "tx_index": None,
                "is_coinbase": False,
                "mempool": True,
                "fee_satoshis": _tx_fee_satoshis(tx, chain),
            }
        )
    for height in range(chain.height, 0, -1):
        block = chain.blocks[height - 1]
        bh = block.block_hash().hex()
        ts = block.timestamp
        for idx in range(len(block.transactions) - 1, -1, -1):
            tx = block.transactions[idx]
            rows.append(
                {
                    "tx": tx,
                    "txid": tx.txid().hex(),
                    "block_height": height,
                    "block_hash": bh,
                    "block_timestamp": ts,
                    "tx_index": idx,
                    "is_coinbase": len(tx.inputs) == 0,
                    "mempool": False,
                    "fee_satoshis": _tx_fee_satoshis(tx, chain),
                }
            )
    return rows


def paginate_tx_feed(page: int, per_page: int) -> tuple[list[dict[str, Any]], int]:
    feed = build_tx_feed()
    total = len(feed)
    page = max(1, page)
    start = (page - 1) * per_page
    return feed[start : start + per_page], total


def block_chart_data(last_n: int = 24) -> list[dict[str, Any]]:
    """Bar chart: each block's transaction count."""
    chain = node.get_chain()
    blocks = chain.blocks[-last_n:]
    out = []
    for i, b in enumerate(blocks):
        height = chain.height - len(blocks) + i + 1
        cnt = len(b.transactions)
        out.append(
            {
                "height": height,
                "hash": b.block_hash().hex(),
                "tx_count": cnt,
                "max_hint": 1,
            }
        )
    max_tx = max((x["tx_count"] for x in out), default=1)
    for x in out:
        x["max_hint"] = max_tx
        x["bar_pct"] = _chart_bar_pct(x["tx_count"], max_tx)
    return out


def block_interval_chart_data(last_n: int = 24) -> list[dict[str, Any]]:
    """Bar chart: seconds between consecutive block timestamps (recent window)."""
    chain = node.get_chain()
    blocks = chain.blocks[-last_n:]
    out: list[dict[str, Any]] = []
    prev_ts: int | None = None
    for i, b in enumerate(blocks):
        height = chain.height - len(blocks) + i + 1
        ts = int(b.timestamp)
        delta = 0
        if prev_ts is not None:
            delta = max(0, ts - prev_ts)
        out.append({"height": height, "interval_s": delta})
        prev_ts = ts
    positives = [x["interval_s"] for x in out if x["interval_s"] > 0]
    max_i = max(positives, default=1)
    for x in out:
        x["max_hint"] = max_i
        x["bar_pct"] = _chart_bar_pct(x["interval_s"], max_i)
    return out


def block_outputs_chart_data(last_n: int = 24) -> list[dict[str, Any]]:
    """Bar chart: total outputs across all transactions in each block."""
    chain = node.get_chain()
    blocks = chain.blocks[-last_n:]
    out = []
    for i, b in enumerate(blocks):
        height = chain.height - len(blocks) + i + 1
        n = sum(len(tx.outputs) for tx in b.transactions)
        out.append({"height": height, "output_count": n, "max_hint": 1})
    mx = max((x["output_count"] for x in out), default=1)
    for x in out:
        x["max_hint"] = mx
        x["bar_pct"] = _chart_bar_pct(x["output_count"], mx)
    return out


def find_transaction(txid_hex: str) -> dict[str, Any] | None:
    tid = txid_hex.lower().removeprefix("0x")
    chain = node.get_chain()
    for height, block in enumerate(chain.blocks, start=1):
        for idx, tx in enumerate(block.transactions):
            if tx.txid().hex() == tid:
                return {
                    "tx": tx,
                    "block_height": height,
                    "block_hash": block.block_hash().hex(),
                    "block_timestamp": block.timestamp,
                    "tx_index": idx,
                    "mempool": False,
                }
    for tx in node.get_mempool():
        if tx.txid().hex() == tid:
            return {
                "tx": tx,
                "block_height": None,
                "block_hash": None,
                "block_timestamp": None,
                "tx_index": None,
                "mempool": True,
            }
    return None


def enrich_inputs_for_display(tx: Transaction, chain) -> list[dict[str, Any]]:
    """For each input, show amount + 'from' address (resolved from past blocks)."""
    rows = []
    for inp in tx.inputs:
        prev_out = _find_prev_output(chain, inp.prev_txid, inp.prev_index)
        amt = prev_out.value if prev_out else None
        addr = (
            _pkh_to_display_address(prev_out.recipient_pubkey_hash) if prev_out else "…"
        )
        rows.append(
            {
                "prev_txid": inp.prev_txid.hex(),
                "prev_index": inp.prev_index,
                "amount_satoshis": amt,
                "from_address": addr,
                "kind": prev_out.kind.value if prev_out else "unknown",
            }
        )
    return rows


def enrich_outputs_for_display(tx: Transaction) -> list[dict[str, Any]]:
    rows = []
    for i, o in enumerate(tx.outputs):
        rows.append(
            {
                "index": i,
                "amount_satoshis": o.value,
                "to_address": _pkh_to_display_address(o.recipient_pubkey_hash),
                "kind": o.kind.value,
                "payload_preview": (
                    (o.payload[:32].hex() + ("…" if len(o.payload) > 32 else ""))
                    if o.payload
                    else ""
                ),
            }
        )
    return rows


def txs_touching_address(address: str) -> list[dict[str, Any]]:
    """Outputs crediting this address (received), newest first; uses chain scan."""
    from tancoin_core import crypto

    chain = node.get_chain()
    pkh = crypto.pubkeyhash_from_address(address)
    hits = []
    for height, block in enumerate(chain.blocks, start=1):
        bh = block.block_hash().hex()
        for idx, tx in enumerate(block.transactions):
            for oi, o in enumerate(tx.outputs):
                if o.recipient_pubkey_hash == pkh:
                    hits.append(
                        {
                            "txid": tx.txid().hex(),
                            "block_height": height,
                            "block_hash": bh,
                            "output_index": oi,
                            "value": o.value,
                            "kind": o.kind.value,
                        }
                    )
    hits.reverse()
    return hits


def _output_value_per_block_chart_data(last_n: int = 72) -> list[dict[str, Any]]:
    """Per-block total output value (satoshis) for the last N blocks (bar chart)."""
    chain = node.get_chain()
    height = chain.height
    n = min(last_n, height)
    if n <= 0:
        return []
    blocks_slice = chain.blocks[-n:]
    rows: list[dict[str, Any]] = []
    for i, block in enumerate(blocks_slice):
        h = height - n + i + 1
        total = sum(sum(o.value for o in tx.outputs) for tx in block.transactions)
        rows.append({"height": h, "value_sat": total})
    max_v = max((r["value_sat"] for r in rows), default=1)
    for r in rows:
        r["bar_pct"] = _chart_bar_pct(r["value_sat"], max_v)
    return rows


def _conic_gradient_from_weights(items: list[tuple[int, str]]) -> str:
    """items: (weight, #hex color). Returns CSS conic-gradient() for a donut fill."""
    total = sum(w for w, _ in items if w > 0)
    if total <= 0:
        return "conic-gradient(#334155 0% 100%)"
    parts: list[str] = []
    start = 0.0
    for w, color in items:
        if w <= 0:
            continue
        frac = (w / total) * 100.0
        end = start + frac
        parts.append(f"{color} {start:.4f}% {end:.4f}%")
        start = end
    return f"conic-gradient({', '.join(parts)})"


def _pie_legend(
    weights: list[tuple[str, int]], colors: list[str]
) -> list[dict[str, Any]]:
    total = sum(w for _, w in weights if w > 0)
    out: list[dict[str, Any]] = []
    for i, (label, w) in enumerate(weights):
        if w <= 0:
            continue
        pct = round(100.0 * w / total, 2) if total else 0.0
        out.append(
            {"label": label, "value": w, "pct": pct, "color": colors[i % len(colors)]}
        )
    return out


def charts_analytics(
    last_n: int = 96,
    *,
    top_blocks_limit: int = 12,
    comparison_strip_n: int = 24,
) -> dict[str, Any]:
    """Deep chain + mempool aggregates for the Charts explorer page."""
    chain = node.get_chain()
    mempool = node.get_mempool()
    height = chain.height

    total_txs = 0
    total_outs = 0
    coinbases = 0
    total_out_val = 0
    total_in_edges = 0
    for b in chain.blocks:
        for tx in b.transactions:
            total_txs += 1
            if not tx.inputs:
                coinbases += 1
            total_outs += len(tx.outputs)
            total_in_edges += len(tx.inputs)
            total_out_val += sum(o.value for o in tx.outputs)

    transfers = max(0, total_txs - coinbases)
    avg_tx_per_block = round(total_txs / max(height, 1), 4)
    avg_out_per_tx = round(total_outs / max(total_txs, 1), 4)

    mp_tx = len(mempool)
    mp_inputs = sum(len(t.inputs) for t in mempool)
    mp_outputs = sum(len(t.outputs) for t in mempool)
    mp_out_val = sum(sum(o.value for o in t.outputs) for t in mempool)
    mp_fee_sum = 0
    mp_fee_n = 0
    for tx in mempool:
        if tx.inputs:
            f = _tx_fee_satoshis(tx, chain)
            if f is not None:
                mp_fee_sum += f
                mp_fee_n += 1

    n = min(last_n, height)
    blocks_slice = chain.blocks[-n:] if n else []
    window_rows: list[dict[str, Any]] = []
    prev_ts: int | None = None
    prev_idx = height - n - 1
    if prev_idx >= 0:
        prev_ts = int(chain.blocks[prev_idx].timestamp)

    for i, b in enumerate(blocks_slice):
        h = height - n + i + 1
        txs = b.transactions
        txc = len(txs)
        oc = sum(len(tx.outputs) for tx in txs)
        ic_s = sum(len(tx.inputs) for tx in txs)
        ov = sum(sum(o.value for o in tx.outputs) for tx in txs)
        cb = sum(1 for tx in txs if not tx.inputs)
        fs = 0
        fn = 0
        for tx in txs:
            if not tx.inputs:
                continue
            f = _tx_fee_satoshis(tx, chain)
            if f is not None:
                fs += f
                fn += 1
        ts = int(b.timestamp)
        interval = 0 if prev_ts is None else max(0, ts - prev_ts)
        maddr = miner_address_from_block(b)
        if maddr and len(maddr) > 18:
            mshort = f"{maddr[:10]}…{maddr[-6:]}"
        elif maddr:
            mshort = maddr
        else:
            mshort = "—"
        window_rows.append(
            {
                "height": h,
                "hash": b.block_hash().hex(),
                "timestamp": ts,
                "tx_count": txc,
                "output_count": oc,
                "input_sum": ic_s,
                "output_value_sat": ov,
                "coinbase_count": cb,
                "fee_sum_sat": fs,
                "fee_tx_count": fn,
                "interval_s": interval,
                "miner_address": maddr or "",
                "miner_short": mshort,
            }
        )
        prev_ts = ts

    max_fee = max((r["fee_sum_sat"] for r in window_rows), default=1)
    for r in window_rows:
        r["fee_bar_pct"] = _chart_bar_pct(r["fee_sum_sat"], max_fee)

    ints = [r["interval_s"] for r in window_rows if r["interval_s"] > 0]

    def _median(xs: list[int]) -> float:
        if not xs:
            return 0.0
        s = sorted(xs)
        m = len(s) // 2
        if len(s) % 2:
            return float(s[m])
        return (s[m - 1] + s[m]) / 2.0

    interval_stats = {
        "min": min(ints, default=0),
        "max": max(ints, default=0),
        "mean": round(sum(ints) / len(ints), 2) if ints else 0.0,
        "median": round(_median(ints), 2) if ints else 0.0,
        "samples": len(ints),
    }

    block_tx_ranked = [
        {
            "height": hi,
            "hash": blk.block_hash().hex(),
            "tx_count": len(blk.transactions),
        }
        for hi, blk in enumerate(chain.blocks, start=1)
    ]
    block_tx_ranked.sort(key=lambda x: -x["tx_count"])
    top_blocks = block_tx_ranked[: max(1, top_blocks_limit)]

    miner_counts: dict[str, int] = {}
    for b in chain.blocks:
        ma = miner_address_from_block(b)
        if ma:
            miner_counts[ma] = miner_counts.get(ma, 0) + 1
    hgt = max(height, 1)
    miner_sorted = sorted(miner_counts.items(), key=lambda x: -x[1])
    top_n = 10
    top_pairs = miner_sorted[:top_n]
    other_cnt = sum(c for _, c in miner_sorted[top_n:])
    miner_palette = [
        "#22d3ee",
        "#a78bfa",
        "#fb7185",
        "#34d399",
        "#fbbf24",
        "#60a5fa",
        "#f472b6",
        "#2dd4bf",
        "#818cf8",
        "#fcd34d",
    ]
    pie_miner_weights: list[tuple[str, int]] = []
    pie_miner_pairs: list[tuple[int, str]] = []
    for i, (addr, cnt) in enumerate(top_pairs):
        lab = f"{addr[:10]}…{addr[-6:]}" if len(addr) > 18 else addr
        pie_miner_weights.append((lab, cnt))
        pie_miner_pairs.append((cnt, miner_palette[i % len(miner_palette)]))
    if other_cnt > 0:
        pie_miner_weights.append((_("Other miners"), other_cnt))
        pie_miner_pairs.append((other_cnt, "#94a3b8"))
    if pie_miner_pairs:
        pie_miners: dict[str, Any] = {
            "conic": _conic_gradient_from_weights(pie_miner_pairs),
            "legend": _pie_legend(pie_miner_weights, [c for _, c in pie_miner_pairs]),
        }
    else:
        pie_miners = {
            "conic": _conic_gradient_from_weights([(1, "#64748b")]),
            "legend": _pie_legend([(_("No blocks yet"), 1)], ["#64748b"]),
        }
    miner_leaderboard = [
        {
            "address": addr,
            "address_short": f"{addr[:10]}…{addr[-6:]}" if len(addr) > 18 else addr,
            "blocks": cnt,
            "pct": round(100.0 * cnt / hgt, 2),
        }
        for addr, cnt in miner_sorted[:40]
    ]

    kind_counts: dict[str, int] = {}
    for b in chain.blocks:
        for tx in b.transactions:
            for o in tx.outputs:
                k = o.kind.value
                kind_counts[k] = kind_counts.get(k, 0) + 1
    for tx in mempool:
        for o in tx.outputs:
            k = o.kind.value
            kind_counts[k] = kind_counts.get(k, 0) + 1

    kind_label_keys = {
        OutputKind.TRANSFER.value: _("Transfer outputs"),
        OutputKind.CONTRACT_DEPLOY.value: _("Contract deploy outputs"),
        OutputKind.CONTRACT_CALL.value: _("Contract call outputs"),
    }
    kind_colors = ["#22d3ee", "#a78bfa", "#fb7185"]
    kind_weights: list[tuple[str, int]] = []
    kind_conic_pairs: list[tuple[int, str]] = []
    for i, kind in enumerate(OutputKind):
        c = int(kind_counts.get(kind.value, 0))
        kind_weights.append((kind_label_keys.get(kind.value, kind.value), c))
        kind_conic_pairs.append((c, kind_colors[i % len(kind_colors)]))

    fee_bucket_counts = [0, 0, 0]
    fee_bucket_labels = (
        _("Block fees: none"),
        _("Block fees: moderate"),
        _("Block fees: high"),
    )
    fee_bucket_colors = ["#64748b", "#38bdf8", "#c026d3"]
    for r in window_rows:
        fs = int(r["fee_sum_sat"])
        if fs <= 0:
            fee_bucket_counts[0] += 1
        elif fs < 50_000:
            fee_bucket_counts[1] += 1
        else:
            fee_bucket_counts[2] += 1
    fee_conic_pairs = [(fee_bucket_counts[i], fee_bucket_colors[i]) for i in range(3)]
    fee_legend_weights = [
        (fee_bucket_labels[i], fee_bucket_counts[i]) for i in range(3)
    ]

    pie_tx_role = {
        "conic": _conic_gradient_from_weights(
            [(coinbases, "#22d3ee"), (transfers, "#c084fc")]
        ),
        "legend": _pie_legend(
            [(_("Coinbase"), coinbases), (_("Transfers"), transfers)],
            ["#22d3ee", "#c084fc"],
        ),
    }
    pie_output_kinds = {
        "conic": _conic_gradient_from_weights(kind_conic_pairs),
        "legend": _pie_legend(kind_weights, kind_colors),
    }
    pie_fee_blocks = {
        "conic": _conic_gradient_from_weights(fee_conic_pairs),
        "legend": _pie_legend(fee_legend_weights, fee_bucket_colors),
    }

    hist_counts = [0, 0, 0, 0]
    hist_colors = ["#38bdf8", "#34d399", "#fbbf24", "#f97316"]
    for r in window_rows:
        c = int(r["tx_count"])
        if c <= 1:
            hist_counts[0] += 1
        elif c <= 3:
            hist_counts[1] += 1
        elif c <= 6:
            hist_counts[2] += 1
        else:
            hist_counts[3] += 1
    hist_labels = (
        _("1 transaction per block"),
        _("2–3 transactions per block"),
        _("4–6 transactions per block"),
        _("7+ transactions per block"),
    )
    hist_legend_weights = [(hist_labels[i], hist_counts[i]) for i in range(4)]
    hist_conic_pairs = [(hist_counts[i], hist_colors[i]) for i in range(4)]
    pie_tx_histogram = {
        "conic": _conic_gradient_from_weights(hist_conic_pairs),
        "legend": _pie_legend(hist_legend_weights, hist_colors),
    }

    cn = min(max(1, comparison_strip_n), len(window_rows))
    strip = window_rows[-cn:] if cn else []
    max_tx_s = max((r["tx_count"] for r in strip), default=1)
    max_ov_s = max((r["output_value_sat"] for r in strip), default=1)
    max_fee_s = max((r["fee_sum_sat"] for r in strip), default=1)
    comparison_strip = [
        {
            "height": r["height"],
            "tx_bar": _chart_bar_pct(r["tx_count"], max_tx_s),
            "out_bar": _chart_bar_pct(r["output_value_sat"], max_ov_s),
            "fee_bar": _chart_bar_pct(r["fee_sum_sat"], max_fee_s),
        }
        for r in strip
    ]

    return {
        "height": height,
        "block_count": height,
        "total_transactions": total_txs,
        "total_outputs": total_outs,
        "total_input_edges": total_in_edges,
        "coinbase_transactions": coinbases,
        "transfer_transactions": transfers,
        "total_output_value_sat": total_out_val,
        "avg_transactions_per_block": avg_tx_per_block,
        "avg_outputs_per_transaction": avg_out_per_tx,
        "utxo_count": len(chain.utxo),
        "contract_count": len(chain.contracts),
        "mempool": {
            "tx_count": mp_tx,
            "input_count": mp_inputs,
            "output_count": mp_outputs,
            "output_value_sat": mp_out_val,
            "fee_sum_sat": mp_fee_sum,
            "fee_tx_with_known_fee": mp_fee_n,
        },
        "window_last_n": n,
        "window_rows": window_rows,
        "interval_stats_window": interval_stats,
        "top_blocks_by_tx": top_blocks,
        "output_value_bars": _output_value_per_block_chart_data(min(72, last_n)),
        "pie_tx_role": pie_tx_role,
        "pie_output_kinds": pie_output_kinds,
        "pie_fee_blocks": pie_fee_blocks,
        "pie_tx_histogram": pie_tx_histogram,
        "comparison_strip": comparison_strip,
        "pie_miners": pie_miners,
        "miner_leaderboard": miner_leaderboard,
    }


def charts_live_snapshot(
    last_n: int = 120,
    n_bars: int = 72,
    tx_feed_limit: int = 80,
) -> dict[str, Any]:
    """JSON-serializable payload for the charts page auto-refresh endpoint."""
    summary = node.chain_summary()
    analytics = charts_analytics(last_n, top_blocks_limit=30, comparison_strip_n=48)
    block_chart = block_chart_data(n_bars)
    interval_chart = block_interval_chart_data(n_bars)
    outputs_chart = block_outputs_chart_data(n_bars)
    win = analytics["window_rows"]
    fee_chart = [
        {
            "height": r["height"],
            "bar_pct": r["fee_bar_pct"],
            "fee_sat": r["fee_sum_sat"],
            "max_hint": 1,
        }
        for r in win[-n_bars:]
    ]
    tip = summary["tip"]
    tip_short = f"{tip[:12]}…{tip[-6:]}" if len(tip) > 18 else tip

    feed, _ = paginate_tx_feed(1, tx_feed_limit)
    recent_txs: list[dict[str, Any]] = []
    for row in feed:
        tid = row["txid"]
        tx = row["tx"]
        fee = row.get("fee_satoshis")
        fee_tan = satoshi_to_tan_str(fee) if fee is not None else None
        recent_txs.append(
            {
                "txid": tid,
                "txid_short": f"{tid[:12]}…{tid[-6:]}",
                "mempool": row["mempool"],
                "block_height": row["block_height"],
                "fee_tan": fee_tan,
                "output_count": len(tx.outputs),
                "input_count": len(tx.inputs),
            }
        )

    mp = analytics["mempool"]
    stats = {
        "height": str(analytics["height"]),
        "total_transactions": str(analytics["total_transactions"]),
        "transfer_transactions": str(analytics["transfer_transactions"]),
        "coinbase_transactions": str(analytics["coinbase_transactions"]),
        "total_outputs": str(analytics["total_outputs"]),
        "total_input_edges": str(analytics["total_input_edges"]),
        "total_output_value_tan": f"{satoshi_to_tan_str(analytics['total_output_value_sat'])} TAN",
        "avg_tx_per_block": str(analytics["avg_transactions_per_block"]),
        "avg_out_per_tx": str(analytics["avg_outputs_per_transaction"]),
        "utxo_count": str(analytics["utxo_count"]),
        "contract_count": str(analytics["contract_count"]),
        "mempool_tx": str(mp["tx_count"]),
        "mempool_inputs": str(mp["input_count"]),
        "mempool_outputs": str(mp["output_count"]),
        "mempool_value_tan": f"{satoshi_to_tan_str(mp['output_value_sat'])} TAN",
        "mempool_fee_tan": (
            f"{satoshi_to_tan_str(mp['fee_sum_sat'])} TAN"
            if mp["fee_sum_sat"]
            else "0 TAN"
        ),
        "mempool_fee_tx": str(mp["fee_tx_with_known_fee"]),
        "reference_price_usd": str(summary["reference_price_usd"]),
        "initial_difficulty_bits": str(summary["initial_difficulty_bits"]),
    }

    window_json: list[dict[str, Any]] = []
    for r in win:
        window_json.append(
            {
                "height": r["height"],
                "hash": r["hash"],
                "tx_count": r["tx_count"],
                "output_count": r["output_count"],
                "input_sum": r["input_sum"],
                "output_value_sat": r["output_value_sat"],
                "output_value_tan": satoshi_to_tan_str(r["output_value_sat"]),
                "fee_sum_sat": r["fee_sum_sat"],
                "fee_tan": (
                    satoshi_to_tan_str(r["fee_sum_sat"]) if r["fee_sum_sat"] else "0"
                ),
                "interval_s": r["interval_s"],
                "miner_address": r.get("miner_address") or "",
                "miner_short": r.get("miner_short") or "—",
            }
        )

    return {
        "height": summary["height"],
        "mempool": summary["mempool_count"],
        "tip_short": tip_short,
        "reference_price_usd": str(summary["reference_price_usd"]),
        "initial_difficulty_bits": str(summary["initial_difficulty_bits"]),
        "stats": stats,
        "block_chart": block_chart,
        "interval_chart": interval_chart,
        "outputs_chart": outputs_chart,
        "fee_chart": fee_chart,
        "output_value_bars": analytics["output_value_bars"],
        "pie_tx_role": analytics["pie_tx_role"],
        "pie_output_kinds": analytics["pie_output_kinds"],
        "pie_fee_blocks": analytics["pie_fee_blocks"],
        "pie_tx_histogram": analytics["pie_tx_histogram"],
        "pie_miners": analytics["pie_miners"],
        "miner_leaderboard": analytics["miner_leaderboard"],
        "comparison_strip": analytics["comparison_strip"],
        "window_rows": window_json,
        "top_blocks_by_tx": analytics["top_blocks_by_tx"],
        "interval_stats": analytics["interval_stats_window"],
        "recent_txs": recent_txs,
    }
