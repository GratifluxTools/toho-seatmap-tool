"""公式サイトと同じ見た目のシーン: 背景gif(screen.gif) + 座席gif を screen.css どおりに重ねる。

背景gifが無い画面は、同じ配色(#616264)で SCREEN 表示と行記号を自動描画して代替する。
"""
from __future__ import annotations

from collections import Counter

from . import assets
from .cssmini import Elem, px
from .layout import Box, trim_box
from .scene import Img, Line, Options, Rect, Scene, Text, _lines, text_width
from .styles import label_of, style_of

BG_FALLBACK = (97, 98, 100)
WHITE = "#FFFFFF"
SOFT = "#D9DADC"


def seat_gif_name(seat, blocked_mode: str):
    """座席に使う gif ファイル名 (状態は常に空席=1。選択不可は _0)。"""
    if seat.kind == "wheelchair":
        return "seat_4.gif"
    fam = None if seat.kind == "normal" else seat.kind
    st = "0" if (seat.blocked and blocked_mode == "mark") else "1"
    return f"seat_{st}.gif" if fam is None else f"seat_{fam}_{st}.gif"


def _synth_seat(name: str):
    """どの画像も得られない時の最終フォールバック: 簡易な座席画像を描く(座席が消えないように)。"""
    from PIL import Image, ImageDraw

    blocked = name.endswith("_0.gif")
    wheel = name == "seat_4.gif"
    fill = (0, 0, 0, 255) if blocked else (255, 255, 255, 255)
    im = Image.new("RGBA", (15, 22), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 14, 21], radius=2, fill=fill, outline=(60, 60, 60, 255))
    if wheel:
        d.ellipse([4, 12, 11, 19], outline=(60, 60, 60, 255))
        d.ellipse([6, 3, 8, 5], fill=(60, 60, 60, 255))
    return im


class _Loader:
    def __init__(self, resources, fetch=False):
        self.resources = resources or {}
        self.fetch = fetch
        self.images = {}
        self.missing = set()

    def get(self, name: str):
        if name in self.images:
            return name
        img = assets.seat_image(name, self.resources, self.fetch)
        if img is None:
            # 席種のgifが無い(未知の席種など): _0 は汎用の選択不可、それ以外は通常席で代替
            alt = "seat_0.gif" if name.endswith("_0.gif") else "seat_1.gif"
            self.missing.add(name)
            if name != alt:
                return self.get(alt)
            img = _synth_seat(name)  # 通常席の画像すら無い場合の最終手段
        self.images[name] = img
        return name


def dominant_bg(img) -> tuple:
    """背景画像で最も多い灰色(白い座席・黒枠・透過/白の外側を除く)を背景色とする。

    スクリーンが台形・曲線の画面は四隅が透過/白なので、1点のサンプリングでは外れてしまう。
    """
    try:
        colors = img.convert("RGBA").getcolors(maxcolors=1 << 20) or []
    except Exception:
        return BG_FALLBACK
    best, best_n = None, 0
    for n, (r, g, b, a) in colors:
        lum = (r + g + b) / 3
        if a < 200 or not (50 <= lum <= 170) or max(r, g, b) - min(r, g, b) > 30:
            continue
        if n > best_n:
            best, best_n = (r, g, b), n
    return best or BG_FALLBACK


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(rgb[:3])


def build_official(sm, opts: Options) -> Scene:
    lang = opts.lang
    box: Box = sm.box
    loader = _Loader(sm.resources, getattr(sm, "fetch_missing", False))
    placed = [p for p in box.seats if not (opts.blocked_mode == "hide" and p.seat.blocked)]
    bg = sm.bg  # PIL RGBA | None
    items = []
    sheet = sm.sheet

    # ---- 本体(背景+座席)を (0,0) 起点で組み立てる --------------------------------
    if bg is not None and sheet is not None:
        defimg = Elem("div", "screen-defimg", ("screen-map",))
        frame = sheet.style_for([defimg, Elem("div", "screen-list-frame")])
        ox = (px(frame.get("padding-left")) or 0.0) + (px(frame.get("margin-left")) or 0.0)
        oy = (px(frame.get("padding-top")) or 0.0) + (px(frame.get("margin-top")) or 0.0)
        bw, bh = bg.size
        W, H = max(float(bw), ox + box.w), max(float(bh), oy + box.h)
        color = _hex(dominant_bg(bg))
        items.append(Rect(0, 0, W, H, fill=color))
        loader.images["__bg__"] = bg
        items.append(Img(0, 0, bw, bh, "__bg__"))
        seat_box, labels = box, []
    else:
        tb = trim_box(box)
        M, LAB = 16.0, 16.0
        W, H = tb.w + (M + LAB) * 2, tb.h + 62 + M + 6
        color = _hex(BG_FALLBACK)
        ox, oy = M + LAB, 50.0
        items.append(Rect(0, 0, W, H, fill=color))
        items.append(Rect(M, 10, W - 2 * M, 3.5, fill=WHITE))
        no = sm.screen_no or sm.screen_cd.lstrip("0")
        items.append(Text(W / 2, 28, f"SCREEN {no}", 13, "middle", WHITE, True))
        seat_box = tb
        labels = [(r, mn, mx, cy) for r, mn, mx, cy in _lines(tb.seats if opts.blocked_mode != "hide" else [p for p in tb.seats if not p.seat.blocked])]

    group_first, counts = {}, Counter()
    for p in placed:
        s = p.seat
        name = loader.get(seat_gif_name(s, opts.blocked_mode))
        grp = style_of(s.kind, s.blocked and opts.blocked_mode == "mark")[0]
        counts[grp] += 1
        group_first.setdefault(grp, name)
        if name:
            items.append(Img(ox + p.x, oy + p.y, p.w, p.h, name))
    # 席数は非表示(hide)でも全席ぶんを凡例に出さない: 描いた席のみ集計
    for row, mn, mx, cy in labels:
        items.append(Text(ox + mn - 4, oy + cy, row, 9, "end", WHITE, True))
        items.append(Text(ox + mx + 4, oy + cy, row, 9, "start", WHITE, True))

    # ---- タイトル/凡例の帯 ------------------------------------------------------
    head_h = 0.0
    head_items = []
    if opts.show_title:
        # スクリーン番号は背景画像(または自動描画)の SCREEN 表示にあるので、最上部は劇場名のみ
        head_items.append(Text(W / 2, 17, sm.theater_name(lang), 15, "middle", WHITE, True))
        head_items.append(Text(W / 2, 34, sm.subtitle(lang), 8.5, "middle", SOFT))
        head_h = 46.0
    order = ["normal", "prm", "wheelchair", "blocked"]
    groups = sorted(counts, key=lambda g: (order.index(g) if g in order else 50, g))
    leg_rows, leg_h = [], 0.0
    if opts.show_legend and groups:
        entries = []
        for g in groups:
            nm = group_first.get(g)
            im = loader.images.get(nm) if nm else None
            sw_w = im.width if im else 15
            txt = f"{label_of(g, lang)} {counts[g]}"
            entries.append((nm, sw_w, im.height if im else 22, txt, sw_w + 6 + text_width(txt, 8.5) + 16))
        cur, cw = [], 0.0
        for e in entries:
            if cur and cw + e[4] > W - 20:
                leg_rows.append(cur)
                cur, cw = [], 0.0
            cur.append(e)
            cw += e[4]
        if cur:
            leg_rows.append(cur)
        leg_h = 10 + 32.0 * len(leg_rows)

    total_h = head_h + H + leg_h
    out = [Rect(0, 0, W, total_h, fill=color)] + head_items
    shift = head_h
    for it in items:
        if isinstance(it, Rect):
            out.append(Rect(it.x, it.y + shift, it.w, it.h, it.r, it.fill, it.stroke, it.sw))
        elif isinstance(it, Img):
            out.append(Img(it.x, it.y + shift, it.w, it.h, it.key))
        elif isinstance(it, Text):
            out.append(Text(it.x, it.y + shift, it.s, it.size, it.anchor, it.color, it.bold))
    y = head_h + H + 6
    for row in leg_rows:
        total = sum(e[4] for e in row) - 16
        x = (W - total) / 2
        for nm, sw_w, sh_h, txt, wd in row:
            if nm:
                out.append(Img(x, y + (22 - sh_h) / 2 + 3, sw_w, sh_h, nm))
            out.append(Text(x + sw_w + 6, y + 14, txt, 8.5, "start", WHITE))
            x += wd
        y += 32
    return Scene(W, total_h, out, bg=color, images=loader.images, ss=1)
