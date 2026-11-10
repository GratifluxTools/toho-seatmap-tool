"""assets/seats/*.gif を toho_seatmap/seat_gifs.py (base64埋め込み)に書き出す。

座席gifは小さい(合計数十KB)ので、データファイルの同梱(PyInstaller等で漏れがち)に頼らず、
Pythonコードの中に埋め込んでおく。assets/seats を更新したらこのスクリプトを再実行する。
"""
import base64
import glob
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "toho_seatmap")


def main():
    items = []
    for p in sorted(glob.glob(os.path.join(ROOT, "assets", "seats", "seat_*.gif"))):
        with open(p, "rb") as f:
            items.append((os.path.basename(p), base64.b64encode(f.read()).decode()))
    out = ['"""座席gif(seat_*.gif)のbase64埋め込み。tools/gen_seat_gifs.py で自動生成。"""', "", "GIFS = {"]
    for name, b64 in items:
        out.append(f'    "{name}": (')
        for i in range(0, len(b64), 100):
            out.append(f'        "{b64[i:i + 100]}"')
        out.append("    ),")
    out.append("}")
    with open(os.path.join(ROOT, "seat_gifs.py"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"{len(items)} 件の座席gifを seat_gifs.py に埋め込みました。")


if __name__ == "__main__":
    main()
