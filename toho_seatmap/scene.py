"""座席レイアウトから、描画バックエンド非依存の図形リスト(Scene)を作る。"""
from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .layout import Box
from .styles import label_of, style_of

MARGIN = 20.0
LABEL_W = 13.0


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float
    r: float = 0
    fill: str | None = None
    stroke: str | None = None
    sw: float = 1


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    color: str = "#000"
    w: float = 1


@dataclass
class Circle:
    cx: float
    cy: float
    r: float
    fill: str | None = None
    stroke: str | None = None
    sw: float = 1


@dataclass
class Text:
    x: float
    y: float
    s: str
    size: float = 8
    anchor: str = "middle"  # start | middle | end
    color: str = "#222"
    bold: bool = False


@dataclass
class Img:
    """画像(座席gif・背景gif)。keyで Scene.images を引く。"""

    x: float
    y: float
    w: float
    h: float
    key: str


@dataclass
class Begin:
    """グループの開始(SVGの <g>)。PNG/WebP では無視される。レイヤー・行・座席1席ずつを表す。"""

    id: str
    attrs: dict = field(default_factory=dict)
    title: str | None = None


@dataclass
class End:
    """Begin に対応するグループの終了。"""


@dataclass
class Scene:
    w: float
    h: float
    items: list = field(default_factory=list)
    bg: str = "#FFFFFF"
    images: dict = field(default_factory=dict)  # key -> PIL.Image (RGBA)
    ss: int = 2  # PNG描画時のスーパーサンプリング倍率
    inline_images: bool = False  # SVGで画像を <use> でなく座席ごとの <image> として埋め込む(オブジェクト化)


@dataclass
class Options:
    show_numbers: bool = True
    blocked_mode: str = "mark"  # mark | normal | hide
    lang: str = "ja"  # 画像内の文言 (日本語フォントが無い時は en)
    style: str = "official"  # official=公式風(背景gif+座席gif) | plain=ベクター描画(明るい配色)
    show_title: bool = True
    show_legend: bool = True
    svg_objects: bool = False  # SVG: 座席を1席ずつ選択できるオブジェクト(グループ)として出力


def layer_begin(name: str, label: str) -> Begin:
    """Inkscape/Illustrator でレイヤーとして扱われるグループ。"""
    return Begin(f"layer-{name}", {"inkscape:groupmode": "layer", "inkscape:label": label})


def group_by_row(placed) -> list:
    """座席を行記号ごとにまとめる (出現順。車いす席は 'HC')。"""
    rows = {}
    for p in placed:
        rows.setdefault(p.seat.row, []).append(p)
    return list(rows.items())


def seat_marker(p, used: set, blocked: bool, lang: str) -> Begin:
    """座席1席ぶんのグループ。id=seat-A-16、data-* に行・番号・席種を持たせ、title で名称を表示。"""
    s = p.seat
    base = f"seat-{s.row}-{s.num}"
    sid, n = base, 2
    while sid in used:
        sid, n = f"{base}-{n}", n + 1
    used.add(sid)
    grp = style_of(s.kind, blocked)[0]
    return Begin(
        sid,
        {
            "class": "seat",
            "data-row": s.row,
            "data-number": str(s.num),
            "data-kind": s.kind,
            "data-blocked": "true" if blocked else "false",
        },
        f"{s.row}-{s.num}  {label_of(grp, lang)}",
    )


def text_width(s: str, size: float) -> float:
    """フォント非依存の概算幅(全角=1em, 半角=0.56em)。"""
    return sum(size if unicodedata.east_asian_width(ch) in "WFA" else size * 0.56 for ch in s)


def wheelchair_icon(cx, cy, a, color="#FFFFFF"):
    """一辺 a の正方形に収まる車いすピクトグラム。"""
    def P(u, v):
        return cx + (u - 0.5) * a, cy + (v - 0.5) * a

    lw = max(0.9, a * 0.09)
    hx, hy = P(0.42, 0.18)
    out = [Circle(hx, hy, a * 0.09, fill=color)]
    for (u1, v1), (u2, v2) in [
        ((0.42, 0.30), (0.42, 0.58)),
        ((0.42, 0.42), (0.64, 0.42)),
        ((0.42, 0.58), (0.68, 0.58)),
        ((0.68, 0.58), (0.76, 0.84)),
    ]:
        x1, y1 = P(u1, v1)
        x2, y2 = P(u2, v2)
        out.append(Line(x1, y1, x2, y2, color, lw))
    wx, wy = P(0.40, 0.70)
    out.append(Circle(wx, wy, a * 0.20, stroke=color, sw=lw))
    return out


def _lines(placed):
    """(行記号, 左端x, 右端x, 中心y) のリスト。

    同じ行記号でも縦に離れていれば別の行として扱う。車いす席(HC)は行記号を持たないので、
    縦位置が最も近い行に所属させて左右端の計算にだけ含める(ラベルを車いす席の外側に出すため)。
    """
    by_row = defaultdict(list)
    hcs = []
    for p in placed:
        (hcs if p.seat.row == "HC" else by_row[p.seat.row]).append(p)
    groups = []  # [row, [seats]]
    for row, ps in by_row.items():
        ps.sort(key=lambda p: p.y + p.h / 2)
        cur = [ps[0]]
        for p in ps[1:]:
            if (p.y + p.h / 2) - (cur[-1].y + cur[-1].h / 2) > max(5.0, p.h * 0.3):
                groups.append([row, cur])
                cur = []
            cur.append(p)
        groups.append([row, cur])

    def cy(ps):
        return sum(p.y + p.h / 2 for p in ps) / len(ps)

    extra = defaultdict(list)
    for h in hcs:
        best = min(groups, key=lambda g: abs(cy(g[1]) - (h.y + h.h / 2)), default=None)
        if best is not None and abs(cy(best[1]) - (h.y + h.h / 2)) <= h.h:
            extra[id(best)].append(h)
    out = []
    xs0 = min(p.x for p in placed) if placed else 0.0
    xs1 = max(p.x + p.w for p in placed) if placed else 0.0
    cx = (xs0 + xs1) / 2
    for g in groups:
        row, ps = g
        allp = sorted(ps + extra[id(g)], key=lambda p: p.x)
        # 通路(座席幅の1.5倍超の空き)でブロックに分け、図全体の中心に最も近いブロックの
        # 両脇に行記号を付ける (公式の背景画像と同じく、中央ブロックの左右に表示する)
        wmed = min(p.w for p in allp)
        segs, cur = [], [allp[0]]
        for p in allp[1:]:
            prev = cur[-1]
            kind_change = p.seat.kind != prev.seat.kind and "wheelchair" not in (p.seat.kind, prev.seat.kind)
            if p.x - (prev.x + prev.w) > wmed * 1.5 or kind_change:
                segs.append(cur)
                cur = []
            cur.append(p)
        segs.append(cur)

        def dist(sg):
            x0, x1 = sg[0].x, sg[-1].x + sg[-1].w
            return 0.0 if x0 <= cx <= x1 else min(abs(cx - x0), abs(cx - x1))

        seg = min(segs, key=lambda sg: (dist(sg), -sum(1 for p in sg if p.seat.row != "HC")))
        main = [p for p in seg if p.seat.row != "HC"] or seg
        out.append((row, min(p.x for p in seg), max(p.x + p.w for p in seg), cy(main), dist(seg)))
    # 同じ行記号が近い高さに複数ある場合(特別席ブロックと翼など)は、中心に近い方だけ残す
    keep = []
    for cand in sorted(out, key=lambda t: t[4]):
        if not any(k[0] == cand[0] and abs(k[3] - cand[3]) < 14 for k in keep):
            keep.append(cand)
    return [(r, mn, mx, y) for r, mn, mx, y, _d in keep]


def build_scene(box: Box, title: str, subtitle: str, opts: Options, footer: str = "") -> Scene:
    lang = opts.lang
    placed = [p for p in box.seats if not (opts.blocked_mode == "hide" and p.seat.blocked)]

    # ---- 凡例(集計) -----------------------------------------------------
    counts = Counter()
    for p in box.seats:
        blocked = p.seat.blocked and opts.blocked_mode == "mark"
        group = style_of(p.seat.kind, blocked)[0]
        counts[group] += 1
    order = ["normal", "prm", "wheelchair", "blocked"]
    groups = sorted(counts, key=lambda g: (order.index(g) if g in order else 50, g))

    legend_items = []
    for g in groups:
        kind = {"mx4d": "mx4d_center"}.get(g, g)
        _grp, fill, stroke, _t = style_of(kind, blocked=(g == "blocked"))
        txt = f"{label_of(g, lang)} {counts[g]}"
        legend_items.append((g, fill, stroke, txt, 12 + 5 + text_width(txt, 8) + 14))

    seat_area_w = box.w + LABEL_W * 2
    header_w = max(text_width(title, 15), text_width(subtitle, 8.5)) if title or subtitle else 0
    canvas_inner = max(seat_area_w, header_w, 260)
    # 凡例の折り返し
    rows, cur, cur_w = [], [], 0.0
    for it in legend_items:
        if cur and cur_w + it[4] > canvas_inner:
            rows.append(cur)
            cur, cur_w = [], 0.0
        cur.append(it)
        cur_w += it[4]
    if cur:
        rows.append(cur)

    W = canvas_inner + MARGIN * 2
    y = MARGIN
    items = []
    obj = opts.svg_objects

    def L_begin(name, label):
        if obj:
            items.append(layer_begin(name, label))

    def L_end():
        if obj:
            items.append(End())

    # ---- ヘッダ ----------------------------------------------------------
    L_begin("header", "タイトル")
    if title:
        items.append(Text(W / 2, y + 8, title, 15, "middle", "#1E2A36", True))
        y += 20
    if subtitle:
        items.append(Text(W / 2, y + 5, subtitle, 8.5, "middle", "#5B6670"))
        y += 14
    y += 6
    L_end()

    # ---- スクリーン ------------------------------------------------------
    L_begin("screen", "スクリーン")
    ox = (W - box.w) / 2
    sw_ = max(box.w * 0.9, 120)
    sx = (W - sw_) / 2
    items.append(Rect(sx, y, sw_, 12, r=4, fill="#3A4652"))
    items.append(Text(W / 2, y + 6.3, "SCREEN" if lang != "ja" else "SCREEN  スクリーン", 7.5, "middle", "#FFFFFF", True))
    y += 12 + 12
    L_end()

    # ---- 座席 ------------------------------------------------------------
    oy = y

    def draw_seat(p):
        s = p.seat
        blocked = s.blocked and opts.blocked_mode == "mark"
        _g, fill, stroke, tcol = style_of(s.kind, blocked)
        gx, gy = 1.0, 1.0
        rx, ry = ox + p.x + gx, oy + p.y + gy
        rw, rh = p.w - gx * 2, p.h - gy * 2
        items.append(Rect(rx, ry, rw, rh, r=min(rw, rh) * 0.22, fill=fill, stroke=stroke, sw=0.7))
        cx, cy = rx + rw / 2, ry + rh / 2
        if s.kind == "wheelchair" and not blocked:
            items.extend(wheelchair_icon(cx, cy, min(rw, rh) * 0.92))
        elif blocked:
            d = min(rw, rh) * 0.28
            items.append(Line(cx - d, cy - d, cx + d, cy + d, stroke, 0.9))
            items.append(Line(cx - d, cy + d, cx + d, cy - d, stroke, 0.9))
        elif opts.show_numbers:
            size = min(rw * 0.62, rh * 0.5, 9.5)
            items.append(Text(cx, cy + 0.2, str(s.num), size, "middle", tcol))

    L_begin("seats", "座席")
    if obj:
        used = set()
        for row, ps in group_by_row(placed):
            items.append(Begin(f"row-{row}", {"data-row": row}, f"{row}列"))
            for p in ps:
                items.append(seat_marker(p, used, p.seat.blocked and opts.blocked_mode == "mark", lang))
                draw_seat(p)
                items.append(End())
            items.append(End())
    else:
        for p in placed:
            draw_seat(p)
    L_end()

    # 行ラベル(各行の左右端に添える)
    L_begin("row-labels", "行記号")
    for row, minx, maxx, cyl in _lines(placed):
        items.append(Text(ox + minx - 3, oy + cyl, row, 8, "end", "#6B7785", True))
        items.append(Text(ox + maxx + 3, oy + cyl, row, 8, "start", "#6B7785", True))
    L_end()

    y = oy + box.h + 14
    # ---- 凡例 ------------------------------------------------------------
    L_begin("legend", "凡例")
    for rowitems in rows:
        total = sum(i[4] for i in rowitems) - 14
        x = (W - total) / 2
        for _g, fill, stroke, txt, wd in rowitems:
            items.append(Rect(x, y, 12, 12, r=3, fill=fill, stroke=stroke, sw=0.7))
            items.append(Text(x + 17, y + 6.3, txt, 8, "start", "#33404D"))
            x += wd
        y += 17
    if footer:
        y += 2
        items.append(Text(W / 2, y + 4, footer, 6.5, "middle", "#8A949E"))
        y += 10
    L_end()
    H = y + MARGIN - 6
    return Scene(W, H, items, inline_images=obj)
