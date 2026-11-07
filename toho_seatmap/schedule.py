"""スケジュールAPI(TNPI3050J05)のレスポンスから、スクリーン名・座席数を引く。

HARにスケジュールAPIの応答が含まれていれば、座席表のタイトルに
「本館スクリーン1」などの正式名を使える。無くても座席表の生成には影響しない。
"""
from __future__ import annotations

import unicodedata


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").strip()


class ScheduleIndex:
    def __init__(self):
        self.screens = {}  # (site_cd, screen_code) -> {"name","seats","icons","theater"}

    def add_response(self, resp: dict):
        try:
            for d in resp.get("data", []):
                site = str(d.get("vitCd", ""))
                for group in d.get("list", []):
                    for movie in group.get("list", []):
                        for show in movie.get("list", []):
                            sc = show.get("screen") or {}
                            code = str(sc.get("code", ""))
                            if not code:
                                continue
                            icons = [nfkc(sc.get(k, "")) for k in ("iconNm1", "iconNm2", "iconNm3")]
                            self.screens[(site, code)] = {
                                "name": nfkc(sc.get("name", "")),
                                "seats": sc.get("allSeatNum"),
                                "icons": [i for i in icons if i],
                                "theater": nfkc(group.get("name", "")),
                            }
        except (AttributeError, TypeError):
            pass

    def lookup(self, site_cd: str, screen_cd: str):
        return self.screens.get((str(site_cd), str(screen_cd).lstrip("0") or "0")) or self.screens.get(
            (str(site_cd), str(screen_cd))
        )
