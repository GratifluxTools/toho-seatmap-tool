"""座席画像(seat_*.gif)の命名規則から席種・状態を判定する。

観測した命名規則 (docs/ANALYSIS.md 参照)::

    seat_1.gif            通常席・空席          seat_2.gif  購入済み   seat_0.gif  選択不可
    seat_3.gif            選択中(凡例のみ)
    seat_4.gif            車いす席 (id は HC-n)
    seat_<種別>_<状態>.gif  特別席 (prm / cnfo / lux / mx4d_* / premiere2 ...)

状態の数字は 0=選択不可 / 1=空席 / 2=購入済み。種別名に数字が含まれる
(premiere2) ため、末尾の ``_<数字>.gif`` だけを状態として扱う。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

IMG_RE = re.compile(r"^seat_(?:(?P<fam>.+)_)?(?P<state>\d)\.gif$")
ID_RE = re.compile(r"^(?P<row>[A-Za-z]+)-(?P<num>\d+)$")


@dataclass(frozen=True)
class Seat:
    seat_id: str
    row: str
    num: int
    kind: str  # normal / wheelchair / prm / cnfo / lux / mx4d_center ...
    blocked: bool  # seat_*_0.gif (選択不可)
    state: str  # 元画像の状態数字


def classify(attrs: dict):
    """<img> 属性から Seat を返す。座席でなければ None。"""
    sid = attrs.get("id", "")
    m = ID_RE.match(sid)
    if not m:
        return None
    src = attrs.get("src", "").split("?")[0].rsplit("/", 1)[-1]
    im = IMG_RE.match(src)
    fam = im.group("fam") if im else None
    state = im.group("state") if im else "1"
    row = m.group("row").upper()
    if row == "HC" or (fam is None and state == "4"):
        kind = "wheelchair"
    else:
        kind = fam or "normal"
    return Seat(
        seat_id=sid,
        row=row,
        num=int(m.group("num")),
        kind=kind,
        blocked=(state == "0"),
        state=state,
    )


def is_spacer(attrs: dict) -> bool:
    return "spacer" in attrs.get("src", "")
