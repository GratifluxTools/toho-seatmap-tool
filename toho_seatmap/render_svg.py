"""Scene -> SVG 文字列。"""
from __future__ import annotations

import base64
import io
from xml.sax.saxutils import escape

from .scene import Circle, Img, Line, Rect, Scene, Text

FONT_STACK = "'Noto Sans JP','Yu Gothic','Meiryo','Hiragino Sans','Noto Sans CJK JP',sans-serif"


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def render_svg(scene: Scene, scale: float = 2.0) -> str:
    w, h = scene.w * scale, scene.h * scale
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(w)}" height="{_f(h)}" '
        f'viewBox="0 0 {_f(scene.w)} {_f(scene.h)}" font-family="{FONT_STACK}">',
        f'<rect width="100%" height="100%" fill="{scene.bg}"/>',
    ]
    ids = {}
    if scene.images:
        out.append("<defs>")
        for n, (key, im) in enumerate(scene.images.items()):
            buf = io.BytesIO()
            im.save(buf, "PNG")
            ids[key] = (f"i{n}", im.width, im.height)
            out.append(
                f'<image id="i{n}" width="{im.width}" height="{im.height}" '
                f'href="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"/>'
            )
        out.append("</defs>")
    for it in scene.items:
        if isinstance(it, Img):
            if it.key in ids:
                iid, nw, nh = ids[it.key]
                out.append(
                    f'<use href="#{iid}" transform="translate({_f(it.x)} {_f(it.y)}) '
                    f'scale({_f(it.w / nw)} {_f(it.h / nh)})"/>'
                )
        elif isinstance(it, Rect):
            a = f'<rect x="{_f(it.x)}" y="{_f(it.y)}" width="{_f(it.w)}" height="{_f(it.h)}"'
            if it.r:
                a += f' rx="{_f(it.r)}"'
            a += f' fill="{it.fill or "none"}"'
            if it.stroke:
                a += f' stroke="{it.stroke}" stroke-width="{_f(it.sw)}"'
            out.append(a + "/>")
        elif isinstance(it, Line):
            out.append(
                f'<line x1="{_f(it.x1)}" y1="{_f(it.y1)}" x2="{_f(it.x2)}" y2="{_f(it.y2)}" '
                f'stroke="{it.color}" stroke-width="{_f(it.w)}" stroke-linecap="round"/>'
            )
        elif isinstance(it, Circle):
            a = f'<circle cx="{_f(it.cx)}" cy="{_f(it.cy)}" r="{_f(it.r)}" fill="{it.fill or "none"}"'
            if it.stroke:
                a += f' stroke="{it.stroke}" stroke-width="{_f(it.sw)}"'
            out.append(a + "/>")
        elif isinstance(it, Text):
            out.append(
                f'<text x="{_f(it.x)}" y="{_f(it.y)}" font-size="{_f(it.size)}" '
                f'text-anchor="{it.anchor}" dominant-baseline="central" fill="{it.color}"'
                + (' font-weight="bold"' if it.bold else "")
                + f">{escape(it.s)}</text>"
            )
    out.append("</svg>")
    return "\n".join(out)
