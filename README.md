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
保存中は進捗ウィンドウ(進捗バー・現在のファイル名・件数)を表示します。「中止」を押すと、次のファイルから書き出しを止めます(保存済みのファイルは残ります)。

### CLI
```
toho-seatmap-cli toho_umeda.zip toho_hibiya.zip -o out
toho-seatmap-cli toho_umeda_1.har -f png --scale 3 --no-numbers
toho-seatmap-cli *.zip --schedule toho_umeda_schedule.har --json
```
主なオプション: `--fetch-missing`(HARに背景が無い画面の背景/CSSをTOHOサイトから取得) / `-f png,svg` / `--scale` / `--style official|plain` / `--no-title` / `--no-legend` / `--blocked mark|normal|hide` / `--schedule` / `--font` / `--json`

`--style official`(既定): 公式風。`plain`: 明るい配色のベクター描画(席番号入り、`--no-numbers` で番号なし)。

`--blocked`: `seat_0`(選択不可)の扱い。既定は灰色に×。全て通常席として見せたい場合は `normal`。

### 出力形式
- ファイル名: `<入力名>_<スタイル>.<拡張子>`。スタイルは `plane`(プレーン) / `official`(公式風)。
  例: `toho_umeda_4_plane.png`、`toho_umeda_4_official.png`、SVGは `toho_umeda_4_plane_hasObject.svg` / `toho_umeda_4_plane_noObject.svg`(公式風も同様に `official_*`)。SVGの `hasObject` / `noObject` は `--svg-objects` の有無です。JSONは `<入力名>.json`。
- `-f png,svg,webp`: **WebP は PNG と同じ画像をロスレス(劣化なし)で変換**したものです(ファイルは小さくなります)。
- SVG は座席を1席ずつ選択できるオブジェクトにできます: CLI `--svg-objects` / GUI「座席を1席ずつオブジェクトにする(SVG)」(SVGを選んだときだけ表示)。
  構造は レイヤー(`layer-seats`) > 行(`row-A`) > 座席(`seat-A-16`、`data-row/number/kind/blocked`、ツールチップ付き)。
  Illustrator / Inkscape / Figma などで個別に選択・色変更できます。画像を座席ごとに埋め込むため、通常のSVGより大きくなります。

### アイコン
`assets/icon/`(`icon.svg` / `icon-1024.png` / `icon-256.png` / `icon.ico`)。濃紺のタイルに光るスクリーンと座席を配したシンプルなデザインで、どの映画館チェーン版にも使えます。特別席の色(アクセント色)だけを版ごとに変えられます:
`python tools/make_icon.py --accent "#2EC4B6" --out assets/icon-teal`(`--embed` でGUIのウィンドウアイコンも更新)。

### 劇場名
劇場コードから自動判定します(日比谷・なんば・ららぽーと門真・池袋・梅田)。それ以外の劇場は「TOHOシネマズ (site コード)」と表示されるので、手動で指定できます。
- GUI: 画面一覧で画面を選び、「劇場名」欄に入力して「適用」(同じ劇場コードの全画面に反映/次回以降も記憶、を選べます)。未登録の劇場は一覧に「※劇場名未登録」と出ます。
- CLI: `--theater-name "084=TOHOシネマズ 池袋"`(コード付きはその劇場のみ)、`--theater-name "TOHOシネマズ ○○"`(全画面)。複数指定可。
- 記憶した名前は `%APPDATA%\toho-seatmap\theaters.json`(Linux: `~/.config/toho-seatmap/theaters.json`)に保存されます。
- 公式風スタイルでは、画像最上部は劇場名のみ(スクリーン番号は画像内のSCREEN表示)。プレーンスタイルでは劇場名+スクリーン名です。

### 同梱アセットの確認(exe/バイナリが正しくビルドされたか)
`toho-seatmap-cli --self-check` で、座席gif(埋め込み)・画面の背景/CSS(同梱)・フォントが読めるか確認できます(GitHub Actionsのビルドでも自動で検査しています)。

### Pythonから直接
```
pip install -r requirements.txt
python run_cli.py …        # CLI (引数なしで GUI)
python run_gui.py          # GUI (tkinter が必要)
python -m unittest discover -s tests
```

## リリース (GitHub Actions)

ワークフローは `.github/workflows/build.yml` の1つだけです。

### 新しい版を出す(通常の手順)
1. GitHub の **Releases → Draft a new release** で、タグ名を `v0.1.0` のように入力して公開(Publish)します。
2. 公開をきっかけに Build が自動で動きます。タグ名から版番号(`0.1.0`)を決め、Windows / Linux の両方をビルドして、そのRelease に添付します。
   - 添付ファイル: `toho-seatmap-v0.1.0-windows-x64.zip`(GUI/CLIのexe) と `toho-seatmap-v0.1.0-linux-x64.tar.gz`
   - 版番号はビルドの中だけで書き換えます(リポジトリの `toho_seatmap/__init__.py` は変更されません)。exe の `--version` と GUI のタイトルに反映されます。
   - タグは `v0.1.0` / `0.1.0` / `0.1.0-beta` の形式(3つの数字が必要)。違う形式だと失敗します。
3. 失敗した場合は Actions タブのログを確認してください。修正後は、Release を削除して同じタグで作り直すと、自動で再ビルド・添付されます。

### テストビルド(添付しない)
Actions タブ → **Build** → *Run workflow* で、対象OS(`windows` / `linux` / `both`)と版番号(空欄なら `0.0.0-dev`)を指定して実行します。成果物は Artifacts にだけ出ます。

- リポジトリが Private の場合、Release を見られるのはリポジトリに権限のある人だけです(座席gif・背景は著作物のため Private を推奨)。
- Windows版は `toho-seatmap-gui.exe` / `toho-seatmap-cli.exe`(Python不要の単一exe)。Linux版は `.tar.gz` を展開し、`chmod +x` のうえ実行します。

Linux版は日本語フォント(Noto Sans CJK)を同梱します。Windows版はOS標準フォントを使います。

## 同梱していない劇場(新しい劇場)を処理するとき
座席gif(席の見た目)は**プログラム内に埋め込み済み**なので、HARに記録が無くても必ず座席が描かれます。HAR間でも画像を共有します(1つのHARにだけ記録されていれば、他のスクリーンでも使います)。
背景画像(通路・出入口・行記号)とCSSは劇場・スクリーンごとに異なります。HARに無い画面は、灰色の自動描画の背景に座席を載せて表示します。公式と同じ見た目にするには:
- GUI: 読み込み後に「背景画像が見つかりません」と出たら「はい」を選ぶと、TOHOサイトから取得して再読み込みします(「不足する背景画像をTOHOサイトから取得」のチェックでも可)。
- CLI: `--fetch-missing` を付けます。
- または、開発者ツールの「キャッシュを無効化」にチェックを入れてHARを取り直します。
劇場名は、スケジュールのHARを一緒に入れると自動で入ります(「TOHOシネマズ 新宿」など)。入れない/自動で入らない場合は、GUIの「劇場名」欄で手動入力できます(読み込み前でも可)。

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
