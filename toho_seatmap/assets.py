"""同梱アセット(座席gif・画面ごとの背景gif/css)の読み込み。HARに記録されたものを優先する。"""
from __future__ import annotations

import io
import os
import sys
from functools import lru_cache

from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))


def _dirs():
    bd = getattr(sys, "_MEIPASS", None)
    if bd:
        yield os.path.join(bd, "toho_seatmap", "assets")
    yield os.path.join(_HERE, "assets")


def _read(*parts):
    for d in _dirs():
        p = os.path.join(d, *parts)
        if os.path.exists(p):
            with open(p, "rb") as f:
                return f.read()
    return None


def seat_gif(name: str, resources: dict | None = None):
    """seat_*.gif のバイト列。HARの記録 -> 同梱 の順。"""
    if resources:
        b = resources.get(f"/layout/0001/ppt/01/{name}")
        if b:
            return b
    return _read("seats", name)


def cache_dir() -> str:
    """オンライン取得した画面アセットの保存先。"""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "toho-seatmap", "screens")


def _fetch(gekijyo: str, screen: str, ext: str, timeout: float = 15.0):
    import urllib.request

    url = f"https://hlo.tohotheater.jp/layout/{gekijyo}/ppt/{screen}/screen.{ext}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 toho-seatmap"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if ext == "gif" and not data.startswith(b"GIF8"):
            return None
        if ext == "css" and b"screen-defimg" not in data:
            return None
        return data
    except Exception:
        return None


def screen_asset(gekijyo: str, screen: str, ext: str, resources: dict | None = None, fetch: bool = False):
    """画面ごとの screen.css / screen.gif。HAR -> ローカルキャッシュ -> 同梱 -> (fetch=Trueなら)オンライン取得。"""
    if resources:
        b = resources.get(f"/layout/{gekijyo}/ppt/{screen}/screen.{ext}")
        if b:
            return b
    name = f"{gekijyo}_{screen}.{ext}"
    cached = os.path.join(cache_dir(), name)
    if os.path.exists(cached):
        with open(cached, "rb") as f:
            return f.read()
    b = _read("screens", name)
    if b or not fetch:
        return b
    b = _fetch(gekijyo, screen, ext)
    if b:
        try:
            os.makedirs(cache_dir(), exist_ok=True)
            with open(cached, "wb") as f:
                f.write(b)
        except OSError:
            pass
    return b


def to_image(data: bytes):
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def clear_outside(img):
    """背景画像の外周から続く白/透過の領域(スクリーン形状の外側)を透明にする。

    台形・斜めの形のスクリーンでは、枠線の外側が白で塗られている。そのまま使うと
    灰色の背景に白い部分が出てしまうので、外周とつながる白だけを透明にして背景色を見せる。
    枠内の白い線・非常口・座席は、黒い枠線で外側と隔てられているので影響しない。
    枠線の外縁に沿う薄い白線(元画像で枠の外側に描かれた縁取り)は、外側の白と連続していても
    「線」として残したいので、色が白(235以上)・透過のものだけを消し、灰色がかった縁は消さない。
    """
    from PIL import ImageDraw

    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            on_edge = x in (0, w - 1) or y in (0, h - 1)
            # 画像の端1ピクセルにある明るい縁(薄灰色など)も外側として扱う
            if a < 10 or (r >= 235 and g >= 235 and b >= 235) or (on_edge and (r + g + b) / 3 >= 150):
                mp[x, y] = 255
    seeds = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
    seeds += [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    for sx, sy in seeds:
        if mp[sx, sy] == 255:
            ImageDraw.floodfill(mask, (sx, sy), 128)
    for y in range(h):
        for x in range(w):
            if mp[x, y] == 128:
                px[x, y] = (0, 0, 0, 0)
    return rgba
