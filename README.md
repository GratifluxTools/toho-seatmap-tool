# toho-seatmap

TOHOシネマズの座席選択ページを保存した **HARファイル** から、**全席空席の座席表**(PNG/SVG)を自動生成するツールです。
既定では **公式サイトと同じ見た目**(背景画像+座席gifを screen.css どおりに重ねたもの)で、通路・出入口・非常口・行記号・
プレミア ボックス/ラグジュアリー/ワイド コンフォート/プレミア シート・車いす席・選択不可席まで再現します。GUI と CLI の両方があります。

- 解析メモ(座席表/スケジュールの仕組み): [docs/ANALYSIS.md](docs/ANALYSIS.md)
- 通信はしません。HARの中の座席ページHTMLだけを読みます (HARにはCookie等が含まれるため、他人へ渡す際は注意)。

## 使い方

### HARの作り方
ブラウザで座席選択画面(`…/TNPI2010J01.do`)を開いた状態で、開発者ツール → Network → 「HARとしてエクスポート(コンテンツ付き)」。
スクリーンごとに1ファイル。`toho_<館名>_<番号>.har` という名前なら番号がタイトルに使われます。

### GUI
`toho-seatmap-gui` を起動 → 「ファイル追加」で `.har` / `.zip` / フォルダを選択 → 「座席表を読み込む」→ プレビュー確認 → 「すべて保存」。

### CLI
```
toho-seatmap-cli toho_umeda.zip toho_hibiya.zip -o out
toho-seatmap-cli toho_umeda_1.har -f png --scale 3 --no-numbers
toho-seatmap-cli *.zip --schedule toho_umeda_schedule.har --json
```
主なオプション: `--fetch-missing`(HARに背景が無い画面の背景/CSSをTOHOサイトから取得) / `-f png,svg` / `--scale` / `--style official|plain` / `--no-title` / `--no-legend` / `--blocked mark|normal|hide` / `--schedule` / `--font` / `--json`

`--style official`(既定): 公式風。`plain`: 明るい配色のベクター描画(席番号入り、`--no-numbers` で番号なし)。

`--blocked`: `seat_0`(選択不可)の扱い。既定は灰色に×。全て通常席として見せたい場合は `normal`。

### 劇場名
劇場コードから自動判定します(日比谷・なんば・ららぽーと門真・池袋・梅田)。それ以外の劇場は「TOHOシネマズ (site コード)」と表示されるので、手動で指定できます。
- GUI: 画面一覧で画面を選び、「劇場名」欄に入力して「適用」(同じ劇場コードの全画面に反映/次回以降も記憶、を選べます)。未登録の劇場は一覧に「※劇場名未登録」と出ます。
- CLI: `--theater-name "084=TOHOシネマズ 池袋"`(コード付きはその劇場のみ)、`--theater-name "TOHOシネマズ ○○"`(全画面)。複数指定可。
- 記憶した名前は `%APPDATA%\toho-seatmap\theaters.json`(Linux: `~/.config/toho-seatmap/theaters.json`)に保存されます。
- 公式風スタイルでは、画像最上部は劇場名のみ(スクリーン番号は画像内のSCREEN表示)。プレーンスタイルでは劇場名+スクリーン名です。

### Pythonから直接
```
pip install -r requirements.txt
python run_cli.py …        # CLI (引数なしで GUI)
python run_gui.py          # GUI (tkinter が必要)
python -m unittest discover -s tests
```

## ビルド (GitHub Actions)
Actions タブ → **Build** → *Run workflow* で `windows` / `linux` / `both` を選択。
完了後、Artifacts に以下が出ます。
- `toho-seatmap-windows-x64`: `toho-seatmap-gui.exe`, `toho-seatmap-cli.exe` (Python不要の単一exe)
- `toho-seatmap-linux-x64`: `.tar.gz` (中に gui / cli。展開後すぐ実行可)

### Release に載せる (`.github/workflows/release.yml`)
Build が成功したあと、Actions タブ → **Release** → *Run workflow* でタグ名(例 `v0.1.0`)を入力して実行すると、
成功済みの Build の成果物が GitHub Release に添付されます(ビルドはやり直しません)。
- `run_id` を空欄にすると最新の成功した Build を使います。特定の Build を使うときはその実行IDを指定します(Build実行画面のURL末尾の数字)。
- 添付されるのは `toho-seatmap-<タグ>-windows-x64.zip`(GUI/CLIのexe)と `toho-seatmap-<タグ>-linux-x64.tar.gz` です。
- 同じタグの Release が既にあれば、添付ファイルを上書きします。`prerelease` にチェックでプレリリース扱いにできます。
- リポジトリが Private の場合、Release を見られるのはリポジトリに権限のある人だけです(座席gif・背景は著作物のため Private を推奨)。

Linux版は日本語フォント(Noto Sans CJK)を同梱します。Windows版はOS標準フォントを使います。

## 背景画像・座席gifについて
- 座席gif(`toho_seatmap/assets/seats/`)と、各画面の背景gif/CSS(`assets/screens/`)を同梱しています(利用者のHARから抽出)。
- 画面固有の背景/CSSは **HARに記録されていればそれを優先**、無ければ同梱分を使います。
- 取得したアセットはローカルにキャッシュされます(Windows: `%LOCALAPPDATA%\toho-seatmap\screens`、Linux: `~/.cache/toho-seatmap/screens`)。`--fetch-missing`(GUIは「不足する背景画像をTOHOサイトから取得」)を付けると、不足分をTOHOサイトの静的ファイル(`/layout/<劇場>/ppt/<画面>/screen.gif|css`)から取得します。この時だけ通信が発生します。
- 今回の同梱分で全52画面(日比谷・なんば・ららぽーと門真・池袋・梅田)の背景/CSSが揃っています。どれも無い画面は、同じ配色で SCREEN 表示と行記号を自動描画します。
  背景まで公式どおりにしたい場合は、そのスクリーンのHARを **開発者ツールの「キャッシュを無効化」にチェックを入れて** 取り直し、
  `python tools/extract_assets.py <HARやZIP...>` で同梱アセットを更新してください。
- これらの画像はTOHOシネマズの著作物です。**リポジトリは非公開(Private)にしてください**。公開する場合は `toho_seatmap/assets/` を外してください(座席gif・背景は無くても動作し、自動描画になります)。

## 台形・斜めなど、形のあるスクリーン
背景gifの枠の外側(白や透過)は、外周につながる部分だけを透明にして、灰色の背景色(画像内で最も多い灰色)を見せています。
枠線の外縁に沿う薄い白線(元画像に描かれた縁取り)は残します。タイトル帯・凡例の背景も同じ灰色です。HTML内の `style` 属性(例: `padding-bottom:0`、`margin:0 auto`)にも対応しています。

## 仕組み
HARから座席ページHTMLを抽出 → screen.css を解釈して入れ子`<table>`を画素座標に展開(ブラウザの表レイアウト相当) → 席種を画像名で判定 → 背景gif+座席gifを重ねて PNG(Pillow)/SVG(画像埋め込み)。

## 制限
- GUIはドラッグ&ドロップ非対応 (ファイル選択ダイアログ)。
- 席種名: prm=プレミア ボックス シート / lux=プレミア ラグジュアリー シート / cnfo=ワイド コンフォート シート / premiere2=プレミア シート。
- `seat_0`(選択不可)は黒い席で表示(`--blocked normal` で通常席扱い)。
- 日比谷は、ページ表記より車いす席が座席表上1つ少ない画面があります(警告表示)。
