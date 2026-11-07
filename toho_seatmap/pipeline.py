"""HAR群 -> 座席表(SeatMap) -> 画像ファイル、までの処理。CLI/GUI共通。"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field

import dataclasses

from . import assets, hario
from .cssmini import Sheet, parse_css
from .htmltable import extract_seat_region, parse_tables
from .layout import Box, layout_tables, trim_box
from .official import build_official
from .render_png import FontSet, make_fontset, render_png
from .render_svg import render_svg
from .scene import Options, build_scene
from .schedule import ScheduleIndex
from . import theaters
from .styles import style_of

CSS_LINK_RE = re.compile(r'href="/layout/(\d+)/ppt/(\d+)/screen\.css"')
FILENAME_RE = re.compile(r"toho_[a-z]+_(\d+)", re.I)
STATED_RE = re.compile(r"(\d+)&nbsp;<span[^>]*>[^<]*</span>&nbsp;\+&nbsp;(\d+)&nbsp;")
FACILITY_RE = re.compile(r'<div class="seat-info-icons icons">\s*<ul>(.*?)</ul>', re.S)


@dataclass
class SeatMap:
    stem: str
    site_cd: str
    screen_cd: str
    screen_no: str | None
    box: Box
    source: str
    params: dict
    stated: tuple | None  # (席数, 車いす席数) ページ表記
    facility: str
    schedule_info: dict | None
    warnings: list = field(default_factory=list)
    theater_override: str | None = None  # 手動指定の劇場名
    sheet: Sheet | None = None  # screen.css (あれば位置計算に使用)
    bg: object = None  # 背景 screen.gif (PIL.Image) / None
    resources: dict = field(default_factory=dict)  # HAR内の画像・CSS

    @property
    def counts(self) -> Counter:
        c = Counter()
        for p in self.box.seats:
            c[style_of(p.seat.kind, p.seat.blocked)[0]] += 1
        return c

    @property
    def n_seats(self) -> int:
        return sum(1 for p in self.box.seats if p.seat.kind != "wheelchair")

    @property
    def n_wheelchair(self) -> int:
        return sum(1 for p in self.box.seats if p.seat.kind == "wheelchair")

    def theater_name(self, lang: str = "ja") -> str:
        return theaters.name_for(self.site_cd, lang, self.theater_override)

    @property
    def theater_known(self) -> bool:
        return bool(self.theater_override and self.theater_override.strip()) or theaters.is_known(self.site_cd)

    def screen_label(self, lang: str = "ja") -> str:
        if lang == "ja":
            if self.schedule_info and self.schedule_info.get("name"):
                return self.schedule_info["name"]
            if self.screen_no:
                return f"スクリーン{self.screen_no}"
            return f"スクリーン(コード {self.screen_cd})"
        return f"Screen {self.screen_no}" if self.screen_no else f"Screen (code {self.screen_cd})"

    def title(self, lang: str = "ja") -> str:
        """劇場名 + スクリーン名 (一覧表示・plainスタイル用)。"""
        return f"{self.theater_name(lang)} {self.screen_label(lang)}"

    def subtitle(self, lang: str = "ja") -> str:
        if lang == "ja":
            s = f"全席空席表示  /  {self.n_seats}席 + 車いす席 {self.n_wheelchair}席"
        else:
            s = f"All seats shown as available  /  {self.n_seats} seats + {self.n_wheelchair} wheelchair"
        if self.facility:
            s += f"  /  {self.facility}"
        elif self.schedule_info and self.schedule_info.get("icons"):
            s += "  /  " + " ".join(self.schedule_info["icons"])
        return s


def _facility(html: str) -> str:
    m = FACILITY_RE.search(html)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()


def build_seatmaps(paths, schedule_paths=(), log=print, fetch_missing=False) -> list:
    """入力(.har/.zip/フォルダ)から SeatMap のリストを作る。"""
    sched = ScheduleIndex()
    pages, order = {}, []
    blobs = list(hario.iter_har_blobs(list(paths))) + list(hario.iter_har_blobs(list(schedule_paths)))
    if not blobs:
        log("入力に .har ファイルが見つかりません。")
    for name, data in blobs:
        try:
            har = hario.parse_har(data)
        except ValueError as e:
            log(f"[skip] {name}: HARとして読めません ({e})")
            continue
        for resp in hario.find_schedule_responses(har):
            sched.add_response(resp)
        found = hario.find_seat_pages(har, name)
        if not found:
            if not hario.find_schedule_responses(har):
                log(f"[skip] {name}: 座席ページ(TNPI2010J01)が見つかりません。座席選択画面を開いた状態で保存したHARか確認してください。")
            continue
        for pg in found:
            key = (pg.site_cd, pg.params.get("gekijyo_cd", ""), pg.params.get("screen_cd", ""))
            if key in pages:
                continue
            pages[key] = pg
            order.append(key)

    # 同じHARに複数スクリーンが入っている場合は出力名を区別する
    per_source = Counter(pages[k].source for k in order)
    maps = []
    for key in order:
        pg = pages[key]
        tables = parse_tables(extract_seat_region(pg.html))
        sheet, bg, note = None, None, ""
        m_css = CSS_LINK_RE.search(pg.html)
        if m_css:
            gek, scr = m_css.groups()
            css_b = assets.screen_asset(gek, scr, "css", pg.resources, fetch_missing)
            gif_b = assets.screen_asset(gek, scr, "gif", pg.resources, fetch_missing)
            if css_b and gif_b:
                sheet = parse_css(css_b.decode("utf-8", errors="replace"))
                bg = assets.to_image(gif_b)
                if bg is not None:
                    bg = assets.clear_outside(bg)
            else:
                note = f"{pg.source}: この画面の背景画像/CSSがHARに無いため自動描画の背景を使います(--fetch-missing でTOHOサイトから取得、または『キャッシュを無効化』してHARを取り直してください)。"
        box = layout_tables(tables, sheet if bg is not None else None)
        if not box.seats:
            log(f"[skip] {pg.source}: 座席が見つかりません")
            continue
        stem = os.path.splitext(pg.source)[0]
        if per_source[pg.source] > 1:
            stem += f"_{key[2]}"
        fm = FILENAME_RE.search(pg.source)
        m = STATED_RE.search(pg.html)
        sm = SeatMap(
            stem=stem,
            site_cd=pg.site_cd,
            screen_cd=key[2],
            screen_no=str(int(fm.group(1))) if fm else None,
            box=box,
            source=pg.source,
            params=pg.params,
            stated=(int(m.group(1)), int(m.group(2))) if m else None,
            facility=_facility(pg.html),
            schedule_info=sched.lookup(pg.site_cd, key[2]),
            sheet=sheet if bg is not None else None,
            bg=bg,
            resources=pg.resources,
        )
        if note:
            sm.warnings.append(note)
        if sm.stated and sm.stated != (sm.n_seats, sm.n_wheelchair):
            sm.warnings.append(
                f"ページ表記({sm.stated[0]}席+{sm.stated[1]}車いす席)と解析結果({sm.n_seats}席+{sm.n_wheelchair}車いす席)が一致しません。座席表に実在する席のみ描画しています。"
            )
        if sm.schedule_info and sm.schedule_info.get("seats") not in (None, sm.n_seats + sm.n_wheelchair):
            sm.warnings.append(
                f"スケジュールAPIの総席数({sm.schedule_info['seats']})と解析結果({sm.n_seats + sm.n_wheelchair})が一致しません。"
            )
        maps.append(sm)
    return maps


def make_scene(sm: SeatMap, opts: Options):
    if opts.style == "official":
        return build_official(sm, opts)
    footer = "TOHOシネマズ公式の座席ページ(HAR)から自動生成 / 空席状態" if opts.lang == "ja" else "Generated from TOHO Cinemas seat page (HAR)"
    tb = trim_box(sm.box)
    return build_scene(tb, sm.title(opts.lang), sm.subtitle(opts.lang), opts, footer=footer)


def render_image(sm: SeatMap, opts: Options, scale: float, fonts: FontSet):
    """PNG用のPIL画像。日本語フォントが無ければ自動で英語表記にする。"""
    o = dataclasses.replace(opts, lang="ja" if fonts.has_cjk else "en")
    return render_png(make_scene(sm, o), scale, fonts)


def render_svg_text(sm: SeatMap, opts: Options, scale: float) -> str:
    return render_svg(make_scene(sm, dataclasses.replace(opts, lang="ja")), scale)


def to_json(sm: SeatMap) -> dict:
    return {
        "source": sm.source,
        "site_cd": sm.site_cd,
        "screen_cd": sm.screen_cd,
        "title": sm.title("ja"),
        "seats": sm.n_seats,
        "wheelchair": sm.n_wheelchair,
        "counts": dict(sm.counts),
        "seat_list": [
            {
                "id": p.seat.seat_id,
                "row": p.seat.row,
                "number": p.seat.num,
                "kind": p.seat.kind,
                "blocked": p.seat.blocked,
                "x": p.x,
                "y": p.y,
                "w": p.w,
                "h": p.h,
            }
            for p in sm.box.seats
        ],
    }


def write_outputs(sm: SeatMap, outdir: str, formats, opts: Options, scale: float, fonts: FontSet, with_json=False) -> list:
    os.makedirs(outdir, exist_ok=True)
    written = []
    if "png" in formats:
        path = os.path.join(outdir, sm.stem + ".png")
        render_image(sm, opts, scale, fonts).save(path)
        written.append(path)
    if "svg" in formats:
        path = os.path.join(outdir, sm.stem + ".svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_svg_text(sm, opts, scale))
        written.append(path)
    if with_json:
        path = os.path.join(outdir, sm.stem + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_json(sm), f, ensure_ascii=False, indent=1)
        written.append(path)
    return written
