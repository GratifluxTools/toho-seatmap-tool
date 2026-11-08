"""劇場コード(site_cd) -> 劇場名。組み込み + 利用者が登録した名前(設定ファイル)。"""
from __future__ import annotations

import json
import os

BUILTIN_JA = {
    "081": "TOHOシネマズ 日比谷",
    "032": "TOHOシネマズ なんば",
    "088": "TOHOシネマズ ららぽーと門真",
    "084": "TOHOシネマズ 池袋",
    "037": "TOHOシネマズ 梅田",
}
BUILTIN_EN = {
    "081": "TOHO Cinemas Hibiya",
    "032": "TOHO Cinemas Namba",
    "088": "TOHO Cinemas LaLaport Kadoma",
    "084": "TOHO Cinemas Ikebukuro",
    "037": "TOHO Cinemas Umeda",
}

_USER: dict | None = None


def config_path() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "toho-seatmap", "theaters.json")


def user_names() -> dict:
    """利用者が登録した {site_cd: 劇場名}。"""
    global _USER
    if _USER is None:
        try:
            with open(config_path(), encoding="utf-8") as f:
                data = json.load(f)
            _USER = {str(k): str(v) for k, v in data.items() if str(v).strip()}
        except (OSError, ValueError, AttributeError):
            _USER = {}
    return _USER


def save_user_name(site_cd: str, name: str) -> bool:
    """劇場名を設定ファイルに記憶する(空文字なら削除)。成功したら True。"""
    d = dict(user_names())
    if name.strip():
        d[str(site_cd)] = name.strip()
    else:
        d.pop(str(site_cd), None)
    try:
        os.makedirs(os.path.dirname(config_path()), exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        return False
    global _USER
    _USER = d
    return True


def is_known(site_cd: str) -> bool:
    return site_cd in BUILTIN_JA or site_cd in user_names()


def name_for(site_cd: str, lang: str = "ja", override: str | None = None, schedule_name: str | None = None) -> str:
    """優先順位: 手動指定 > 利用者登録 > 組み込み > スケジュールHAR由来 > 「TOHOシネマズ (site コード)」。"""
    if override and override.strip():
        return override.strip()
    if site_cd in user_names():
        return user_names()[site_cd]
    table = BUILTIN_JA if lang == "ja" else BUILTIN_EN
    if site_cd in table:
        return table[site_cd]
    if lang == "ja" and schedule_name and schedule_name.strip():
        return schedule_name.strip()
    return f"TOHOシネマズ (site {site_cd})" if lang == "ja" else f"TOHO Cinemas (site {site_cd})"
