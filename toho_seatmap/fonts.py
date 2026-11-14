"""日本語表示用フォントの探索 (Pillow用)。見つからなければ None。"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _bundle_dir():
    # PyInstaller(onefile)展開先 or 通常実行
    return getattr(sys, "_MEIPASS", None)


def _candidates():
    bd = _bundle_dir()
    for base in filter(None, [os.path.join(bd, "toho_seatmap", "fonts") if bd else None, os.path.join(_HERE, "fonts")]):
        for pat in ("*.ttf", "*.otf", "*.ttc"):
            yield from sorted(glob.glob(os.path.join(base, pat)))
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in ("YuGothM.ttc", "YuGothR.ttc", "meiryo.ttc", "msgothic.ttc", "YuGothic.ttf"):
        yield os.path.join(win, name)
    yield "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"
    yield "/System/Library/Fonts/Hiragino Sans GB.ttc"
    try:
        out = subprocess.run(
            ["fc-list", ":lang=ja", "file"], capture_output=True, text=True, timeout=5
        ).stdout
        files = [l.split(":")[0].strip() for l in out.splitlines() if l.strip()]
        # Regularを優先 (Bold/Black/Light等は後回し)
        files.sort(key=lambda f: (any(k in f for k in ("Bold", "Black", "Light", "Thin", "Medium")), "Serif" in f, f))
        yield from files
    except Exception:
        pass
    for pat in (
        "/usr/share/fonts/**/NotoSansCJK*Regular*.tt[cf]",
        "/usr/share/fonts/**/NotoSansCJK*Regular*.otf",
        "/usr/share/fonts/**/ipag*.ttf",
        "/usr/share/fonts/**/takao*.ttf",
        "/usr/share/fonts/**/vlgothic*.ttf",
    ):
        yield from sorted(glob.glob(pat, recursive=True))


def find_cjk_font(user_path: str | None = None):
    """使える日本語フォントのパスを返す。"""
    if user_path:
        return user_path if os.path.exists(user_path) else None
    for p in _candidates():
        if p and os.path.exists(p):
            return p
    return None


def has_cjk_glyphs(font) -> bool:
    try:
        return font.getmask("座").getbbox() is not None and font.getmask("席").getbbox() is not None
    except Exception:
        return False
