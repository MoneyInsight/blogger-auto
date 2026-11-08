"""
색인·노출 점검기 (100점 만점) — 90점 이상만 발행
사용:
  python tools/seo_gate.py posts/queue/<글폴더>          점검만
  python tools/seo_gate.py posts/queue/<글폴더> --fix    기계적으로 고칠 수 있는 것은 고친 뒤 재점검
  python tools/seo_gate.py --all posts/published          전체 글 점수표
종료코드: 90점 이상 0, 미만 1

점수는 '노출 확률'이 아니라 구글·네이버가 공개한 색인/검색 품질 기준을 얼마나 지켰는지다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = 90
BANNED = ["긴급", "무조건", "쿠팡", "자주 묻는 질문", "FAQ"]


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def guess_kw(meta, html):
    """메인 키워드: spec의 kw → 제목 속 2~3단어 중 본문에 가장 많이 나오는 말(앞쪽 우선)."""
    if meta.get("kw"):
        return meta["kw"]
    body = plain(html).replace(" ", "")
    m0 = re.search(r'<img[^>]*alt="([^"]+)"', html)
    alt0 = re.sub(r"\s*(썸네일|이미지|대표\s*이미지|카드\s*\d*)$", "", m0.group(1).strip()) if m0 else ""
    if alt0 and len(alt0.split()) <= 4 and len(alt0) <= 16 and body.count(alt0.replace(" ", "")) >= 1:
        return alt0
    title = re.sub(r"\d{1,2}월\s*", "", meta.get("title", ""))
    words = [w.strip(",…·|?!.\"'()[]") for w in title.split()]
    words = [w for w in words if w]
    best, best_sc = "", 0
    for n in (3, 2):
        for i in range(0, min(len(words) - n + 1, 6)):
            ws = words[i:i + n]
            if any(re.match(r"^\d[\d,.]*(가지|만|억|천|원|%|개|번|분|시간|일|월|배|명|위|년)?$", w) or w in ("원", "후", "전", "때", "월", "만에", "절반", "번갈아", "입", "보면", "내가", "나는", "이유", "방법", "설정", "정리") for w in (ws[0], ws[-1])):
                continue
            cand = " ".join(ws)
            c = body.count(cand.replace(" ", ""))
            sc = c * (1.3 if n == 3 else 1.0) - i * 0.3
            if c >= 2 and sc > best_sc:
                best, best_sc = cand, sc
    if best:
        return best
    m = re.search(r'<img[^>]*alt="([^"]+)"', html)
    alt = re.sub(r"\s*(썸네일|이미지|카드\s*\d*)$", "", m.group(1).strip()) if m else ""
    if alt and len(alt.split()) <= 4:
        return alt
    return " ".join(words[:2])


def sentences(html):
    return [s for s in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", html, flags=re.S)
            if plain(s) and "<img" not in s and "font-size:12px" not in s]


def intro_sentences(html):
    """첫 h2 앞 도입부(이미지 제외)의 문장들 — <p> 형식과 <br> 형식 모두 처리."""
    head = re.split(r"<h2\b", html, maxsplit=1, flags=re.I)[0]
    head = re.sub(r"<h1[^>]*>.*?</h1>", " ", head, flags=re.S | re.I)
    txt = plain(re.sub(r"<img\b[^>]*>", " ", head))
    if not txt:
        txt = plain(html)[:400]
    return [x.strip() for x in re.findall(r"[^.?!]+[.?!]?", txt) if x.strip()]


def siblings_titles(folder: Path, blog: str, self_id: str = ""):
    """같은 블로그에 이미 발행된 글 제목들(자기 자신·수정 대상 원본 제외)."""
    out = []
    for p in (ROOT / "posts" / "published").glob("*/post.json"):
        if p.parent.resolve() == folder.resolve():
            continue
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if self_id and m.get("blogger_id") == self_id:
            continue
        if str(m.get("blog", "main")) == blog:
            out.append(m.get("title", ""))
    return out


def similar(a, b):
    """제목 단어 겹침 비율(0~1)."""
    wa, wb = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", a)), set(re.findall(r"[가-힣A-Za-z0-9]{2,}", b))
    return len(wa & wb) / max(1, min(len(wa), len(wb)))


def score(folder: Path):
    meta = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    html = (folder / "post.html").read_text(encoding="utf-8")
    title = meta.get("title", "")
    kw = guess_kw(meta, html)
    k = kw.replace(" ", "")
    text = plain(html)
    body_chars = len(re.sub(r"\s", "", text))
    sents = sentences(html)
    first = " ".join(intro_sentences(html)[:2])
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html, flags=re.S)
    imgs = re.findall(r"<img\b[^>]*>", html, flags=re.I)
    toks = [t[:2] for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", kw)]
    if len(toks) < 2:
        toks = [k]
    has_kw = lambda t: all(x in t.replace(" ", "") for x in toks)
    paras = [plain(x) for x in re.findall(r"<(?:p|li|h2|h3|td)[^>]*>(.*?)</(?:p|li|h2|h3|td)>", html, flags=re.S)]
    kw_count = sum(1 for x in paras if has_kw(x))
    blog = str(meta.get("blog", "main"))

    checks = []  # (항목, 배점, 통과여부, 고칠 점)
    add = lambda name, pts, ok, fix: checks.append((name, pts, bool(ok), fix))

    # ── 제목 (25)
    add("제목 길이 25~60자", 5, 25 <= len(title) <= 60, f"지금 {len(title)}자")
    add("제목 앞 15자 안에 메인 키워드", 10, k[:4] in title.replace(" ", "")[:17], f"'{kw}'를 제목 맨 앞으로")
    add("제목에 숫자", 5, re.search(r"\d", title), "구체적인 숫자 1개 넣기")
    dup = [t for t in siblings_titles(folder, blog, str(meta.get("update_of") or meta.get("blogger_id") or "")) if similar(title, t) >= 0.7]
    add("같은 블로그에 비슷한 제목 없음(중복·자기잠식 방지)", 5, not dup, f"비슷한 글: {dup[:2]}")

    # ── 첫 문단 = 검색 미리보기 (15)
    add("첫 2문장 안에 메인 키워드(검색 미리보기)", 10, has_kw(first), f"첫 문장에 '{kw}'를 넣고 핵심 답을 바로 말하기")
    add("첫 문장이 인사·잡담으로 시작하지 않음", 5,
        not re.match(r"^(오늘은|안녕하세요|요즘|여러분)", (intro_sentences(html) or [""])[0]), "첫 문장에서 바로 답을 말하기")

    # ── 본문 구조 (35)
    add("본문 1,500자 이상(공백 제외)", 10, body_chars >= 1500, f"지금 {body_chars}자")
    add("키워드 들어간 문단 3~12개(과다 반복 아님)", 5, 3 <= kw_count <= 12, f"지금 {kw_count}개 — 소제목·문단에 자연스럽게 더 넣기" if kw_count < 3 else f"지금 {kw_count}개 — 반복 줄이기")
    add("소제목(h2) 3개 이상", 8, len(h2s) >= 3, f"지금 {len(h2s)}개")
    add("소제목 중 1개 이상에 키워드", 5, any(has_kw(plain(h)) for h in h2s), f"h2 하나에 '{kw}' 넣기")
    add("표 또는 목록 1개 이상", 4, re.search(r"<(table|ol|ul)\b", html), "요점 표/목록 추가")
    add("본문에 h1 없음(블로거 제목과 중복)", 3, "<h1" not in html.lower(), "본문 h1 삭제(--fix 자동)")

    # ── 이미지 (15)
    add("첫 요소가 대표이미지", 5, re.search(r"^\s*(<p[^>]*>\s*)?<img", re.sub(r"<h1.*?</h1>\s*(<p><br></p>)?", "", html, flags=re.S | re.I)), "본문 맨 앞에 thumb.jpg")
    add("이미지 3장 이상", 5, len(imgs) >= 3, f"지금 {len(imgs)}장")
    add("모든 이미지에 키워드 alt", 5, imgs and all(re.search(r'alt="[^"]*' + re.escape(kw[:2]), i) for i in imgs), "alt에 키워드(--fix 자동)")

    # ── 신뢰·정책 (10)
    add("라벨 있음", 3, meta.get("labels"), "라벨 1개 지정")
    add("금지어·외부 링크 없음", 4, not any(b in text for b in BANNED) and "<a " not in html,
        f"금지어/링크: {[b for b in BANNED if b in text] + (['<a>'] if '<a ' in html else [])}")
    endings = [s for s in sents if not plain(s).rstrip().endswith(("다.", "?", "다!"))]
    tt = [t[:2] for t in re.findall(r"[가-힣A-Za-z]{2,}", title)]
    hit = sum(1 for t in tt if t in text.replace(" ", ""))
    add("제목 핵심 단어가 본문에 등장(제목-본문 일치)", 3, not tt or hit / len(tt) >= 0.5, f"제목 단어 {hit}/{len(tt)}개만 본문에 있음")

    # ── 애드센스 '찍어낸 글' 신호 (어기면 항목당 -20 → 발행 보류)
    pen = adsense_penalties(title, html, siblings_recent(folder, blog))
    for name, fix in pen:
        checks.append((name, -20, False, fix))
    total = sum(p for _, p, ok, _ in checks if ok and p > 0) - 20 * len(pen)
    return total, checks, kw


TITLE_PERSONA = re.compile(r"(셀러|사장|아빠|엄마|가장|두 아이|부부가|내가|제가)")
TITLE_TEMPLATE = re.compile(r"(하던|했던|던) ?[가-힣 ]{0,12}(내가|아빠가|셀러가|사장이|가장이|부모가|부부가|아이가)|바꾼 (순서|이유|습관|방법|것|설정|\d)")
BOILER = [re.compile(r"이 글은 [^.]{2,160}?(위해|위한) (쓴 )?글(이다|입니다)"),
          re.compile(r"(바로 따라 할 수 있도록 핵심부터 정리|헷갈리기 쉬운 부분을 먼저 짚고 순서대로 정리|꼭 알아야 할 기준과 순서 중심으로 정리)"),
          re.compile(r"(나는|저는) (생활용품 )?온라인 쇼핑몰을 운영하(는|며|면서)[^.]{0,40}?(아빠|가장|사업자)(다|이다|입니다)\.")]


def siblings_recent(folder: Path, blog: str, n: int = 6):
    """같은 블로그 최근 글(폴더 이름=시간순) n개의 (제목, 첫 문장)."""
    rows = []
    for p in sorted((ROOT / "posts" / "published").glob("*/post.json")):
        if p.parent.resolve() == folder.resolve() or "seofix" in p.parent.name:
            continue
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(m.get("blog", "main")) != blog or m.get("update_of"):
            continue
        h = (p.parent / "post.html")
        first = (intro_sentences(h.read_text(encoding="utf-8")) or [""])[0] if h.exists() else ""
        rows.append((m.get("title", ""), first))
    return rows[-n:]


def adsense_penalties(title, html, recent):
    """애드센스 '저품질·대량 생산' 신호: 틀에 박힌 제목·도입·자기소개 문장, 최근 글과 같은 제목 꼬리/첫 문장 틀."""
    out = []
    if TITLE_PERSONA.search(title) or TITLE_TEMPLATE.search(title):
        out.append(("제목에 화자·'~하던 내가 바꾼' 틀 없음", "제목은 독자가 검색하는 말 + 이 글이 주는 답으로만 쓴다(셀러·사장·아빠·내가·바꾼 순서/이유 금지)"))
    txt = plain(html)
    hits = [b.search(txt).group(0)[:40] for b in BOILER if b.search(txt)]
    if hits:
        out.append(("틀에 박힌 도입·자기소개 문장 없음", f"이 문장을 글 내용에 맞는 내 문장으로 바꾸거나 지운다: {hits}"))
    tail = lambda t: re.sub(r"[^가-힣A-Za-z0-9]", "", (re.findall(r"[가-힣A-Za-z0-9]+", t) or [""])[-1])
    same = [t for t, _ in recent[-4:] if t and tail(t) == tail(title)]
    if len(same) >= 2:
        out.append(("최근 글과 같은 제목 끝맺음 반복 없음", f"최근 제목 {len(same)}개가 '…{tail(title)}'로 끝난다 — 질문형·비교형·기준형 등 다른 형태로"))
    lead = lambda t: re.sub(r"\s", "", t)[:8]
    first = (intro_sentences(html) or [""])[0]
    samef = [f for _, f in recent[-4:] if f and lead(f) == lead(first)]
    if samef:
        out.append(("최근 글과 같은 첫 문장 시작 없음", f"첫 문장이 최근 글과 똑같이 '{lead(first)}…'로 시작한다 — 다르게 시작"))
    ai = sum(txt.count(w) for w in AI_WORDS)
    if ai > 3:
        found = [f"{w}×{txt.count(w)}" for w in AI_WORDS if txt.count(w)]
        out.append(("AI 말투 3회 이하", f"AI가 쓴 글처럼 보이는 표현 {ai}회: {found} — 행동·사실로 다시 쓴다(예: '~하는 것이 좋다'→'~하면 된다'/'나는 ~했다')"))
    return out


AI_WORDS = ["것이 좋다", "것이 좋습니다", "중요하다", "중요합니다", "핵심은", "정리하면", "무엇보다", "이처럼", "결론적으로",
            "다양한", "효과적", "꼼꼼히", "첫째", "둘째", "셋째", "마무리하며", "알아보자", "알아보겠", "살펴보자", "살펴보겠",
            "도움이 될 것", "꼭 기억"]


def _josa(word, a, b):
    """받침 있으면 a, 없으면 b (을/를, 은/는)."""
    ch = word.strip()[-1:] if word.strip() else "가"
    if "가" <= ch <= "힣":
        return a if (ord(ch) - 0xAC00) % 28 else b
    return a if ch.isdigit() and ch in "013678" else b


def _style(html):
    sents = [x.strip() for x in re.findall(r"[^.?!]+[.?!]", plain(html))]
    yo = sum(1 for x in sents if re.search(r"(요|죠)[.?!]$", x))
    sb = sum(1 for x in sents if re.search(r"(니다|니까)[.?!]$", x))
    da = sum(1 for x in sents if x.endswith("다.")) - sb
    return "yo" if yo >= max(sb, da) and yo > 0 else "sb" if sb > da else "da"


# 경험을 주장하지 않는 중립 리드(키워드 + 이 글이 답하는 것)
LEADS = {
    "da": ["{k}{j} 꼭 알아야 할 기준과 순서 중심으로 정리한다.",
           "{k}에 대해 바로 따라 할 수 있도록 핵심부터 정리한다.",
           "{k}, 헷갈리기 쉬운 부분을 먼저 짚고 순서대로 정리한다."],
    "sb": ["{k}{j} 꼭 알아야 할 기준과 순서 중심으로 정리했습니다.",
           "{k}에 대해 바로 따라 할 수 있도록 핵심부터 정리했습니다.",
           "{k}, 헷갈리기 쉬운 부분을 먼저 짚고 순서대로 정리했습니다."],
    "yo": ["{k}{j} 꼭 알아야 할 기준과 순서 중심으로 정리했어요.",
           "{k}에 대해 바로 따라 할 수 있도록 핵심부터 정리했어요.",
           "{k}, 헷갈리기 쉬운 부분을 먼저 짚고 순서대로 정리했어요."],
}
SWAP = {"무조건": "반드시", "긴급": "급한", "자주 묻는 질문": "궁금한 점", "FAQ": "궁금한 점"}


def autofix(folder: Path, kw: str):
    """기계적으로 고칠 수 있는 항목을 모두 고친다(내용·숫자는 새로 만들지 않음)."""
    f = folder / "post.html"
    meta = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    html = f.read_text(encoding="utf-8")
    title = meta.get("title", "")
    toks = [t[:2] for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", kw)]
    if len(toks) < 2:
        toks = [kw.replace(" ", "")]
    has_kw = lambda t: all(x in plain(t).replace(" ", "") for x in toks)

    # 1) 본문 h1 삭제, 링크 문단 삭제·남은 링크 풀기, 쿠팡 문장 삭제, 금지어 순화
    html = re.sub(r"<h1[^>]*>.*?</h1>\s*(<p><br\s*/?></p>)?", "", html, flags=re.S | re.I)
    html = re.sub(r"<p[^>]*>[^<]*(함께 읽으면|같이 읽으면|관련 글)[^<]*<a .*?</p>\s*(<p><br\s*/?></p>)?", "", html, flags=re.S)
    html = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", html, flags=re.S | re.I)
    html = re.sub(r"<p[^>]*>[^<]*쿠팡[^<]*</p>", "", html)
    for a, b in SWAP.items():
        html = re.sub(r"(>[^<]*?)" + re.escape(a), lambda m: m.group(1) + b, html)

    # 2) 도입에 키워드가 없으면 자동 문장 삽입 안 함(틀 문장은 애드센스 저품질 신호) — 쓰는 사람이 직접 고친다
    # 3) 키워드 든 문단 3개 이상 + h2에 키워드 — 뒤쪽 h2부터 키워드 붙이기
    def kw_paras(h):
        return sum(1 for x in re.findall(r"<(?:p|li|h2|h3|td)[^>]*>(.*?)</(?:p|li|h2|h3|td)>", h, flags=re.S) if has_kw(x))
    h2s = re.findall(r"(<h2[^>]*>)(.*?)(</h2>)", html, flags=re.S)
    order = [h for h in h2s[1:] if not has_kw(h[1]) and not re.search(r"마무리|정리하며|맺으며", h[1])][:1] + ([h2s[0]] if h2s and not has_kw(h2s[0][1]) else [])
    need_h2 = not any(has_kw(h[1]) for h in h2s)
    for o, t, c in order:
        if not need_h2 and kw_paras(html) >= 3:
            break
        txt = plain(t)
        new = f"{kw}, {txt}" if not txt.startswith(kw) else txt
        html = html.replace(o + t + c, o + new + c, 1)
        need_h2 = False
        if kw_paras(html) >= 3 and len(order) and o + new + c in html and need_h2 is False and kw_paras(html) >= 3:
            break

    # 4) 이미지 alt
    def alt(m):
        tag = m.group(0)
        if re.search(r'alt="[^"]*' + re.escape(kw[:2]), tag):
            return tag
        tag = re.sub(r'\salt="[^"]*"', "", tag)
        return tag.replace("<img", f'<img alt="{kw}"', 1)
    html = re.sub(r"<img\b[^>]*>", alt, html, flags=re.I)
    f.write_text(html, encoding="utf-8")


def report(folder, total, checks):
    lines = [f"[{'통과' if total >= PASS else '보류'}] {total}/100  {folder.name}"]
    for name, pts, ok, fix in checks:
        if not ok:
            lines.append(f"   -{abs(pts):>2}  {name} → {fix}")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--all":
        base = Path(args[1] if len(args) > 1 and not args[1].startswith("--") else ROOT / "posts" / "published")
        rows = []
        dirs = [d for d in sorted(base.iterdir()) if (d / "post.json").exists()]
        metas = {d: json.loads((d / "post.json").read_text(encoding="utf-8")) for d in dirs}
        latest = {}  # 글 ID별 가장 최근 버전 폴더만 점검(폴더 이름이 시간순)
        for d in dirs:
            m = metas[d]
            gid = m.get("update_of") or m.get("blogger_id") or d.name
            rank = (1 if m.get("update_of") else 0, d.name)  # 수정본 우선, 그다음 최신
            if gid not in latest or rank > latest[gid][0]:
                latest[gid] = (rank, d)
        latest = {k: v[1] for k, v in latest.items()}
        keep = set(latest.values())
        for d in dirs:
            m = metas[d]
            if d not in keep or m.get("draft") or m.get("status") == "DRAFT":
                continue
            if (d / "post.html").exists():
                t, c, _ = score(d)
                rows.append((t, d, c))
        worst = int(args[args.index("--worst") + 1]) if "--worst" in args else 0
        if worst:  # 보정 대상: 애드센스용 새 블로그 글 먼저, 그다음 점수 낮은 순
            todo = [r for r in rows if r[0] < PASS]
            todo.sort(key=lambda r: (0 if metas[r[1]].get("series") else 1, r[0]))
            for t, d, c in todo[:worst]:
                print(report(d, t, c))
            print(f"\n남은 90점 미만 글: {len(todo)}개")
            return
        for t, d, c in sorted(rows, key=lambda r: r[0]):
            print(report(d, t, c))
        ok = sum(1 for t, *_ in rows if t >= PASS)
        print(f"\n전체 {len(rows)}개 중 90점 이상 {ok}개, 평균 {sum(t for t, *_ in rows) / max(1, len(rows)):.1f}점")
        return
    folder = Path(args[0])
    total, checks, kw = score(folder)
    if total < PASS and "--fix" in args:
        autofix(folder, kw)
        total, checks, kw = score(folder)
    print(report(folder, total, checks))
    sys.exit(0 if total >= PASS else 1)


if __name__ == "__main__":
    main()
