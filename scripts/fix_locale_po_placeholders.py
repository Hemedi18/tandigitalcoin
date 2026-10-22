#!/usr/bin/env python3
"""
Normalize locale/*/LC_MESSAGES/django.po after `makemessages`.

Django's makemessages often writes python-format msgids as `%%(name)s` and marks
entries fuzzy when msgid changes; fuzzy + %% breaks runtime interpolation so
users see literal `%(h)s` on the site.

Run after every `makemessages` for sw/ar (or all locales):

    python scripts/fix_locale_po_placeholders.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE_ROOT = ROOT / "locale"


def defuzz_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#, fuzzy, python-format"):
            out.append("#, python-format\n")
            i += 1
            while i < len(lines) and lines[i].startswith("#|"):
                i += 1
            continue
        if line.startswith("#, fuzzy"):
            i += 1
            while i < len(lines) and lines[i].startswith("#|"):
                i += 1
            continue
        out.append(line)
        i += 1
    return out


def fix_broken_total_msgid(text: str) -> str:
    """Merge a line-broken `Total: %%` + `(total)s` msgid into one valid %(total)s line."""
    old = (
        'msgid ""\n'
        '"Public feed: unconfirmed first, then confirmed newest first. Total: %%"\n'
        '"(total)s."'
    )
    new = (
        'msgid ""\n'
        '"Public feed: unconfirmed first, then confirmed newest first. Total: %(total)s."'
    )
    return text.replace(old, new)


def process_po(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    raw = fix_broken_total_msgid(raw)
    lines = raw.splitlines(keepends=True)
    lines = defuzz_lines(lines)
    text = "".join(lines)
    # Do NOT replace "%%(" with "%(" in .po: Django's old %(var)s inside
    # blocktrans doubles literal "%" in the gettext key; mangling msgid breaks lookups.
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if not LOCALE_ROOT.is_dir():
        raise SystemExit(f"Missing {LOCALE_ROOT}")
    for po in sorted(LOCALE_ROOT.glob("*/LC_MESSAGES/django.po")):
        process_po(po)
        print("processed", po.relative_to(ROOT))


if __name__ == "__main__":
    main()
