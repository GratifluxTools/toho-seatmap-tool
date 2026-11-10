"""入れ子<table>を、ブラウザの表レイアウト(auto)に近い形で画素座標に展開する。

CSS(screen.css)があればそのpadding/widthを使って位置を決める。背景画像(screen.gif)の
行記号・通路・出口表示と座席が一致するためには、この位置の再現が必要になる。
CSSが無い画面は、他画面のCSSから抽出した既定値(synth_sheet)で近似する。
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .cssmini import Elem, Sheet, parse_inline, px, synth_sheet
from .htmltable import Cell, Img, Table
from .seatmodel import Seat, classify, is_spacer

DEFAULT_SEAT = (15.0, 22.0)


@dataclass
class Placed:
    x: float
    y: float
    w: float
    h: float
    seat: Seat


@dataclass
class Box:
    w: float
    h: float
    seats: list = field(default_factory=list)


def _size(attrs: dict, default=DEFAULT_SEAT):
    def num(v, d):
        try:
            return float(str(v).strip().rstrip("px"))
        except (TypeError, ValueError):
            return d

    return num(attrs.get("width"), default[0]), num(attrs.get("height"), default[1])


def modal_seat_width(tables) -> float:
    cnt = Counter()

    def walk(t):
        for row in t.rows:
            for cell in row.cells:
                for it in cell.items:
                    if isinstance(it, Img) and classify(it.attrs) is not None:
                        cnt[_size(it.attrs)[0]] += 1
                    elif isinstance(it, Table):
                        walk(it)

    for t in tables:
        walk(t)
    return cnt.most_common(1)[0][0] if cnt else DEFAULT_SEAT[0]


def _elem(tag, attrs) -> Elem:
    return Elem(tag, attrs.get("id") or None, tuple((attrs.get("class") or "").split()))


def _int(v, d):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return d


def _percent(v):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*", v or "")
    return float(m.group(1)) / 100.0 if m else None


class _Cell:
    __slots__ = ("r", "c", "rs", "cs", "cell", "pl", "pr", "pt", "pb", "cw", "chh", "parts", "cont_w", "cont_h",
                 "halign", "valign", "dx", "dy", "tr")


def _flow(parts):
    """内容を行に分ける。連続する画像は横並び(inline)、表は単独行(block)。"""
    lines, cur = [], []
    for p in parts:
        if p[0] == "table":
            if cur:
                lines.append(cur)
                cur = []
            lines.append([p])
        else:
            cur.append(p)
    if cur:
        lines.append(cur)
    return lines


def layout_table(table: Table, sheet: Sheet, ancestors, target_w: float | None = None) -> Box:
    t_el = _elem("table", table.attrs)
    anc = list(ancestors) + [t_el]
    # cellspacing 属性が無い表のセル間隔は0とする。ブラウザの既定は2pxだが、実際の座席ページは
    # 属性の無い入れ子の表(西宮2のL列など)でも0間隔で表示される(サイト共通CSSでリセットされている)。
    spacing = _int(table.attrs.get("cellspacing"), 0.0)
    cpad = _int(table.attrs.get("cellpadding"), 1.0)
    nrows = len(table.rows)

    occ, gcells = set(), []
    for r, row in enumerate(table.rows):
        tr_el = _elem("tr", row.attrs)
        c = 0
        for cell in row.cells:
            while (r, c) in occ:
                c += 1
            g = _Cell()
            g.r, g.c, g.cell, g.tr = r, c, cell, tr_el
            g.rs, g.cs = min(cell.rowspan, nrows - r), cell.colspan
            for dr in range(g.rs):
                for dc in range(g.cs):
                    occ.add((r + dr, c + dc))
            st = sheet.style_for(anc + [tr_el, _elem("td", cell.attrs)])
            st.update(parse_inline(cell.attrs.get("style")))  # HTML内の style 属性が最優先
            g.pt = px(st.get("padding-top")) if px(st.get("padding-top")) is not None else cpad
            g.pr = px(st.get("padding-right")) if px(st.get("padding-right")) is not None else cpad
            g.pb = px(st.get("padding-bottom")) if px(st.get("padding-bottom")) is not None else cpad
            g.pl = px(st.get("padding-left")) if px(st.get("padding-left")) is not None else cpad
            g.cw, g.chh = px(st.get("width")), px(st.get("height"))
            # position: relative は配置(レイアウト)を変えず、描画だけを left/top 等の分ずらす
            g.dx = g.dy = 0.0
            if (st.get("position") or "").lower() == "relative":
                lf, rt = px(st.get("left")), px(st.get("right"))
                tp, bt = px(st.get("top")), px(st.get("bottom"))
                g.dx = lf if lf is not None else (-rt if rt is not None else 0.0)
                g.dy = tp if tp is not None else (-bt if bt is not None else 0.0)
            g.halign = (st.get("text-align") or cell.attrs.get("align") or "left").lower()
            g.valign = (st.get("vertical-align") or cell.attrs.get("valign") or "middle").lower()
            parts = []
            for it in cell.items:
                if isinstance(it, Img):
                    seat = classify(it.attrs)
                    if seat is not None:
                        w, h = _size(it.attrs)
                        parts.append(("seat", seat, w, h))
                    elif is_spacer(it.attrs):
                        w, h = _size(it.attrs, (0, 0))
                        parts.append(("space", None, w, h))
                elif isinstance(it, Table):
                    box = layout_table(it, sheet, anc + [tr_el, _elem("td", cell.attrs)])
                    parts.append(("table", it, box.w, box.h))
            g.parts = parts
            lines = _flow(parts)
            g.cont_w = max((sum(p[2] for p in ln) for ln in lines), default=0.0)
            g.cont_h = sum(max(p[3] for p in ln) for ln in lines)
            gcells.append(g)
            c += g.cs
    ncols = max((g.c + g.cs for g in gcells), default=0)
    if nrows == 0 or ncols == 0:
        return Box(0, 0, [])

    def outer_w(g):
        return g.pl + g.pr + max(g.cont_w, g.cw or 0.0)

    def outer_h(g):
        return g.pt + g.pb + max(g.cont_h, g.chh or 0.0)

    colw = [0.0] * ncols
    rowh = [0.0] * nrows
    for g in gcells:
        if g.cs == 1:
            colw[g.c] = max(colw[g.c], outer_w(g))
        if g.rs == 1:
            rowh[g.r] = max(rowh[g.r], outer_h(g))
    for g in sorted(gcells, key=lambda g: g.rs * g.cs):
        if g.cs > 1:
            deficit = outer_w(g) - (sum(colw[g.c : g.c + g.cs]) + spacing * (g.cs - 1))
            if deficit > 0:
                _spread(colw, g.c, g.cs, deficit)
        if g.rs > 1:
            deficit = outer_h(g) - (sum(rowh[g.r : g.r + g.rs]) + spacing * (g.rs - 1))
            if deficit > 0:
                _spread(rowh, g.r, g.rs, deficit)  # ブラウザ同様、結合した全行に比例配分

    px_w = px(table.attrs.get("width"))
    want = target_w
    if px_w and (want is None or px_w > want):
        want = px_w
    total = sum(colw) + spacing * (ncols + 1)
    if want and want > total:
        _spread(colw, 0, ncols, want - total)

    xs = [spacing]
    for w in colw:
        xs.append(xs[-1] + w + spacing)
    ys = [spacing]
    for h in rowh:
        ys.append(ys[-1] + h + spacing)

    seats = []
    for g in gcells:
        sw = xs[g.c + g.cs] - spacing - xs[g.c]
        sh = ys[g.r + g.rs] - spacing - ys[g.r]
        bx, by = xs[g.c] + g.pl, ys[g.r] + g.pt
        bw, bh = sw - g.pl - g.pr, sh - g.pt - g.pb
        lines = _flow(g.parts)
        if g.valign == "top":
            y = by
        elif g.valign == "bottom":
            y = by + bh - g.cont_h
        else:
            y = by + max(0.0, (bh - g.cont_h) / 2)
        for ln in lines:
            lh = max(p[3] for p in ln)
            lw = sum(p[2] for p in ln)
            align = g.halign
            if ln[0][0] == "table":
                # 入れ子の表は自身の align 属性(left/center/right)がセルの配置より優先される
                ta = (ln[0][1].attrs.get("align") or "").lower()
                if ta not in ("left", "center", "right"):
                    # style="margin:0 auto" など(左右 auto)での中央寄せ・右寄せ
                    mg = parse_inline(ln[0][1].attrs.get("style"))
                    ml, mr = mg.get("margin-left"), mg.get("margin-right")
                    if ml == "auto" and mr == "auto":
                        ta = "center"
                    elif ml == "auto":
                        ta = "right"
                if ta in ("left", "center", "right"):
                    align = ta
            if align in ("center", "-webkit-center"):
                x = bx + (bw - lw) / 2
            elif align == "right":
                x = bx + bw - lw
            else:
                x = bx
            for kind, obj, w, h in ln:
                if kind == "seat":
                    seats.append(Placed(x + g.dx, y + (lh - h) / 2 + g.dy, w, h, obj))
                elif kind == "table":
                    pct = _percent(obj.attrs.get("width"))
                    box = layout_table(obj, sheet, anc + [g.tr, _elem("td", g.cell.attrs)],
                                       target_w=bw * pct if pct else None)
                    for p in box.seats:
                        seats.append(Placed(x + p.x + g.dx, y + p.y + g.dy, p.w, p.h, p.seat))
                    w, h = box.w, box.h
                x += w
            y += lh
    return Box(xs[-1], ys[-1], seats)


def _spread(colw, c, n, extra):
    """余剰幅を既存の列幅に比例して配る(全て0なら均等)。"""
    cur = sum(colw[c : c + n])
    for k in range(c, c + n):
        colw[k] += extra * (colw[k] / cur) if cur > 0 else extra / n


def layout_tables(tables, sheet: Sheet | None = None) -> Box:
    """トップレベルの表を上から順に積む(ブロック要素、左揃え)。位置は切り詰めない。"""
    if sheet is None:
        sheet = synth_sheet(modal_seat_width(tables))
    root = [Elem("div", "screen-table-1")]
    seats, y, width = [], 0.0, 0.0
    for t in tables:
        b = layout_table(t, sheet, root)
        seats += [Placed(p.x, p.y + y, p.w, p.h, p.seat) for p in b.seats]
        y += b.h
        width = max(width, b.w)
    return Box(width, y, seats)


def trim_box(box: Box, gap: float = 0.0) -> Box:
    """座席の外接矩形に合わせて余白を除く (背景画像を使わない描画用)。"""
    if not box.seats:
        return box
    x0 = min(p.x for p in box.seats)
    y0 = min(p.y for p in box.seats)
    x1 = max(p.x + p.w for p in box.seats)
    y1 = max(p.y + p.h for p in box.seats)
    return Box(x1 - x0, y1 - y0, [Placed(p.x - x0, p.y - y0, p.w, p.h, p.seat) for p in box.seats])
