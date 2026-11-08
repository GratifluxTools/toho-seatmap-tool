"""Scene -> PNG (Pillow)。2倍で描いて縮小するアンチエイリアス付き。"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .fonts import find_cjk_font, has_cjk_glyphs
from .scene import Circle, Img, Line, Rect, Scene, Text



class FontSet:
    def __init__(self, path: str | None):
        self.path = path
        self._cache = {}

    def get(self, size: float):
        px = max(1, int(round(size)))
        if px not in self._cache:
            try:
                if self.path:
                    self._cache[px] = ImageFont.truetype(self.path, px)
                else:
                    self._cache[px] = ImageFont.load_default(size=px)
            except Exception:
                self._cache[px] = ImageFont.load_default(size=px)
        return self._cache[px]

    @property
    def has_cjk(self) -> bool:
        return bool(self.path) and has_cjk_glyphs(self.get(20))


def make_fontset(user_font: str | None = None) -> FontSet:
    return FontSet(find_cjk_font(user_font))


def render_png(scene: Scene, scale: float = 2.0, fonts: FontSet | None = None) -> Image.Image:
    fonts = fonts or make_fontset()
    SS = max(1, scene.ss)
    k = scale * SS
    cache = {}
    W, H = int(round(scene.w * k)), int(round(scene.h * k))
    img = Image.new("RGB", (W, H), scene.bg)
    d = ImageDraw.Draw(img)
    for it in scene.items:
        if isinstance(it, Rect):
            box = [it.x * k, it.y * k, (it.x + it.w) * k - 1, (it.y + it.h) * k - 1]
            kw = dict(fill=it.fill)
            if it.stroke:
                kw.update(outline=it.stroke, width=max(1, int(round(it.sw * k))))
            if it.r:
                d.rounded_rectangle(box, radius=it.r * k, **kw)
            else:
                d.rectangle(box, **kw)
        elif isinstance(it, Line):
            d.line([it.x1 * k, it.y1 * k, it.x2 * k, it.y2 * k], fill=it.color, width=max(1, int(round(it.w * k))))
        elif isinstance(it, Circle):
            box = [(it.cx - it.r) * k, (it.cy - it.r) * k, (it.cx + it.r) * k, (it.cy + it.r) * k]
            kw = dict(fill=it.fill)
            if it.stroke:
                kw.update(outline=it.stroke, width=max(1, int(round(it.sw * k))))
            d.ellipse(box, **kw)
        elif isinstance(it, Img):
            src = scene.images.get(it.key)
            if src is None:
                continue
            size = (max(1, int(round(it.w * k))), max(1, int(round(it.h * k))))
            ck = (it.key, size)
            if ck not in cache:
                cache[ck] = src if src.size == size else src.resize(size, Image.LANCZOS)
            im = cache[ck]
            img.paste(im, (int(round(it.x * k)), int(round(it.y * k))), im)
        elif isinstance(it, Text):
            anchor = {"start": "lm", "middle": "mm", "end": "rm"}[it.anchor]
            d.text(
                (it.x * k, it.y * k),
                it.s,
                fill=it.color,
                font=fonts.get(it.size * k),
                anchor=anchor,
                stroke_width=max(0, int(round(k * 0.18))) if it.bold else 0,
                stroke_fill=it.color,
            )
    target = (int(round(scene.w * scale)), int(round(scene.h * scale)))
    return img if img.size == target else img.resize(target, Image.LANCZOS)
