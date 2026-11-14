"""ビルド前に toho_seatmap/__init__.py の版番号を書き換える(CI用)。

使い方: python tools/set_version.py 0.1.0
  タグ名 v0.1.0 からは先頭の v を取り除いた値(0.1.0)を渡す。
  不正な形式(例: "v1.0" のような3桁未満)は失敗させる。
"""
import os
import re
import sys

PATTERN = re.compile(r"^\d+\.\d+\.\d+([-.][0-9A-Za-z.]+)?$")
INIT = os.path.join(os.path.dirname(__file__), "..", "toho_seatmap", "__init__.py")


def main(argv):
    if len(argv) != 2:
        print("usage: set_version.py VERSION", file=sys.stderr)
        return 2
    version = argv[1].removeprefix("v")
    if not PATTERN.match(version):
        print(f"版番号の形式が不正です: {argv[1]!r} (例: v0.1.0 / 0.1.0-beta)", file=sys.stderr)
        return 1
    with open(INIT, encoding="utf-8") as f:
        src = f.read()
    new, n = re.subn(r'^__version__ = .*$', f'__version__ = "{version}"', src, flags=re.M)
    if n != 1:
        print("__init__.py に __version__ の行が見つかりません", file=sys.stderr)
        return 1
    with open(INIT, "w", encoding="utf-8") as f:
        f.write(new)
    print("version set to", version)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
