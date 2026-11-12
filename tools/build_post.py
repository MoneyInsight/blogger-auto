"""글 설계(spec.json) → post.html·post.json·images.json 생성 + 분량(1,500~2,600자, 직전 글과 250자 이상 차이)·'다.' 종결·금지어·링크·h1 검사.
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
    if spec.get("refs"):
        out.append('<p style="font-size:13px;color:#666;">참고 자료: ' + " · ".join(spec["refs"]) + "</p>")
    out.append(f'<p style="font-size:12px;color:#888;">{spec["foot"]}</p>')
    return "\n".join(out)

def check(html):
    body = re.sub(r"<p style=\"font-size:1[23]px.*?</p>", "", html)
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
# 분량은 글마다 달라야 한다: 1,500~2,600자 안에서, 같은 블로그 직전 글과 250자 이상 차이
def _prev_len(blog):
    root = Path(__file__).resolve().parent.parent / "posts"
    cur = Path(sys.argv[2]).name
    cands = sorted((p for d in ("queue", "published") for p in (root / d).glob("*/post.json") if p.parent.name != cur),
                   key=lambda p: p.parent.name, reverse=True)
    for p in cands[:400]:
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("blog") == blog and (p.parent / "post.html").exists():
                h = (p.parent / "post.html").read_text(encoding="utf-8")
                return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", h)))
        except Exception:
            pass
    return None
prev = _prev_len(spec.get("meta", {}).get("blog"))
same = prev is not None and abs(n - prev) < 250
if same: print(f"분량이 같은 블로그 직전 글({prev}자)과 비슷함 — 250자 이상 차이 나게 줄이거나 늘린다(억지로 늘리지 말고 구성을 바꾼다)")
if n < 1500 or n > 2600 or same or bad or forb: sys.exit(1)
D = Path(sys.argv[2]); D.mkdir(parents=True, exist_ok=True)
(D/"post.html").write_text(html, encoding="utf-8")
(D/"images.json").write_text(json.dumps(spec["images"], ensure_ascii=False, indent=1), encoding="utf-8")
(D/"post.json").write_text(json.dumps(spec["meta"], ensure_ascii=False, indent=2), encoding="utf-8")
