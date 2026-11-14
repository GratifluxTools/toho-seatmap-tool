import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests.make_sample_har import main as make_sample  # noqa: E402
from toho_seatmap.pipeline import build_seatmaps, make_fontset, write_outputs  # noqa: E402
from toho_seatmap.scene import Options  # noqa: E402
from toho_seatmap.seatmodel import classify  # noqa: E402


class TWriteProgress(unittest.TestCase):
    def test_progress_reports_each_file_start_and_end(self):
        from toho_seatmap.pipeline import build_seatmaps, make_fontset, write_outputs
        from toho_seatmap.scene import Options
        from tests.make_sample_har import main as make_sample

        with tempfile.TemporaryDirectory() as d:
            har = os.path.join(d, "toho_umeda_1.har")
            make_sample(har)
            sm = build_seatmaps([har], log=lambda m: None)[0]
            events = []
            files = write_outputs(sm, d, {"png", "svg"}, Options(style="plain", svg_objects=True), 1.0, make_fontset(),
                                  progress=lambda p, fin: events.append((os.path.basename(p), fin)))
            self.assertEqual(len(files), 2)
            self.assertEqual(events, [("toho_umeda_1_plane.png", False), ("toho_umeda_1_plane.png", True),
                                      ("toho_umeda_1_plane_hasObject.svg", False),
                                      ("toho_umeda_1_plane_hasObject.svg", True)])

    def test_progress_can_cancel_before_next_file(self):
        from toho_seatmap.pipeline import build_seatmaps, make_fontset, write_outputs
        from toho_seatmap.scene import Options
        from tests.make_sample_har import main as make_sample

        class Stop(Exception):
            pass

        def stop_at_svg(path, finished):
            if path.endswith(".svg") and not finished:
                raise Stop()

        with tempfile.TemporaryDirectory() as d:
            har = os.path.join(d, "toho_umeda_1.har")
            make_sample(har)
            sm = build_seatmaps([har], log=lambda m: None)[0]
            with self.assertRaises(Stop):
                write_outputs(sm, d, {"png", "svg"}, Options(style="plain"), 1.0, make_fontset(), progress=stop_at_svg)
            self.assertTrue(os.path.exists(os.path.join(d, "toho_umeda_1_plane.png")))
            self.assertFalse(os.path.exists(os.path.join(d, "toho_umeda_1_plane_noObject.svg")))


class T(unittest.TestCase):
    def test_classify(self):
        c = lambda i, s: classify({"id": i, "src": f"/x/{s}"})
        self.assertEqual(c("A-1", "seat_2.gif").kind, "normal")
        self.assertEqual(c("HC-1", "seat_4.gif").kind, "wheelchair")
        self.assertEqual(c("O-16", "seat_prm_2.gif").kind, "prm")
        self.assertEqual(c("H-3", "seat_premiere2_1.gif").kind, "premiere2")
        self.assertTrue(c("A-3", "seat_0.gif").blocked)
        self.assertIsNone(classify({"id": "x", "src": "spacer.gif"}))

    def test_sample_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            har = os.path.join(d, "toho_umeda_1.har")
            make_sample(har)
            maps = build_seatmaps([har], log=lambda m: None)
            self.assertEqual(len(maps), 1)
            sm = maps[0]
            self.assertEqual((sm.n_seats, sm.n_wheelchair), (11, 1))
            self.assertEqual(sm.counts["prm"], 3)
            self.assertEqual(sm.warnings, [])  # ページ表記と一致していれば警告なし
            files = write_outputs(sm, d, {"png", "svg"}, Options(), 2.0, make_fontset(), with_json=True)
            for f in files:
                self.assertTrue(os.path.getsize(f) > 0)


if __name__ == "__main__":
    unittest.main()


class TStyles(unittest.TestCase):
    def test_css_cascade_and_layout(self):
        from toho_seatmap.cssmini import Elem, parse_css

        sh = parse_css(".screen-table td{padding:0 0 7px 0} .premiam td{padding-bottom:4px} #f{padding-top:145px;padding-left:16px}")
        st = sh.style_for([Elem("table", None, ("screen-table",)), Elem("table", None, ("premiam",)), Elem("td")])
        self.assertEqual(st["padding-bottom"], "4px")
        self.assertEqual(sh.style_for([Elem("div", "f")])["padding-top"], "145px")

    def test_official_and_plain_render(self):
        import dataclasses

        from toho_seatmap.pipeline import render_image, render_svg_text

        with tempfile.TemporaryDirectory() as d:
            har = os.path.join(d, "toho_umeda_1.har")
            make_sample(har)
            sm = build_seatmaps([har], log=lambda m: None)[0]
            fonts = make_fontset()
            for style in ("official", "plain"):
                o = Options(style=style)
                img = render_image(sm, o, 1.0, fonts)
                self.assertGreater(img.width, 50)
                svg = render_svg_text(sm, o, 1.0)
                self.assertTrue(svg.startswith("<svg"))
            # 同梱の座席gifが使われる(official)
            self.assertIn("<image", render_svg_text(sm, Options(style="official"), 1.0))


class TLayoutFixes(unittest.TestCase):
    def test_nested_table_align_left_wins(self):
        # セルは align=center でも、入れ子の表が align=left なら左寄せ(池袋3の不具合の再発防止)
        from toho_seatmap.htmltable import parse_tables
        from toho_seatmap.layout import layout_tables

        seat = '<img id="{r}-{n}" width="15" height="22" src="/layout/0001/ppt/01/seat_{s}.gif">'
        html = (
            '<table class="screen-table">'
            "<tr><td>" + seat.format(r="A", n=1, s="1") + "</td><td>" + seat.format(r="A", n=2, s="1") + "</td>"
            "<td>" + seat.format(r="A", n=3, s="1") + "</td><td>" + seat.format(r="A", n=4, s="1") + "</td></tr>"
            '<tr><td colspan="4" align="center" class="paddingLeft2"><table align="left" width="50%"><tr>'
            "<td>" + seat.format(r="B", n=1, s="prm_1") + "</td></tr></table></td></tr></table>"
        )
        box = layout_tables(parse_tables(html))
        b1 = [p for p in box.seats if p.seat.row == "B"][0]
        self.assertLess(b1.x, 20)  # 中央(約30px)ではなく左端付近


class TTitleAndNames(unittest.TestCase):
    def _sm(self, d, site="037"):
        har = os.path.join(d, "toho_umeda_1.har")
        make_sample(har)
        sm = build_seatmaps([har], log=lambda m: None)[0]
        sm.site_cd = site
        return sm

    def test_official_header_is_theater_only(self):
        from toho_seatmap.official import build_official
        from toho_seatmap.scene import Text

        with tempfile.TemporaryDirectory() as d:
            sm = self._sm(d)
            texts = [i.s for i in build_official(sm, Options(style="official")).items if isinstance(i, Text)]
            self.assertIn("TOHOシネマズ 梅田", texts)  # 劇場名のみ
            self.assertFalse(any("スクリーン1" in t and "梅田" in t for t in texts))
            self.assertTrue(any("全席空席表示" in t for t in texts))  # 席数表示はそのまま

    def test_plain_title_keeps_screen_label(self):
        with tempfile.TemporaryDirectory() as d:
            sm = self._sm(d)
            self.assertEqual(sm.title("ja"), "TOHOシネマズ 梅田 スクリーン1")

    def test_manual_theater_name(self):
        import toho_seatmap.theaters as th

        with tempfile.TemporaryDirectory() as d:
            sm = self._sm(d, site="099")
            self.assertFalse(sm.theater_known)
            self.assertEqual(sm.theater_name("ja"), "TOHOシネマズ (site 099)")
            sm.theater_override = "TOHOシネマズ テスト"
            self.assertTrue(sm.theater_known)
            self.assertEqual(sm.theater_name("ja"), "TOHOシネマズ テスト")
            # 設定ファイルへの記憶
            os.environ["XDG_CONFIG_HOME"] = d
            th._USER = None
            self.assertTrue(th.save_user_name("099", "TOHOシネマズ 保存名"))
            th._USER = None
            self.assertEqual(th.name_for("099"), "TOHOシネマズ 保存名")
            th.save_user_name("099", "")
            self.assertFalse(th.is_known("099"))
            del os.environ["XDG_CONFIG_HOME"]
            th._USER = None

    def test_relative_offset_from_tr_class(self):
        from toho_seatmap.cssmini import parse_css
        from toho_seatmap.htmltable import parse_tables
        from toho_seatmap.layout import layout_tables

        sheet = parse_css(".table1 td{position:relative;left:-8px} .screen-table td{padding:0 0 7px 0}")
        img = '<img id="A-1" width="15" height="22" src="/layout/0001/ppt/01/seat_1.gif">'
        html = f'<table class="screen-table" cellspacing="0"><tr class=\'table1\'><td>{img}</td></tr></table>'
        box = layout_tables(parse_tables(html), sheet)
        self.assertEqual(box.seats[0].x, -8.0)


class TInlineAndBackground(unittest.TestCase):
    def test_inline_td_style_and_table_margin_auto(self):
        # なんば2: <td style="padding-bottom:0"> と <table style="margin:0 auto"> (行のずれ/車いす席の中央寄せ)
        from toho_seatmap.cssmini import parse_css
        from toho_seatmap.htmltable import parse_tables
        from toho_seatmap.layout import layout_tables

        sheet = parse_css(".screen-table td{padding:0 0 7px 0}")
        s = '<img id="{i}" width="13" height="19" src="/layout/0001/ppt/01/seat_{k}.gif">'
        html = (
            '<table class="screen-table" cellspacing="0">'
            '<tr><td colspan="6" style="padding-bottom:0;">'
            '<table style="margin:0 auto;" class="screen-table" cellspacing="0"><tr><td>' + s.format(i="HC-1", k=4) + "</td></tr></table>"
            "</td></tr>"
            "<tr>" + "".join("<td>" + s.format(i=f"E-{n}", k=1) + "</td>" for n in range(1, 7)) + "</tr></table>"
        )
        box = layout_tables(parse_tables(html), sheet)
        hc = [p for p in box.seats if p.seat.row == "HC"][0]
        e = [p for p in box.seats if p.seat.row == "E" and p.seat.num == 1][0]
        self.assertEqual(e.y, 19 + 7)  # D列相当の行は下余白0(+ネストの7)で26px。33pxにならない
        self.assertAlmostEqual(hc.x, (6 * 13 - 13) / 2)  # 6列ぶんの幅の中央に寄る

    def test_clear_outside_and_dominant_bg(self):
        from PIL import Image, ImageDraw

        from toho_seatmap import assets
        from toho_seatmap.official import dominant_bg

        im = Image.new("RGBA", (40, 40), (255, 255, 255, 255))  # 外側は白
        d = ImageDraw.Draw(im)
        d.polygon([(8, 4), (32, 4), (36, 36), (4, 36)], fill=(0, 0, 0, 255))  # 黒い枠
        d.polygon([(10, 6), (30, 6), (33, 34), (7, 34)], fill=(97, 98, 100, 255))  # 灰色の内側
        d.rectangle([18, 18, 22, 22], fill=(255, 255, 255, 255))  # 内側の白(非常口など)
        out = assets.clear_outside(im)
        self.assertEqual(out.getpixel((1, 1))[3], 0)  # 外側は透明
        self.assertEqual(out.getpixel((20, 20)), (255, 255, 255, 255))  # 内側の白は残る
        self.assertEqual(dominant_bg(out), (97, 98, 100))


class TOutlineKept(unittest.TestCase):
    def test_thin_light_outline_next_to_frame_is_kept(self):
        # 梅田4: 黒い枠線の外縁に沿う薄い白線(アンチエイリアスの明るい画素)は消さない
        from PIL import Image

        from toho_seatmap import assets

        im = Image.new("RGBA", (12, 12), (0, 0, 0, 0))  # 外側は透過
        px = im.load()
        for y in range(2, 10):
            for x in range(2, 10):
                px[x, y] = (0, 0, 0, 255)  # 黒い枠
        for y in range(2, 10):
            px[1, y] = (200, 200, 200, 255)  # 外縁の薄い白線(輝度200)
        out = assets.clear_outside(im)
        self.assertEqual(out.getpixel((1, 5))[3], 255)  # 線は残る
        self.assertEqual(out.getpixel((0, 5))[3], 0)  # 透過の外側は透明のまま


class TBareNestedTable(unittest.TestCase):
    def test_bare_nested_table_has_zero_spacing(self):
        # 西宮2: 属性のない入れ子の表(最下行)の座席は 15px 間隔で並び、親の表の列を引き伸ばさない
        from toho_seatmap.cssmini import parse_css
        from toho_seatmap.htmltable import parse_tables
        from toho_seatmap.layout import layout_tables

        sheet = parse_css(".screen-table td{width:13px;padding:0 0 7px 0}")
        s = '<img id="{i}" width="15" height="22" src="/layout/0001/ppt/01/seat_1.gif">'
        top = "".join("<td>" + s.format(i=f"K-{n}") + "</td>" for n in range(1, 8))
        low = "".join("<td>" + s.format(i=f"L-{n}") + "</td>" for n in range(1, 8))
        html = (
            '<table class="screen-table" cellspacing="0" cellpadding="0">'
            f"<tr>{top}</tr>"
            f'<tr><td colspan="7"><table><tr>{low}</tr></table></td></tr></table>'  # 属性なしの素の<table>
        )
        box = layout_tables(parse_tables(html), sheet)
        k = sorted([p for p in box.seats if p.seat.row == "K"], key=lambda p: p.x)
        l = sorted([p for p in box.seats if p.seat.row == "L"], key=lambda p: p.x)
        self.assertEqual([p.x for p in k], [i * 15.0 for i in range(7)])  # 列が引き伸ばされない
        self.assertEqual([p.x for p in l], [i * 15.0 for i in range(7)])  # セル間隔0


class TFormats(unittest.TestCase):
    def _sm(self, d):
        har = os.path.join(d, "toho_umeda_1.har")
        make_sample(har)
        return build_seatmaps([har], log=lambda m: None)[0]

    def test_webp_is_lossless_copy_of_png(self):
        from PIL import Image, ImageChops

        with tempfile.TemporaryDirectory() as d:
            sm = self._sm(d)
            files = write_outputs(sm, d, {"png", "webp"}, Options(), 2.0, make_fontset())
            png = [f for f in files if f.endswith(".png")][0]
            webp = [f for f in files if f.endswith(".webp")][0]
            a, b = Image.open(png).convert("RGB"), Image.open(webp).convert("RGB")
            self.assertIsNone(ImageChops.difference(a, b).getbbox())  # PNGを変換しただけ(劣化なし)

    def test_svg_objects_each_seat_is_a_group(self):
        import re
        import xml.dom.minidom

        from toho_seatmap.pipeline import render_svg_text

        with tempfile.TemporaryDirectory() as d:
            sm = self._sm(d)
            for style in ("official", "plain"):
                svg = render_svg_text(sm, Options(style=style, svg_objects=True), 1.0)
                doc = xml.dom.minidom.parseString(svg)
                seats = [g for g in doc.getElementsByTagName("g") if g.getAttribute("class") == "seat"]
                self.assertEqual(len(seats), len(sm.box.seats))  # 全席がグループ
                ids = [g.getAttribute("id") for g in doc.getElementsByTagName("g")]
                self.assertEqual(len(ids), len(set(ids)))  # idは重複しない
                self.assertTrue(any(i == "seat-A-1" for i in ids))
                self.assertIn("layer-seats", ids)
                self.assertTrue(re.search(r'data-kind="prm"', svg))
            # オプション無しは従来どおり(座席のグループなし)
            flat = render_svg_text(sm, Options(), 1.0)
            self.assertNotIn('class="seat"', flat)

    def test_icon_assets_exist(self):
        from toho_seatmap.icon_data import PNG_B64
        import base64

        self.assertTrue(base64.b64decode(PNG_B64).startswith(b"\x89PNG"))
