"""tkinter製GUI。HAR/ZIP/フォルダを選んで座席表を生成・プレビュー・保存する。"""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from . import __version__, theaters
from .pipeline import build_seatmaps, make_fontset, render_image, write_outputs
from .scene import Options


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"TOHO 座席表ジェネレーター {__version__}")
        self.geometry("1100x720")
        self.minsize(820, 520)
        try:  # ウィンドウ/タスクバーのアイコン(コードに埋め込み済みなので、ファイル同梱に依存しない)
            from .icon_data import PNG_B64

            self._icon = tk.PhotoImage(data=PNG_B64)
            self.iconphoto(True, self._icon)
        except Exception:
            pass
        self.inputs: list = []
        self.schedules: list = []
        self.maps: list = []
        self.fonts = make_fontset()
        self._photo = None
        self.default_name = ""  # 読み込み前に入力された劇場名
        self._build()

    # ---- UI ------------------------------------------------------------
    def _build(self):
        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")
        right = ttk.Frame(self, padding=8)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="入力 (.har / .zip / フォルダ)").pack(anchor="w")
        self.lb_in = tk.Listbox(left, width=44, height=6)
        self.lb_in.pack(fill="x")
        row = ttk.Frame(left)
        row.pack(fill="x", pady=2)
        ttk.Button(row, text="ファイル追加…", command=self.add_files).pack(side="left")
        ttk.Button(row, text="フォルダ追加…", command=self.add_dir).pack(side="left", padx=4)
        ttk.Button(row, text="クリア", command=self.clear).pack(side="left")
        ttk.Label(left, text="※スケジュールのHARも一緒に入れると画面名が正式名になります", foreground="#666").pack(anchor="w")

        opt = ttk.LabelFrame(left, text="オプション", padding=6)
        opt.pack(fill="x", pady=6)
        self.v_png = tk.BooleanVar(value=True)
        self.v_svg = tk.BooleanVar(value=True)
        self.v_webp = tk.BooleanVar(value=False)
        self.v_svgobj = tk.BooleanVar(value=False)
        self.v_num = tk.BooleanVar(value=True)
        self.v_json = tk.BooleanVar(value=False)
        self.v_scale = tk.DoubleVar(value=2.0)
        self.v_blocked = tk.StringVar(value="mark")
        self.v_style = tk.StringVar(value="official")
        self.v_title = tk.BooleanVar(value=True)
        self.v_legend = tk.BooleanVar(value=True)
        self.v_fetch = tk.BooleanVar(value=False)
        r = ttk.Frame(opt); r.pack(anchor="w")
        ttk.Checkbutton(r, text="PNG", variable=self.v_png).pack(side="left")
        ttk.Checkbutton(r, text="SVG", variable=self.v_svg, command=self._sync_svg_option).pack(side="left", padx=6)
        ttk.Checkbutton(r, text="WebP", variable=self.v_webp).pack(side="left")
        ttk.Checkbutton(r, text="JSON", variable=self.v_json).pack(side="left", padx=6)
        # SVGを選んだときだけ表示するオプション
        self.f_svgopt = ttk.Frame(opt)
        ttk.Checkbutton(self.f_svgopt, text="座席を1席ずつオブジェクトにする(SVG)", variable=self.v_svgobj).pack(anchor="w")
        ttk.Label(self.f_svgopt, text="レイヤー>行>座席のグループ。Illustrator/Inkscape等で個別に選択できます", foreground="#666").pack(anchor="w")
        self._svgopt_anchor = r
        ttk.Label(opt, text="スタイル").pack(anchor="w")
        for val, txt in (("official", "公式サイト風(背景gif+座席gif)"), ("plain", "プレーン(明るい配色)")):
            ttk.Radiobutton(opt, text=txt, value=val, variable=self.v_style, command=self.refresh_preview).pack(anchor="w")
        ttk.Checkbutton(opt, text="タイトル帯", variable=self.v_title, command=self.refresh_preview).pack(anchor="w")
        ttk.Checkbutton(opt, text="凡例", variable=self.v_legend, command=self.refresh_preview).pack(anchor="w")
        ttk.Checkbutton(opt, text="不足する背景画像をTOHOサイトから取得(通信あり)", variable=self.v_fetch).pack(anchor="w")
        ttk.Checkbutton(opt, text="席番号を表示(プレーンのみ)", variable=self.v_num, command=self.refresh_preview).pack(anchor="w")
        r = ttk.Frame(opt); r.pack(anchor="w", pady=2)
        ttk.Label(r, text="拡大率").pack(side="left")
        ttk.Spinbox(r, from_=0.5, to=6.0, increment=0.5, width=5, textvariable=self.v_scale).pack(side="left", padx=4)
        ttk.Label(opt, text="選択不可席(seat_0)の扱い").pack(anchor="w")
        for val, txt in (("mark", "灰色に×で表示"), ("normal", "通常の空席として表示"), ("hide", "描かない")):
            ttk.Radiobutton(opt, text=txt, value=val, variable=self.v_blocked, command=self.refresh_preview).pack(anchor="w")

        ttk.Label(left, text="出力フォルダ").pack(anchor="w")
        r = ttk.Frame(left); r.pack(fill="x")
        self.v_out = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "seatmaps"))
        ttk.Entry(r, textvariable=self.v_out).pack(side="left", fill="x", expand=True)
        ttk.Button(r, text="参照…", command=self.pick_out).pack(side="left", padx=4)

        ttk.Button(left, text="座席表を読み込む", command=self.load).pack(fill="x", pady=(10, 2))
        ttk.Button(left, text="すべて保存", command=self.save_all).pack(fill="x")

        ttk.Label(left, text="検出した画面").pack(anchor="w", pady=(8, 0))
        self.lb_maps = tk.Listbox(left, width=44, height=10)
        self.lb_maps.pack(fill="both", expand=True)
        self.lb_maps.bind("<<ListboxSelect>>", lambda _e: self.on_select())

        nm = ttk.LabelFrame(left, text="劇場名 (手動入力。空欄で自動判定に戻す)", padding=6)
        nm.pack(fill="x", pady=(6, 0))
        self.v_name = tk.StringVar()
        self.v_name_scope = tk.StringVar(value="site")
        self.v_name_save = tk.BooleanVar(value=True)
        self.lbl_name = ttk.Label(nm, text="読み込み前に入力しても、読み込み後に全画面へ反映されます")
        self.lbl_name.pack(anchor="w")
        row = ttk.Frame(nm)
        row.pack(fill="x")
        self.ent_name = ttk.Entry(row, textvariable=self.v_name)
        self.ent_name.pack(side="left", fill="x", expand=True)
        self.ent_name.bind("<Return>", lambda _e: self.apply_name())
        ttk.Button(row, text="適用", command=self.apply_name).pack(side="left", padx=4)
        for val, txt in (("one", "選択中の画面のみ"), ("site", "同じ劇場コードの全画面"), ("all", "読み込み済みの全画面")):
            ttk.Radiobutton(nm, text=txt, value=val, variable=self.v_name_scope).pack(anchor="w")
        ttk.Checkbutton(nm, text="次回以降も記憶する(劇場コード単位)", variable=self.v_name_save).pack(anchor="w")

        self.log = tk.Text(left, height=6, width=44, state="disabled", wrap="word")
        self.log.pack(fill="x", pady=(6, 0))

        self.canvas = tk.Canvas(right, bg="#f3f4f6", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.refresh_preview())
        self._sync_svg_option()

    def _sync_svg_option(self):
        """SVGにチェックがあるときだけ「座席をオブジェクトにする」を表示する。"""
        if self.v_svg.get():
            self.f_svgopt.pack(anchor="w", after=self._svgopt_anchor)
        else:
            self.f_svgopt.pack_forget()

    # ---- 操作 ----------------------------------------------------------
    def say(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def add_files(self):
        fs = filedialog.askopenfilenames(title="HAR / ZIP を選択", filetypes=[("HAR/ZIP", "*.har *.zip"), ("すべて", "*.*")])
        for f in fs:
            if f not in self.inputs:
                self.inputs.append(f)
                self.lb_in.insert("end", f)

    def add_dir(self):
        d = filedialog.askdirectory(title="HARを含むフォルダ")
        if d and d not in self.inputs:
            self.inputs.append(d)
            self.lb_in.insert("end", d)

    def clear(self):
        self.inputs.clear()
        self.lb_in.delete(0, "end")

    def pick_out(self):
        d = filedialog.askdirectory(title="出力フォルダ")
        if d:
            self.v_out.set(d)

    def opts(self) -> Options:
        return Options(
            show_numbers=self.v_num.get(),
            blocked_mode=self.v_blocked.get(),
            style=self.v_style.get(),
            show_title=self.v_title.get(),
            show_legend=self.v_legend.get(),
            svg_objects=bool(self.v_svg.get() and self.v_svgobj.get()),
        )

    def load(self):
        if not self.inputs:
            messagebox.showinfo("入力なし", "HAR / ZIP / フォルダを追加してください。")
            return
        self.say("読み込み中…")

        def work():
            msgs = []
            maps = build_seatmaps(self.inputs, log=msgs.append, fetch_missing=self.v_fetch.get())
            self.after(0, lambda: self._loaded(maps, msgs))

        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, maps, msgs):
        for m in msgs:
            self.say(m)
        self.maps = maps
        if self.default_name:
            for sm in maps:
                sm.theater_override = self.default_name
        for sm in maps:
            for w in sm.warnings:
                self.say(f"[注意] {sm.stem}: {w}")
            if not sm.theater_known:
                self.say(f"[注意] 劇場コード {sm.site_cd} の劇場名が未登録です。「劇場名」欄に入力して「適用」を押してください。")
        self._refill_list()
        self.say(f"{len(maps)} 件の座席表を検出しました。")
        if maps:
            self.on_select()
        missing = [sm for sm in maps if sm.bg is None]
        if missing and not self.v_fetch.get():
            if messagebox.askyesno(
                "背景画像が見つかりません",
                f"{len(missing)} 画面で、背景画像(通路・出入口・行記号)がHARにも同梱分にもありません。\n"
                "今は灰色の自動描画で座席のみ表示しています。\n\n"
                "TOHOサイトから背景画像とCSSを取得して、公式と同じ見た目にしますか?\n"
                "(この画面だけ通信します。取得したものは保存され、次回以降は通信しません)",
            ):
                self.v_fetch.set(True)
                self.load()

    def _label(self, sm) -> str:
        mark = "" if sm.theater_known else "  ※劇場名未登録"
        if sm.bg is None:
            mark += "  [背景なし]"
        return f"{sm.title('ja')}  ({sm.n_seats}+{sm.n_wheelchair}){mark}"

    def _refill_list(self, keep=None):
        self.lb_maps.delete(0, "end")
        for sm in self.maps:
            self.lb_maps.insert("end", self._label(sm))
        if self.maps:
            self.lb_maps.selection_set(keep if keep is not None else 0)

    def on_select(self):
        sel = self.lb_maps.curselection()
        if sel and self.maps:
            sm = self.maps[sel[0]]
            self.v_name.set(sm.theater_name("ja"))
            self.lbl_name.configure(
                text=f"劇場コード {sm.site_cd} の劇場名:" + ("" if sm.theater_known else "  (未登録: 入力してください)"),
                foreground="#000000" if sm.theater_known else "#c0392b",
            )
        self.refresh_preview()

    def apply_name(self):
        name = self.v_name.get().strip()
        if not self.maps:
            self.default_name = name
            self.say(f"劇場名「{name}」を、読み込み後に全画面へ適用します。" if name else "劇場名の手動指定を解除しました。")
            return
        sel = self.lb_maps.curselection()
        cur = self.maps[sel[0]] if sel else self.maps[0]
        scope = self.v_name_scope.get()
        if scope == "one":
            targets = [cur]
        elif scope == "all":
            targets = list(self.maps)
        else:
            targets = [sm for sm in self.maps if sm.site_cd == cur.site_cd]
        for sm in targets:
            sm.theater_override = name or None
        if name and self.v_name_save.get() and scope != "one":
            if theaters.save_user_name(cur.site_cd, name):
                self.say(f"劇場コード {cur.site_cd} = 「{name}」 を記憶しました。")
            else:
                self.say("劇場名を設定ファイルに保存できませんでした(この回のみ有効)。")
        self.say(f"{len(targets)} 画面の劇場名を「{name or '自動判定'}」にしました。")
        self._refill_list(sel[0] if sel else 0)
        self.on_select()

    def refresh_preview(self):
        sel = self.lb_maps.curselection()
        if not sel or not self.maps:
            return
        sm = self.maps[sel[0]]
        img = render_image(sm, self.opts(), 2.0, self.fonts)
        cw, ch = max(self.canvas.winfo_width(), 50), max(self.canvas.winfo_height(), 50)
        k = min(cw / img.width, ch / img.height, 1.0)
        if k < 1.0:
            from PIL import Image

            img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo)

    def save_all(self):
        if not self.maps:
            messagebox.showinfo("未読み込み", "先に「座席表を読み込む」を実行してください。")
            return
        formats = {f for f, v in (("png", self.v_png), ("svg", self.v_svg), ("webp", self.v_webp)) if v.get()}
        if not formats and not self.v_json.get():
            messagebox.showinfo("形式未選択", "PNG / SVG / WebP / JSON のいずれかを選んでください。")
            return
        out = self.v_out.get()
        n = 0
        try:
            for sm in self.maps:
                n += len(write_outputs(sm, out, formats, self.opts(), float(self.v_scale.get()), self.fonts, with_json=self.v_json.get()))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("保存に失敗", str(e))
            return
        self.say(f"{n} ファイルを {out} に保存しました。")
        messagebox.showinfo("完了", f"{n} ファイルを保存しました。\n{out}")


def main() -> int:
    App().mainloop()
    return 0
