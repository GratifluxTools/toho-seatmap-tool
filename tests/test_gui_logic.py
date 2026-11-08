"""GUIのロジック(読み込み・劇場名の手動入力・保存)を、tkinter を差し替えて実際に動かして確認する。

tkinter が無い環境(CIのサーバー等)でも動くよう、画面部品はダミーに置き換える。
"""
import importlib
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests.make_sample_har import main as make_sample  # noqa: E402


class _Dummy:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        return lambda *a, **k: None


class _Var:
    def __init__(self, value=None, **k):
        self.v = value

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


class _Listbox(_Dummy):
    def __init__(self, *a, **k):
        self.items, self.sel = [], ()

    def insert(self, idx, txt):
        self.items.append(txt)

    def delete(self, a, b=None):
        self.items.clear()
        self.sel = ()

    def selection_set(self, i):
        self.sel = (i,)

    def curselection(self):
        return self.sel


class _Text(_Dummy):
    def __init__(self, *a, **k):
        self.lines = []

    def insert(self, idx, txt):
        self.lines.append(txt)


class _Canvas(_Dummy):
    def winfo_width(self):
        return 800

    def winfo_height(self):
        return 600


class _Tk(_Dummy):
    def after(self, ms, fn):
        fn()


def _fake_modules(ask_result):
    tk = types.ModuleType("tkinter")
    ttk = types.ModuleType("tkinter.ttk")
    mb = types.ModuleType("tkinter.messagebox")
    fd = types.ModuleType("tkinter.filedialog")
    tk.Tk, tk.StringVar, tk.BooleanVar, tk.DoubleVar = _Tk, _Var, _Var, _Var
    tk.Listbox, tk.Text, tk.Canvas = _Listbox, _Text, _Canvas
    for n in ("Frame", "Label", "Button", "Entry", "Spinbox", "Checkbutton", "Radiobutton", "LabelFrame"):
        setattr(ttk, n, _Dummy)
    mb.calls = []
    mb.showinfo = lambda *a, **k: mb.calls.append(("info",) + a)
    mb.showerror = lambda *a, **k: mb.calls.append(("error",) + a)
    mb.askyesno = lambda *a, **k: (mb.calls.append(("ask",) + a), ask_result)[1]
    tk.ttk, tk.messagebox, tk.filedialog = ttk, mb, fd
    imagetk = types.ModuleType("PIL.ImageTk")
    imagetk.PhotoImage = _Dummy
    return {"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb, "tkinter.filedialog": fd, "PIL.ImageTk": imagetk}


class TGui(unittest.TestCase):
    def setUp(self):
        self._saved = {k: sys.modules.get(k) for k in ("tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog", "PIL.ImageTk", "toho_seatmap.gui")}
        self.tmp = tempfile.TemporaryDirectory()
        self.har = os.path.join(self.tmp.name, "toho_umeda_1.har")
        make_sample(self.har)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        self.tmp.cleanup()

    def _app(self, ask_result=False):
        sys.modules.update(_fake_modules(ask_result))
        sys.modules.pop("toho_seatmap.gui", None)
        gui = importlib.import_module("toho_seatmap.gui")
        gui.threading.Thread = lambda target, daemon=None: types.SimpleNamespace(start=target)  # 同期実行
        app = gui.App()
        app.inputs = [self.har]
        return gui, app

    def test_load_lists_maps_and_asks_about_missing_background(self):
        gui, app = self._app(ask_result=False)
        app.load()
        self.assertEqual(len(app.maps), 1)
        self.assertIn("背景なし", app.lb_maps.items[0])  # サンプルは背景無し
        asks = [c for c in gui.messagebox.calls if c[0] == "ask"]
        self.assertEqual(len(asks), 1)  # 取得するか尋ねる

    def test_manual_theater_name_before_and_after_load(self):
        gui, app = self._app()
        app.v_name.set("TOHOシネマズ 手入力")
        app.apply_name()  # 読み込み前
        app.load()
        self.assertEqual(app.maps[0].theater_name("ja"), "TOHOシネマズ 手入力")
        # 読み込み後、選択中の画面のみ変更
        app.lb_maps.selection_set(0)
        app.v_name_scope.set("one")
        app.v_name.set("TOHOシネマズ 別名")
        app.apply_name()
        self.assertEqual(app.maps[0].theater_name("ja"), "TOHOシネマズ 別名")
        # 空欄で自動判定に戻る
        app.v_name.set("")
        app.apply_name()
        self.assertIsNone(app.maps[0].theater_override)

    def test_save_all_writes_files(self):
        gui, app = self._app()
        app.load()
        app.v_out.set(os.path.join(self.tmp.name, "out"))
        app.save_all()
        names = sorted(os.listdir(os.path.join(self.tmp.name, "out")))
        self.assertIn("toho_umeda_1.png", names)
        self.assertIn("toho_umeda_1.svg", names)


class TSharedResources(unittest.TestCase):
    def test_seats_drawn_even_when_bundled_assets_unreadable(self):
        # 再現: 未同梱の劇場で、座席gif/背景/CSSがHARに記録されておらず、同梱ファイルも読めない
        from toho_seatmap import assets
        from toho_seatmap.pipeline import build_seatmaps, make_fontset, render_image
        from toho_seatmap.scene import Options

        with tempfile.TemporaryDirectory() as d:
            har = os.path.join(d, "toho_newtheater_2.har")
            make_sample(har)
            orig = assets._dirs
            assets._dirs = lambda: iter(())
            try:
                sm = build_seatmaps([har], log=lambda m: None)[0]
                img = render_image(sm, Options(), 1.0, make_fontset())
                white = sum(1 for p in img.convert("RGB").get_flattened_data() if p == (255, 255, 255)) if hasattr(img, "get_flattened_data") else sum(1 for p in img.convert("RGB").getdata() if p == (255, 255, 255))
            finally:
                assets._dirs = orig
            self.assertGreater(white, 500)  # 座席(白)が描かれている

    def test_schedule_theater_name_for_unknown_site(self):
        from toho_seatmap.schedule import ScheduleIndex

        s = ScheduleIndex()
        s.add_response({"data": [{"vitCd": "099", "list": [{"name": "ＴＯＨＯシネマズ新宿", "code": "099", "list": []}]}]})
        self.assertEqual(s.theater_name("099"), "TOHOシネマズ 新宿")

    def test_self_check(self):
        from toho_seatmap import assets

        info = assets.self_check()
        self.assertGreaterEqual(info["embedded_seat_gifs"], 10)


if __name__ == "__main__":
    unittest.main()
