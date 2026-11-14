"""중복 글 검사: 새 글 제목·메인 키워드가 8개 블로그 전체(발행·예약·대기·라이브 점검본)의 기존 글과 겹치는지 본다.
사용: python tools/dup_check.py "<제목>" "<메인 키워드>" [제외할 폴더이름]  → 겹치면 목록 출력 후 exit 1."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOSA = re.compile(r"(으로|에서|에게|까지|부터|보다|하는|하기|할때|은|는|이|가|을|를|의|에|와|과|도|로|만)$")
STOP = {"방법", "확인", "기준", "이유", "차이", "가지", "단계", "순서", "정리", "체크리스트", "주의점", "주의", "때", "전", "후",
        "법", "것", "할", "볼", "점검", "설정", "2026년", "2026", "언제", "얼마", "어디로", "무엇", "필요한", "놓치기", "쉬운"}


def toks(t):
    out = set()
    for w in re.sub(r"[^0-9A-Za-z가-힣 ]", " ", t).lower().split():
        w = JOSA.sub("", w) if len(w) > 2 else w
        w = re.sub(r"^\d+(가지|단계|개)$", "", w)
        if len(w) >= 2 and w not in STOP:
            out.add(w)
    return out


def corpus(skip=""):
    seen = {}
    for d in ("published", "queue"):
        for p in (ROOT / "posts" / d).glob("*/post.json"):
            if p.parent.name == skip or "seofix" in p.parent.name:
                continue
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
                m = m.get("meta", m)
                if m.get("title") and str(m.get("status", "")).upper() not in ("DELETED",):
                    seen[m["title"]] = m.get("blog", "main")
            except Exception:
                pass
    try:
        for b in json.loads((ROOT / "posts" / "audit" / "live.json").read_text(encoding="utf-8"))["blogs"]:
            for p in b.get("posts", []):
                seen.setdefault(p["title"], b.get("url", ""))
    except Exception:
        pass
    return seen


def check(title, kw, skip=""):
    tt, kt = toks(title), toks(kw)
    hits = []
    for t, blog in corpus(skip).items():
        if t == title:
            continue
        o = toks(t)
        j = len(tt & o) / max(1, len(tt | o))
        kin = len(kt) >= 2 and kt <= o
        if j >= 0.4 or kin:
            hits.append((round(j, 2), blog, t))
    return sorted(hits, reverse=True)


if __name__ == "__main__":
    hits = check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3] if len(sys.argv) > 3 else "")
    for h in hits[:8]:
        print("중복 의심", h)
    if hits:
        print("→ 8개 블로그 어디에든 같은 고민을 다룬 글이 있다. 주제를 바꾼다(각도만 바꾸지 않는다).")
        sys.exit(1)
    print("중복 없음")
