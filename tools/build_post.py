"""글 설계(spec.json) → post.html·post.json·images.json 생성 + 분량(1,500~1,900자)·'다.' 종결·금지어·링크·h1 검사.
사용: python tools/build_post.py spec.json posts/queue/<글폴더>   (검사 실패 시 종료코드 1, 파일 안 만듦)
spec 형식 예시는 tools/spec_example.json
"""
import json, re, sys, os
from pathlib import Path
BR = "<p><br></p>"
TABLE = '<table style="width:100%;border-collapse:collapse;">'
TD = 'style="border:1px solid #ddd;padding:8px;"'
def build(spec):
    out = [f'<img src="thumb.jpg" alt="{spec["kw"]}">', BR]
    for s in spec["intro"]: out.append(f"<p>{s}</p>")
    out.append(BR)
    for sec in spec["sections"]:
        out += [f"<h2>{sec['h2']}</h2>", BR]
        for blk in sec["blocks"]:
            kind = blk[0]
            if kind == "h3": out += [f"<h3>{blk[1]}</h3>", BR]
            elif kind == "p":
                for s in blk[1]: out.append(f"<p>{s}</p>")
                out.append(BR)
            elif kind == "img": out += [f'<img src="{blk[1]}" alt="{spec["kw"]}">', BR]
            elif kind == "table":
                rows = blk[1]
                t = [TABLE, "<tr>" + "".join(f"<th {TD}>{c}</th>" for c in rows[0]) + "</tr>"]
                t += ["<tr>" + "".join(f"<td {TD}>{c}</td>" for c in r) + "</tr>" for r in rows[1:]]
                out += ["".join(t) + "</table>", BR]
            elif kind == "ol":
                out.append("<ol>" + "".join(f"<li>{x}</li>" for x in blk[1]) + "</ol>"); out.append(BR)
    out.append(f'<p style="font-size:12px;color:#888;">{spec["foot"]}</p>')
    return "\n".join(out)

def check(html):
    body = re.sub(r"<p style=\"font-size:12px.*?</p>", "", html)
    text = re.sub(r"<[^>]+>", "", re.sub(r"<table.*?</table>", "", body, flags=re.S))
    n = len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", html)))
    bad = [p for p in re.findall(r"<p>(.*?)</p>", body) if p not in ("<br>",) and not p.rstrip().endswith("다.")]
    bad += [li for li in re.findall(r"<li>(.*?)</li>", body) if not li.endswith("다.")]
    plain = re.sub(r"<[^>]+>", "", html)
    forb = [w for w in ["충격","긴급","폭탄","털린","무조건","100%","쿠팡","FAQ"] if w in plain] + [w for w in ["<a ","<h1"] if w in html]
    return n, bad, forb

spec = json.load(open(sys.argv[1], encoding="utf-8"))
html = build(spec)
n, bad, forb = check(html)
print("글자수", n, "| 다.위반", bad, "| 금지어", forb)
if n < 1500 or n > 1900 or bad or forb: sys.exit(1)
D = Path(sys.argv[2]); D.mkdir(parents=True, exist_ok=True)
(D/"post.html").write_text(html, encoding="utf-8")
(D/"images.json").write_text(json.dumps(spec["images"], ensure_ascii=False, indent=1), encoding="utf-8")
(D/"post.json").write_text(json.dumps(spec["meta"], ensure_ascii=False, indent=2), encoding="utf-8")
