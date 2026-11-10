"""座席表HTML(入れ子の<table>)を軽量な木構造にパースする。標準ライブラリのみ使用。"""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class Img:
    attrs: dict


@dataclass
class Cell:
    attrs: dict
    colspan: int = 1
    rowspan: int = 1
    items: list = field(default_factory=list)  # Img | Table


@dataclass
class Row:
    attrs: dict = field(default_factory=dict)  # <tr class='table1'> などCSSの照合に使う
    cells: list = field(default_factory=list)


@dataclass
class Table:
    attrs: dict
    rows: list = field(default_factory=list)

    @property
    def classes(self) -> list:
        return (self.attrs.get("class") or "").split()


def _int(v, default=1) -> int:
    try:
        return max(1, int(str(v).strip()))
    except (TypeError, ValueError):
        return default


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.stack = []

    def _nearest(self, kind):
        for obj in reversed(self.stack):
            if isinstance(obj, kind):
                return obj
        return None

    def _pop_to(self, kind, inclusive):
        while self.stack:
            top = self.stack[-1]
            if isinstance(top, kind):
                if inclusive:
                    self.stack.pop()
                return
            self.stack.pop()

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if tag == "table":
            t = Table(a)
            cell = self.stack[-1] if self.stack and isinstance(self.stack[-1], Cell) else None
            if cell is not None:
                cell.items.append(t)
            else:
                self.tables.append(t)
            self.stack.append(t)
        elif tag == "tr":
            if self._nearest(Table) is None:
                return
            while self.stack and not isinstance(self.stack[-1], Table):
                self.stack.pop()
            row = Row(a)
            self.stack[-1].rows.append(row)
            self.stack.append(row)
        elif tag in ("td", "th"):
            if self._nearest(Table) is None:
                return
            while self.stack and not isinstance(self.stack[-1], Row):
                if isinstance(self.stack[-1], Table):
                    row = Row()
                    self.stack[-1].rows.append(row)
                    self.stack.append(row)
                    break
                self.stack.pop()
            cell = Cell(a, colspan=_int(a.get("colspan")), rowspan=_int(a.get("rowspan")))
            self.stack[-1].cells.append(cell)
            self.stack.append(cell)
        elif tag == "img":
            cell = self._nearest(Cell)
            if cell is not None:
                cell.items.append(Img(a))

    def handle_startendtag(self, tag, attrs):
        if tag == "img":
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            if self._nearest(Cell) is not None:
                self._pop_to(Cell, True)
        elif tag == "tr":
            if self._nearest(Row) is not None:
                self._pop_to(Row, True)
        elif tag == "table":
            if self._nearest(Table) is not None:
                self._pop_to(Table, True)


def parse_tables(html: str) -> list:
    p = _Parser()
    p.feed(html)
    p.close()
    return p.tables


def extract_seat_region(html: str) -> str:
    """座席テーブル部分のHTMLだけを切り出す。"""
    s = html.find("Screen Table Start")
    if s >= 0:
        e = html.find("Screen Table End", s)
        return html[s : e if e >= 0 else len(html)]
    s = html.find('id="screen-table-1"')
    if s >= 0:
        return html[s:]
    return html
