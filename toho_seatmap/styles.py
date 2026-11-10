"""席種ごとの見た目(plainスタイル用)と凡例名。

凡例名は seat_prm=プレミア ボックス シート / seat_lux=プレミア ラグジュアリー シート /
seat_cnfo=ワイド コンフォート シート / seat_premiere2=プレミア シート (利用者提供の情報)。
"""
from __future__ import annotations

# kind -> (凡例グループキー, 塗り, 枠線, 文字色)
KIND_STYLE = {
    "normal": ("normal", "#FFFFFF", "#6B7785", "#33404D"),
    "wheelchair": ("wheelchair", "#2F6FDE", "#1B4DA6", "#FFFFFF"),
    "prm": ("prm", "#F5C542", "#A97C00", "#4A3600"),
    "lux": ("lux", "#E58FB8", "#A93F77", "#4A1230"),
    "cnfo": ("cnfo", "#6FCF97", "#2E8B57", "#0F3B22"),
    "premiere": ("premiere", "#F2994A", "#B8651B", "#4A2300"),
    "premiere2": ("premiere", "#F2994A", "#B8651B", "#4A2300"),  # premiere と同じ凡例にまとめる
    "mx4d_left": ("mx4d", "#9DB8F5", "#4968B8", "#14264F"),
    "mx4d_center": ("mx4d", "#9DB8F5", "#4968B8", "#14264F"),
    "mx4d_right": ("mx4d", "#9DB8F5", "#4968B8", "#14264F"),
}
BLOCKED_STYLE = ("blocked", "#E3E6EA", "#9AA3AE", "#7B8591")
_FALLBACK_PALETTE = [
    ("#C7A6E8", "#7B4FB0", "#2A1745"),
    ("#8ADBD3", "#2B8C84", "#0D3A36"),
    ("#E8D28A", "#9C842B", "#3D3410"),
]

KIND_LABELS_JA = {
    "normal": "一般席",
    "wheelchair": "車いす席",
    "prm": "プレミア ボックス シート",
    "lux": "プレミア ラグジュアリー シート",
    "cnfo": "ワイド コンフォート シート",
    "premiere": "プレミア シート",
    "premiere2": "プレミア シート",
    "mx4d": "MX4Dシート",
    "blocked": "選択不可席",
}
KIND_LABELS_EN = {
    "normal": "Standard",
    "wheelchair": "Wheelchair",
    "prm": "Premier Box Seat",
    "lux": "Premier Luxury Seat",
    "cnfo": "Wide Comfort Seat",
    "premiere": "Premier Seat",
    "premiere2": "Premier Seat",
    "mx4d": "MX4D seat",
    "blocked": "Not selectable",
}


def style_of(kind: str, blocked: bool = False):
    """(group, fill, stroke, text) を返す。未知の席種は種別名で色を決める。"""
    if blocked:
        return BLOCKED_STYLE
    if kind in KIND_STYLE:
        return KIND_STYLE[kind]
    fill, stroke, text = _FALLBACK_PALETTE[sum(map(ord, kind)) % len(_FALLBACK_PALETTE)]
    return (kind, fill, stroke, text)


def label_of(group: str, lang: str = "ja") -> str:
    table = KIND_LABELS_JA if lang == "ja" else KIND_LABELS_EN
    if group in table:
        return table[group]
    return f"特別席({group})" if lang == "ja" else f"Special ({group})"
