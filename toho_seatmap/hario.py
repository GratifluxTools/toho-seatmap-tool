"""HARファイルの読み込みと、座席ページ/スケジュールAPIレスポンスの抽出。"""
from __future__ import annotations

import base64
import codecs
import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Iterator

SEAT_URL_RE = re.compile(r"/net/ticket/(\d+)/TNPI2010J01\.do")
SCHEDULE_API_RE = re.compile(r"api2\.tohotheater\.jp/api/schedule/v\d+/schedule/(\d+)/TNPI3050J05")


@dataclass
class SeatPage:
    html: str
    params: dict
    url: str
    source: str  # 入力ファイル名(表示用)
    resources: dict = field(default_factory=dict)  # '/layout/...' -> bytes (同じHARに記録された画像/CSS)

    @property
    def site_cd(self) -> str:
        m = SEAT_URL_RE.search(self.url)
        return self.params.get("site_cd") or (m.group(1) if m else "")


def iter_har_blobs(paths) -> Iterator[tuple]:
    """.har / .zip(中の.har) / ディレクトリ(再帰)から (表示名, bytes) を列挙する。"""
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for fn in sorted(files):
                    yield from iter_har_blobs([os.path.join(root, fn)])
        elif p.lower().endswith(".zip"):
            with zipfile.ZipFile(p) as zf:
                for info in sorted(zf.infolist(), key=lambda i: i.filename):
                    if info.is_dir() or not info.filename.lower().endswith(".har"):
                        continue
                    base = os.path.basename(info.filename)
                    if base.startswith("._"):  # macOSのメタデータ
                        continue
                    yield base, zf.read(info)
        elif p.lower().endswith(".har"):
            with open(p, "rb") as f:
                yield os.path.basename(p), f.read()


def parse_har(data: bytes) -> dict:
    return json.loads(data.decode("utf-8-sig"))


def _charset_of(mime: str) -> str:
    m = re.search(r"charset=([\w\-]+)", mime or "", re.I)
    name = (m.group(1) if m else "cp932").strip()
    try:
        codecs.lookup(name)
        return name
    except LookupError:
        return "cp932"  # Windows-31J など


def entry_text(entry: dict) -> str:
    content = entry.get("response", {}).get("content", {}) or {}
    text = content.get("text") or ""
    if content.get("encoding") == "base64" and text:
        raw = base64.b64decode(text)
        return raw.decode(_charset_of(content.get("mimeType", "")), errors="replace")
    return text


def _params(req: dict) -> dict:
    out = {q["name"]: q.get("value", "") for q in req.get("queryString", []) or []}
    post = req.get("postData") or {}
    for p in post.get("params", []) or []:
        out[p["name"]] = p.get("value", "")
    if not post.get("params") and post.get("text") and "=" in post["text"]:
        from urllib.parse import parse_qsl

        out.update(dict(parse_qsl(post["text"], keep_blank_values=True)))
    return out


LAYOUT_RE = re.compile(r"hlo\.tohotheater\.jp(/layout/[^?#]+\.(?:css|gif))$")


def find_layout_resources(har: dict) -> dict:
    """座席ページが参照した screen.css / screen.gif / seat_*.gif を取り出す。"""
    out = {}
    for e in har.get("log", {}).get("entries", []):
        m = LAYOUT_RE.search(e.get("request", {}).get("url", "").split("?")[0])
        content = e.get("response", {}).get("content", {}) or {}
        if not m or e.get("response", {}).get("status") != 200 or not content.get("text"):
            continue
        if m.group(1).endswith(".css"):
            out[m.group(1)] = content["text"].encode("utf-8")
        elif content.get("encoding") == "base64":
            out[m.group(1)] = base64.b64decode(content["text"])
    return out


def find_seat_pages(har: dict, source: str = "") -> list:
    pages = []
    resources = None
    for e in har.get("log", {}).get("entries", []):
        req = e.get("request", {})
        url = req.get("url", "")
        if not SEAT_URL_RE.search(url) or "hlo.tohotheater.jp" not in url:
            continue
        html = entry_text(e)
        if "screen-table" not in html:
            continue
        if resources is None:
            resources = find_layout_resources(har)
        pages.append(SeatPage(html=html, params=_params(req), url=url, source=source, resources=resources))
    return pages


def find_schedule_responses(har: dict) -> list:
    """スケジュールAPI(v2/TNPI3050J05)のJSONレスポンスを返す。"""
    out = []
    for e in har.get("log", {}).get("entries", []):
        url = e.get("request", {}).get("url", "")
        if not SCHEDULE_API_RE.search(url):
            continue
        try:
            out.append(json.loads(entry_text(e)))
        except (ValueError, TypeError):
            continue
    return out
