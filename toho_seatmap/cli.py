"""コマンドライン版。引数なしで起動した場合はGUIを開く。"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .pipeline import build_seatmaps, make_fontset, write_outputs
from .scene import Options


def _setup_streams() -> None:
    """日本語を出力しても落ちないようにする。

    GitHub Actions など出力がパイプ/リダイレクトの時、Windowsの標準出力は cp1252 になり
    日本語の print で UnicodeEncodeError になる。その場合は UTF-8 に切り替える。
    対話コンソールはそのまま(Python 3.6+ は Unicode対応)にし、変換不能文字は ? に置換して落とさない。
    --windowed ビルドでは標準出力自体が None になるので何もしない。
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="toho-seatmap",
        description="TOHOシネマズの座席ページ(HAR)から、全席空席の座席表画像(PNG/SVG)を生成します。",
    )
    p.add_argument("inputs", nargs="*", help=".har / .zip(中に.har) / フォルダ (複数可)")
    p.add_argument("-o", "--outdir", default="seatmaps", help="出力フォルダ (既定: ./seatmaps)")
    p.add_argument("-f", "--format", default="png,svg", help="png, svg, webp をカンマ区切りで (既定: png,svg)。webpはPNGと同じ見た目のロスレス")
    p.add_argument(
        "--svg-objects",
        action="store_true",
        help="SVG: 座席を1席ずつ選択できるオブジェクトにする(レイヤー>行>座席のグループ、id=seat-A-16、data-*付き。画像はファイルが大きくなります)",
    )
    p.add_argument("--scale", type=float, default=2.0, help="拡大率 (既定: 2.0)")
    p.add_argument("--no-numbers", action="store_true", help="席番号を表示しない (plainスタイルのみ。officialは背景に番号が描かれています)")
    p.add_argument(
        "--blocked",
        choices=["mark", "normal", "hide"],
        default="mark",
        help="選択不可席(seat_0)の扱い: mark=灰色に×(既定) / normal=通常の空席として表示 / hide=描かない",
    )
    p.add_argument(
        "--style",
        choices=["official", "plain"],
        default="official",
        help="official=公式サイト風(背景gif+座席gif、既定) / plain=明るい配色のベクター描画",
    )
    p.add_argument("--no-title", action="store_true", help="タイトル帯を付けない")
    p.add_argument("--no-legend", action="store_true", help="凡例を付けない")
    p.add_argument(
        "--fetch-missing",
        action="store_true",
        help="HAR・同梱分に無い画面の背景画像/CSSを、TOHOサイトの静的ファイルから取得してキャッシュ (通信が発生します)",
    )
    p.add_argument(
        "--theater-name",
        action="append",
        default=[],
        metavar="[コード=]劇場名",
        help="劇場名を手動指定。『084=TOHOシネマズ 池袋』のようにコード付きなら該当劇場のみ、劇場名だけなら全て。複数可",
    )
    p.add_argument("--schedule", action="append", default=[], help="スケジュールのHAR (画面名の取得用。複数可)")
    p.add_argument("--font", help="日本語フォントのパス (.ttf/.ttc/.otf)。省略時は自動検出")
    p.add_argument("--json", action="store_true", help="座席データ(JSON)も出力")
    p.add_argument("--self-check", action="store_true", help="同梱アセット(座席gif・画面の背景/CSS・フォント)が読めるか確認して終了")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv=None) -> int:
    _setup_streams()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        try:
            from .gui import main as gui_main
        except Exception as e:  # tkinter が無い環境など
            build_parser().print_help()
            print(f"\n(GUIを起動できませんでした: {e})", file=sys.stderr)
            return 2
        return gui_main()
    args = build_parser().parse_args(argv)
    if args.self_check:
        from . import assets
        from .fonts import find_cjk_font

        info = assets.self_check()
        print(f"embedded_seat_gifs={info['embedded_seat_gifs']}")
        print(f"bundled_screen_files={info['bundled_screen_files']}")
        print(f"font={find_cjk_font() or 'none'}")
        return 0 if info["embedded_seat_gifs"] >= 10 else 1
    if not args.inputs:
        build_parser().print_help()
        return 2
    formats = {f.strip().lower() for f in args.format.split(",") if f.strip()}
    bad = formats - {"png", "svg", "webp"}
    if bad or not formats:
        print(f"--format は png / svg / webp のみ指定できます: {sorted(bad)}", file=sys.stderr)
        return 2

    maps = build_seatmaps(args.inputs, args.schedule, log=lambda m: print(m, file=sys.stderr), fetch_missing=args.fetch_missing)
    if not maps:
        print("座席表を生成できませんでした。", file=sys.stderr)
        return 1
    for spec in args.theater_name:
        code, sep, name = spec.partition("=")
        if sep and code.strip().isdigit():
            for sm in maps:
                if sm.site_cd == code.strip():
                    sm.theater_override = name.strip()
        else:
            for sm in maps:
                sm.theater_override = spec.strip()
    for sm in maps:
        if not sm.theater_known:
            print(f"[注意] 劇場コード {sm.site_cd} の劇場名が未登録です({sm.source})。--theater-name で指定できます。", file=sys.stderr)
    fonts = make_fontset(args.font)
    if "png" in formats and not fonts.has_cjk:
        print("[warn] 日本語フォントが見つからないため、PNGは英語表記になります (--font で指定可、SVGは日本語のまま)。", file=sys.stderr)
    opts = Options(
        show_numbers=not args.no_numbers,
        blocked_mode=args.blocked,
        style=args.style,
        show_title=not args.no_title,
        show_legend=not args.no_legend,
        svg_objects=args.svg_objects,
    )
    for sm in maps:
        files = write_outputs(sm, args.outdir, formats, opts, args.scale, fonts, with_json=args.json)
        print(f"{sm.title('ja')}: {sm.n_seats}席 + 車いす{sm.n_wheelchair}席 -> " + ", ".join(files))
        for w in sm.warnings:
            print(f"  [注意] {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
