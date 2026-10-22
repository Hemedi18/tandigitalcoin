#!/usr/bin/env python3
"""Fill django.po msgstr using batched machine translation (one request per chunk)."""

from __future__ import annotations

import argparse
import sys
import time

import polib
from deep_translator import GoogleTranslator

SEP = "\x1e"  # record separator — not used in our msgids


def chunk_msgids(msgids: list[str], max_chars: int = 3800) -> list[list[str]]:
    chunks: list[list[str]] = []
    cur: list[str] = []
    n = 0
    for m in msgids:
        piece = len(m) + (1 if cur else 0)
        if cur and n + piece > max_chars:
            chunks.append(cur)
            cur = []
            n = 0
        cur.append(m)
        n += len(m) + (1 if len(cur) > 1 else 0)
    if cur:
        chunks.append(cur)
    return chunks


def translate_chunk(tr: GoogleTranslator, parts: list[str]) -> list[str]:
    joined = SEP.join(parts)
    out = tr.translate(joined)
    got = out.split(SEP)
    if len(got) == len(parts):
        return got
    # Fallback: per-string if API merged or dropped separators
    return [tr.translate(p) for p in parts]


def fill(path: str, target: str) -> None:
    po = polib.pofile(path)
    entries = [e for e in po if e.msgid]
    msgids = [e.msgid for e in entries]
    chunks = chunk_msgids(msgids)
    tr = GoogleTranslator(source="en", target=target)
    mapping: dict[str, str] = {}
    for i, chunk in enumerate(chunks):
        try:
            outs = translate_chunk(tr, chunk)
        except Exception as e:
            print("chunk fail", i, e, file=sys.stderr)
            outs = chunk
        for a, b in zip(chunk, outs):
            mapping[a] = b
        time.sleep(0.35)
        if (i + 1) % 5 == 0:
            print(f"{target}: chunks {i + 1}/{len(chunks)}", file=sys.stderr)

    for e in entries:
        e.msgstr = mapping.get(e.msgid, e.msgid)

    po.metadata["Language"] = target
    po.metadata["Project-Id-Version"] = "Tancoin"
    po.save(path)
    print("saved", path)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("po_path")
    p.add_argument(
        "--lang", required=True, help="Google translate target code, e.g. sw or ar"
    )
    args = p.parse_args()
    fill(args.po_path, args.lang)


if __name__ == "__main__":
    main()
