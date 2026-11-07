"""HAR/ZIPから座席gif・画面ごとの背景gif/CSSを抽出して toho_seatmap/assets/ に追加・更新する。

使い方: python tools/extract_assets.py toho_*.zip other.har ...
HARは「キャッシュを無効化」して保存したものほど多くのアセットが含まれます。
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from toho_seatmap import hario  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "toho_seatmap", "assets")


def main(paths):
    n_seat = n_screen = 0
    for name, data in hario.iter_har_blobs(paths):
        try:
            res = hario.find_layout_resources(hario.parse_har(data))
        except ValueError:
            continue
        for path, b in res.items():
            m = re.fullmatch(r"/layout/0001/ppt/01/(seat_[^/]+\.gif)", path)
            if m:
                os.makedirs(os.path.join(ROOT, "seats"), exist_ok=True)
                with open(os.path.join(ROOT, "seats", m.group(1)), "wb") as f:
                    f.write(b)
                n_seat += 1
                continue
            m = re.fullmatch(r"/layout/(\d+)/ppt/(\d+)/screen\.(css|gif)", path)
            if m:
                os.makedirs(os.path.join(ROOT, "screens"), exist_ok=True)
                with open(os.path.join(ROOT, "screens", f"{m.group(1)}_{m.group(2)}.{m.group(3)}"), "wb") as f:
                    f.write(b)
                n_screen += 1
    print(f"座席gif {n_seat} 件 / 画面アセット {n_screen} 件を更新しました。")


if __name__ == "__main__":
    main(sys.argv[1:]) if len(sys.argv) > 1 else print(__doc__)
