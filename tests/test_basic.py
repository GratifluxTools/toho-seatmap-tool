import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests.make_sample_har import main as make_sample  # noqa: E402
from toho_seatmap.pipeline import build_seatmaps, make_fontset, write_outputs  # noqa: E402
from toho_seatmap.scene import Options  # noqa: E402
from toho_seatmap.seatmodel import classify  # noqa: E402


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
