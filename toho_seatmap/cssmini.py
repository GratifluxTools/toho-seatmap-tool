"""座席ページ用 screen.css を解釈する最小限のCSSエンジン。

対応: タイプ/クラス/ID セレクタとその子孫結合、詳細度と記述順によるカスケード、
padding/margin の短縮記法、px 値。screen.css が使う範囲だけを扱う。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"^([a-zA-Z][\w-]*)?(#[\w-]+)?((?:\.[\w-]+)*)$")


@dataclass(frozen=True)
class Elem:
    tag: str | None = None
    id: str | None = None
    classes: tuple = ()


@dataclass
class Simple:
    tag: str | None
    id: str | None
    classes: tuple


@dataclass
class Rule:
    chain: list
    decls: dict
    spec: tuple
    order: int


def _strip_comments(t: str) -> str:
    return re.sub(r"/\*.*?\*/", "", t, flags=re.S)


def px(v):
    """'22px' / '22' / '0' -> float。それ以外(auto, % 等)は None。"""
    if v is None:
        return None
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(?:px)?\s*", str(v))
    return float(m.group(1)) if m else None


def _expand(prop: str, val: str) -> dict:
    prop = prop.strip().lower()
    val = re.sub(r"!important", "", val, flags=re.I).strip()
    if prop in ("padding", "margin"):
        parts = val.split()
        if not 1 <= len(parts) <= 4:
            return {}
        t, r, b, l = {1: lambda p: (p[0],) * 4, 2: lambda p: (p[0], p[1], p[0], p[1]),
                      3: lambda p: (p[0], p[1], p[2], p[1]), 4: lambda p: tuple(p)}[len(parts)](parts)
        return {f"{prop}-top": t, f"{prop}-right": r, f"{prop}-bottom": b, f"{prop}-left": l}
    return {prop: val}


def _parse_selector(sel: str):
    chain = []
    for tok in re.split(r"\s*>\s*|\s+", sel.strip()):
        if not tok:
            continue
        m = _TOKEN_RE.match(tok)
        if not m:
            return None  # 疑似クラス等は未対応 -> ルールごと無視
        tag, id_, cls = m.groups()
        chain.append(Simple(tag.lower() if tag else None, id_[1:] if id_ else None,
                            tuple(c for c in cls.split(".") if c)))
    return chain or None


def _spec(chain) -> tuple:
    return (sum(1 for s in chain if s.id), sum(len(s.classes) for s in chain), sum(1 for s in chain if s.tag))


def _simple_match(s: Simple, e: Elem) -> bool:
    if s.tag and e.tag and s.tag != e.tag:
        return False
    if s.id and s.id != e.id:
        return False
    return all(c in e.classes for c in s.classes)


def _chain_match(chain, elems) -> bool:
    if not elems or not _simple_match(chain[-1], elems[-1]):
        return False
    i = len(elems) - 2
    for s in reversed(chain[:-1]):
        while i >= 0 and not _simple_match(s, elems[i]):
            i -= 1
        if i < 0:
            return False
        i -= 1
    return True


@dataclass
class Sheet:
    rules: list = field(default_factory=list)

    def style_for(self, elems) -> dict:
        hit = [r for r in self.rules if _chain_match(r.chain, elems)]
        hit.sort(key=lambda r: (r.spec, r.order))
        out = {}
        for r in hit:
            out.update(r.decls)
        return out


def parse_css(text: str) -> Sheet:
    sheet, order = Sheet(), 0
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", _strip_comments(text)):
        decls = {}
        for d in m.group(2).split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                decls.update(_expand(k, v))
        for sel in m.group(1).split(","):
            chain = _parse_selector(sel)
            if chain:
                order += 1
                sheet.rules.append(Rule(chain, decls, _spec(chain), order))
    return sheet


def synth_sheet(cell_w: float) -> Sheet:
    """screen.css が無い場合の既定値 (同梱している46画面のCSSの共通項)。

    共通: `.screen-table td` は下余白7px、`td.paddingLeftN`(特別席ブロックを入れる結合セル)は
    下余白0。左余白は画面ごとに0〜14pxと異なるため中央値付近の7pxにしている。
    """
    return parse_css(
        f".screen-table td {{ padding: 0 0 7px 0; width: {cell_w:g}px; }}"
        ".screen-table td.paddingLeft1, .screen-table td.paddingLeft2, .screen-table td.paddingLeft3,"
        " .screen-table td.paddingLeft4, .screen-table td.paddingLeft5 { padding-left: 7px; padding-bottom: 0; }"
        ".screen-table td.paddingNoLeft { padding-left: 0; padding-bottom: 0; }"
        ".screen-table .wheel-td { padding-bottom: 0; }"
    )
