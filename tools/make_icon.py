"""アイコン(SVG/PNG/ICO)を生成する。どの映画館チェーン版でも使える共通デザイン。

デザイン: 暗いグレーの角丸四角に、曲線のスクリーン(白)と、通路で分かれた座席の並び(白)、
特別席を表す1席だけアクセント色。ブランド固有の要素は使わない。

使い方:
    python tools/make_icon.py                       # 既定(ゴールド)を assets/icon/ に出力
    python tools/make_icon.py --accent "#2EC4B6" --out assets/icon-teal   # 版ごとに色違い
"""
import argparse
import base64
import io
import os

from PIL import Image, ImageDraw

S = 1024
BG = (38, 43, 49)
SEAT = (245, 247, 250)
SEAT_EDGE = (176, 183, 192)

# 座席の並び: (行の上端y, 左ブロックの席数, 右ブロックの席数)
SEAT_W, SEAT_H, GAP, AISLE, R = 68, 80, 16, 56, 16
ROWS = [(470, 2, 2), (576, 3, 3), (682, 4, 4), (788, 5, 5)]
ACCENT_SEAT = (2, 1, 1)  # (行index, 0=左/1=右ブロック, ブロック内index)
SCREEN = ((200, 262), (512, 96), (824, 262))  # 2次ベジェ曲線(始点, 制御点, 終点)
SCREEN_W = 36
RADIUS = 224


# 小サイズ(16〜48px)用: 席を少なく大きくして潰れないようにした簡略版
SMALL = dict(seat=(104, 120, 24, 64), rows=[(520, 1, 1), (672, 2, 2), (824 - 0, 3, 3)], accent=(1, 1, 0), screen_w=52)


def seat_rects(small=False):
    """[(x, y, w, h, is_accent)]"""
    out = []
    seat_w, seat_h, gap, aisle = (SMALL["seat"] if small else (SEAT_W, SEAT_H, GAP, AISLE))
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
    (x0, y0), (x1, y1), (x2, y2) = SCREEN
    return (
        (1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t ** 2 * x2,
        (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t ** 2 * y2,
    )


def _shade(rgb, k):
    return tuple(max(0, min(255, int(c * k))) for c in rgb)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def draw_png(accent, size=S, ss=2, small=False):
    k = size * ss / S
    im = Image.new("RGBA", (int(S * k), int(S * k)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, S * k - 1, S * k - 1], radius=RADIUS * k, fill=BG + (255,))
    # スクリーン(曲線の太線): 曲線上に細かく円を並べて、端も含めてなめらかにする
    sw = SMALL["screen_w"] if small else SCREEN_W
    r = sw / 2 * k
    for i in range(0, 801):
        x, y = _bez(i / 800)
        d.ellipse([x * k - r, y * k - r, x * k + r, y * k + r], fill=(255, 255, 255, 255))
    for x, y, w, h, acc in seat_rects(small):
        fill = hex_to_rgb(accent) if acc else SEAT
        edge = _shade(hex_to_rgb(accent), 0.7) if acc else SEAT_EDGE
        d.rounded_rectangle([x * k, y * k, (x + w) * k, (y + h) * k], radius=R * k, fill=fill + (255,), outline=edge + (255,), width=max(1, int((6 if small else 4) * k)))
    return im.resize((size, size), Image.LANCZOS) if ss != 1 else im


def svg_text(accent):
    (x0, y0), (cx, cy), (x2, y2) = SCREEN
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="512" height="512">',
        f'<rect width="{S}" height="{S}" rx="{RADIUS}" fill="rgb{BG}"/>',
        f'<path d="M{x0} {y0} Q{cx} {cy} {x2} {y2}" fill="none" stroke="#fff" stroke-width="{SCREEN_W}" stroke-linecap="round"/>',
    ]
    acc = hex_to_rgb(accent)
    for x, y, w, h, a in seat_rects():
        fill = f"rgb{acc}" if a else f"rgb{SEAT}"
        edge = f"rgb{_shade(acc, 0.7)}" if a else f"rgb{SEAT_EDGE}"
        out.append(f'<rect x="{x:g}" y="{y:g}" width="{w}" height="{h}" rx="{R}" fill="{fill}" stroke="{edge}" stroke-width="4"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accent", default="#F5C542", help="特別席の色 (既定: ゴールド)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "assets", "icon"))
    ap.add_argument("--embed", action="store_true", help="GUIのウィンドウ用に toho_seatmap/icon_data.py も更新する")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    big = draw_png(a.accent, 1024)
    big.save(os.path.join(a.out, "icon-1024.png"))
    draw_png(a.accent, 256).save(os.path.join(a.out, "icon-256.png"))
    # ICO: 大きいサイズは通常版、小さいサイズ(16〜48)は簡略版を使う
    frames = [draw_png(a.accent, sz, small=(sz <= 48)) for sz in (16, 24, 32, 48, 64, 128, 256)]
    frames[-1].save(
        os.path.join(a.out, "icon.ico"),
        sizes=[(sz, sz) for sz in (16, 24, 32, 48, 64, 128, 256)],
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
