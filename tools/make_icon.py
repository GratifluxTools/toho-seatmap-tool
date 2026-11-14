"""アイコン(SVG/PNG/ICO)を生成する。どの映画館チェーン版でも使える共通デザイン。

デザイン: 夜のシアターをイメージした濃紺の角丸タイル。上部に光るスクリーン(白い弧)、
その下に座席の並び。特別席を表す1席だけがアクセント色。
席数を絞り、小さいサイズでも「スクリーンと座席」が読み取れるようにしている。

使い方:
    python tools/make_icon.py                       # 既定(ゴールド)を assets/icon/ に出力
    python tools/make_icon.py --accent "#2EC4B6" --out assets/icon-teal   # 版ごとに色違い
    python tools/make_icon.py --embed               # GUIのウィンドウ用アイコンも更新
"""
import argparse
import base64
import io
import os

from PIL import Image, ImageDraw, ImageFilter

S = 1024
BG = (27, 32, 44)            # 濃紺のタイル
SEAT = (226, 231, 240)       # 座席(少しだけ暖かみのある白)
SCREEN = (255, 255, 255)     # スクリーン
GLOW = 26                    # スクリーンの光のぼかし量(1024px基準)
RADIUS = 224

# スクリーン: 2次ベジェ曲線(始点, 制御点, 終点)
ARC = ((230, 300), (512, 176), (794, 300))
ARC_W = 52

# 通常サイズ: (行の上端y, 左ブロックの席数, 右ブロックの席数)
SEAT_W, SEAT_H, GAP, AISLE, R = 150, 104, 28, 120, 42
ROWS = [(500, 2, 2), (640, 2, 2), (780, 2, 2)]
ACCENT_SEAT = (1, 1, 1)  # (行index, 0=左/1=右ブロック, ブロック内index)

# 小サイズ(16〜48px)用: 席を大きく少なくして潰れないようにした簡略版
SMALL = dict(
    seat=(150, 130, 30, 70),        # (w, h, gap, aisle)
    rows=[(560, 2, 2), (760, 2, 2)],
    accent=(1, 1, 0),
    arc_w=76,
)


def seat_rects(small=False):
    """[(x, y, w, h, is_accent)]"""
    out = []
    seat_w, seat_h, gap, aisle = SMALL["seat"] if small else (SEAT_W, SEAT_H, GAP, AISLE)
    rows = SMALL["rows"] if small else ROWS
    accent = SMALL["accent"] if small else ACCENT_SEAT
    for ri, (y, nl, nr) in enumerate(rows):
        block_l = nl * seat_w + (nl - 1) * gap
        block_r = nr * seat_w + (nr - 1) * gap
        total = block_l + aisle + block_r
        x0 = (S - total) / 2
        for bi, (n, bx) in enumerate(((nl, x0), (nr, x0 + block_l + aisle))):
            for i in range(n):
                out.append((bx + i * (seat_w + gap), y, seat_w, seat_h, (ri, bi, i) == accent))
    return out


def _bez(t):
    (x0, y0), (x1, y1), (x2, y2) = ARC
    return (
        (1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t ** 2 * x2,
        (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t ** 2 * y2,
    )


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _draw_arc(d, k, width, fill):
    r = width / 2 * k
    for i in range(0, 801):
        x, y = _bez(i / 800)
        d.ellipse([x * k - r, y * k - r, x * k + r, y * k + r], fill=fill)


def draw_png(accent, size=S, ss=2, small=False):
    k = size * ss / S
    W = int(S * k)
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, W - 1], radius=RADIUS * k, fill=BG + (255,))

    arc_w = SMALL["arc_w"] if small else ARC_W
    if not small:  # 大きいサイズだけ、スクリーンに淡い光を入れる
        glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        _draw_arc(ImageDraw.Draw(glow), k, arc_w * 2.2, SCREEN + (110,))
        glow = glow.filter(ImageFilter.GaussianBlur(GLOW * k))
        im = Image.alpha_composite(im, glow)
        d = ImageDraw.Draw(im)

    _draw_arc(d, k, arc_w, SCREEN + (255,))
    acc = hex_to_rgb(accent)
    for x, y, w, h, is_acc in seat_rects(small):
        fill = acc if is_acc else SEAT
        d.rounded_rectangle([x * k, y * k, (x + w) * k, (y + h) * k], radius=R * k, fill=fill + (255,))
    return im.resize((size, size), Image.LANCZOS) if ss != 1 else im


def svg_text(accent):
    (x0, y0), (cx, cy), (x2, y2) = ARC
    acc = hex_to_rgb(accent)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="512" height="512">',
        '<defs><filter id="glow" x="-20%" y="-50%" width="140%" height="200%">'
        f'<feGaussianBlur stdDeviation="{GLOW}"/></filter></defs>',
        f'<rect width="{S}" height="{S}" rx="{RADIUS}" fill="rgb{BG}"/>',
        f'<path d="M{x0} {y0} Q{cx} {cy} {x2} {y2}" fill="none" stroke="#fff" stroke-opacity="0.45" '
        f'stroke-width="{ARC_W * 2.2:g}" stroke-linecap="round" filter="url(#glow)"/>',
        f'<path d="M{x0} {y0} Q{cx} {cy} {x2} {y2}" fill="none" stroke="#fff" '
        f'stroke-width="{ARC_W}" stroke-linecap="round"/>',
    ]
    for x, y, w, h, a in seat_rects():
        fill = f"rgb{acc}" if a else f"rgb{SEAT}"
        out.append(f'<rect x="{x:g}" y="{y:g}" width="{w}" height="{h}" rx="{R}" fill="{fill}"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accent", default="#F5C542", help="特別席の色 (既定: ゴールド)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "assets", "icon"))
    ap.add_argument("--embed", action="store_true", help="GUIのウィンドウ用に toho_seatmap/icon_data.py も更新する")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    draw_png(a.accent, 1024).save(os.path.join(a.out, "icon-1024.png"))
    draw_png(a.accent, 256).save(os.path.join(a.out, "icon-256.png"))
    # ICO: 大きいサイズは通常版、小さいサイズ(16〜48)は簡略版を使う
    sizes = (16, 24, 32, 48, 64, 128, 256)
    frames = [draw_png(a.accent, sz, small=(sz <= 48)) for sz in sizes]
    frames[-1].save(
        os.path.join(a.out, "icon.ico"),
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[:-1],
    )
    with open(os.path.join(a.out, "icon.svg"), "w", encoding="utf-8") as f:
        f.write(svg_text(a.accent))
    if a.embed:
        buf = io.BytesIO()
        draw_png(a.accent, 128).save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        path = os.path.join(os.path.dirname(__file__), "..", "toho_seatmap", "icon_data.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write('"""GUIウィンドウ用アイコン(128px PNG, base64)。tools/make_icon.py --embed で自動生成。"""\n\nPNG_B64 = (\n')
            for i in range(0, len(b64), 100):
                f.write(f'    "{b64[i:i + 100]}"\n')
            f.write(")\n")
    print("icon written to", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
