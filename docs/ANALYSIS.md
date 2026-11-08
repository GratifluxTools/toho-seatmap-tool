# TOHOシネマズ 座席表・スケジュールの表示方法 (HAR解析メモ)

対象: 日比谷(081) / なんば(032) / ららぽーと門真(088) / 池袋(084) / 梅田(037) の全52スクリーン + 梅田スケジュール。

## 1. 座席表

- 取得: `POST https://hlo.tohotheater.jp/net/ticket/{site_cd}/TNPI2010J01.do`
  - フォーム: `site_cd, jyoei_date, gekijyo_cd, screen_cd, sakuhin_cd, pf_no, pageid=2000J01, enter_kbn, seq_no`
  - レスポンスは **サーバー側で組み立て済みのHTML** (Windows-31J)。座席データ用のJSON APIは無い。
  - `<!--Screen Table Start-->` 〜 `<!--Screen Table End-->` の間の `<table>` が座席表。
- 座席 = `<td><img id="A-16" src="/layout/0001/ppt/01/seat_1.gif" onclick="seatSelect('A','16','1')"></td>`
  - `id` = `{行記号}-{番号}`。車いす席は `HC-1, HC-2 ...`。
  - 画像サイズ(11x19 / 13x19 / 15x22 / 20x20 ...)がそのまま座席の大きさ。
- 通路 = 空の `<td>` または `spacer.gif`。行間の通路は `<!-- 通路 -->` の行(高さだけの spacer)。
- 特別席ブロック = `colspan/rowspan` を持つ `<td>` の中の **入れ子 `<table>`** (class: `premiam` / `front-lik` / `screen-table-premiam`)。入れ子はさらに入れ子になることがある。
- 劇場・スクリーンごとの `…/layout/{gekijyo_cd}/ppt/{screen_cd}/screen.css|screen.gif|spacer.gif` が余白調整とスクリーン画像を担当。
- ページ内に「`N席 + M車いす席`」の表記あり (突き合わせに使用)。

### 画像名と席種

| ファイル名 | 意味 | 使われている画面 |
|---|---|---|
| `seat_1.gif` | 通常席・空席 | 全て |
| `seat_2.gif` | 通常席・購入済み | 全て |
| `seat_0.gif` | 選択不可 (販売対象外) | 多数 |
| `seat_3.gif` | 選択中 (凡例のみ) | - |
| `seat_4.gif` (id=`HC-n`) | 車いす席 | 全スクリーン |
| `seat_prm_1/2.gif` | プレミア ボックス シート (`premiam` テーブル内) | 日比谷2-13以外ほぼ全て、梅田1-3、池袋3/6/7/10、なんば1/6/7 |
| `seat_lux_1/2.gif` | プレミア ラグジュアリー シート | 日比谷1 |
| `seat_cnfo_1/2.gif` | ワイド コンフォート シート | 門真2/3/7/9 |
| `seat_premiere2_0/1/2.gif` | プレミア シート | 門真6/7 |
| `seat_mx4d_left/center/right_1/2.gif` | MX4Dシート | なんば5 |

末尾の数字が状態 (0=選択不可 / 1=空席 / 2=購入済み)。`premiere2` のように種別名に数字を含むので、末尾の `_<数字>.gif` だけを状態とみなす。
**HAR取得時の購入済み席は、状態 2→1 と読み替えて全席空席として描く。**

### 背景画像(通路・出入口・行記号)の仕組み
`<div id="screen-defimg">` が `screen.css` で `background-image: url(screen.gif)` を持ち(画面ごとの画像、例: 530x599)、
SCREEN表示・出入口・非常口・行記号(A,B,…)・列番号・特別席の枠線・階段などは **すべてこの背景画像に描かれている**。
座席テーブルは `#screen-list-frame {padding-top:145px; padding-left:16px}` のように画面ごとの余白で背景の上に重ねられ、
セルの余白は `.screen-table td {padding-bottom:7px}` / `td.paddingLeftN` などのCSSで決まる。
ツールは screen.css を解釈して同じ位置に座席gifを重ねる。座席gifは `width/height` 属性の大きさに拡縮して表示される(実寸と異なる場合あり)。

### 検証結果
- 52画面すべてで「座席表上の席数 = ページ表記の席数」。
- 車いす席数は日比谷の11画面でページ表記より座席表上の `HC` が1つ少ない (HTML内に該当席なし。ツールは警告を出して実在する席のみ描画)。
- 梅田のスケジュールAPIの `allSeatNum` は 席数+車いす席 と一致 (例: 梅田1 = 728 = 724+4)。

## 2. スケジュール (梅田)

1. `GET /net/schedule/037/TNPI2000J01.do` は **殻のHTML** (上映データを含まない)。
2. ページのJS (`scheduleUtils.js`, `theaterTop.js` 等) が XHR で `api2.tohotheater.jp` のJSON APIを呼ぶ (CORS: `Origin: https://hlo.tohotheater.jp`)。
   - `GET /api/schedule/v1/schedule/037/TNPI3050J03?vg_cd=037&show_day=YYYYMMDD&term=99&seq_disp_term=7&…` → 日付タブ (7日分: 日付・曜日・イベント名)
   - `GET /api/schedule/v2/schedule/037/TNPI3050J05?vg_cd=037&show_day=YYYYMMDD&isMember=&enter_kbn=&_dc=…` → その日の上映一覧
3. v2 のJSON構造: `data[0].list[]`(館グループ) → `.list[]`(作品: `mcode, name, ename, hours`) → `.list[]`(上映回)
   - 上映回: `showingStart, showingEnd, code, unsoldSeatInfo{unsoldSeatStatus: A/…/G…}, screen{code, name, theaterCd, allSeatNum, iconNm2…}`
4. 上映回をクリックすると、座席表の `TNPI2010J01.do` へPOST:
   `screen_cd = screen.code`, `gekijyo_cd = screen.theaterCd`, `sakuhin_cd = mcode`, `pf_no = 上映回の code` (データ上の対応から推定。該当JSは今回のHARに含まれず未確認)。
