"""CI/テスト用の最小サンプルHAR(実サイトと同じ構造の合成データ)を生成する。"""
import json
import os

ROW = '<td><img id="{r}-{n}" name="{r}-{n}" width="15" height="22" src="/layout/0001/ppt/01/seat_{s}.gif" alt="" onclick="JavaScript:seatSelect(\'{r}\',\'{n}\', \'1\');" /></td>'


def seat(r, n, s="1"):
    return ROW.format(r=r, n=n, s=s)


def build_html():
    rows = []
    rows.append("<tr>" + "".join(seat("A", n, "2" if n == 2 else "1") for n in range(1, 5)) + "<td></td>" + seat("HC", 1, "4") + "</tr>")
    rows.append("<tr>" + "".join(seat("B", n, "0" if n == 3 else "1") for n in range(1, 5)) + "<td></td><td></td></tr>")
    nested = "<table class=\"premiam\"><tr>" + "".join(seat("C", n).replace("seat_1.gif", "seat_prm_1.gif") for n in range(1, 4)) + "</tr></table>"
    rows.append(f'<tr><td colspan="6" class="paddingLeft2" align="center">{nested}</td></tr>')
    html = (
        "<html><body><!--Screen Table Start-->\n<div id=\"screen-table-1\"><table class=\"screen-table\">"
        + "".join(rows)
        + "</table></div>\n<!--Screen Table End-->"
        + "<td>11&nbsp;<span class=\"message-page-seat\">席</span>&nbsp;+&nbsp;1&nbsp;<span class=\"message-theaterInfo-seat-wheelChair\">車いす席</span></td>"
        + "</body></html>"
    )
    return html


def main(path):
    har = {"log": {"entries": [{
        "request": {"method": "POST", "url": "https://hlo.tohotheater.jp/net/ticket/037/TNPI2010J01.do",
                    "postData": {"params": [{"name": "site_cd", "value": "037"}, {"name": "screen_cd", "value": "11"}, {"name": "gekijyo_cd", "value": "0371"}]}},
        "response": {"status": 200, "content": {"mimeType": "text/html;charset=Windows-31J", "text": build_html()}},
    }]}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(har, f, ensure_ascii=False)


if __name__ == "__main__":
    main(os.path.join(os.path.dirname(__file__), "sample", "sample.har"))
