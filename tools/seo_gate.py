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
BANNED = ["충격", "긴급", "무조건", "100%", "쿠팡", "자주 묻는 질문", "FAQ"]


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def guess_kw(meta, html):
    if meta.get("kw"):
        return meta["kw"]
    m = re.search(r'<img[^>]*alt="([^"]+)"', html)
    if m:
        return m.group(1)
    return " ".join(meta.get("title", "").split()[:2])


def sentences(html):
    return [s for s in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", html, flags=re.S)
            if plain(s) and "<img" not in s and "font-size:12px" not in s]


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
    first = plain(" ".join(sents[:2]))
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html, flags=re.S)
    imgs = re.findall(r"<img\b[^>]*>", html, flags=re.I)
    toks = [t[:2] for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", kw)] or [k[:2]]
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
        not re.match(r"^(오늘은|안녕하세요|요즘|여러분)", plain(sents[0]) if sents else ""), "첫 문장에서 바로 답을 말하기")

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
    add("문장 '~다.' 종결 95% 이상", 3, not sents or len(endings) / len(sents) <= 0.05, f"어긋난 문장 {len(endings)}개")

    total = sum(p for _, p, ok, _ in checks if ok)
    return total, checks, kw


def autofix(folder: Path, kw: str):
    f = folder / "post.html"
    html = f.read_text(encoding="utf-8")
    html = re.sub(r"<h1[^>]*>.*?</h1>\s*(<p><br\s*/?></p>)?", "", html, flags=re.S | re.I)

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
            lines.append(f"   -{pts:>2}  {name} → {fix}")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--all":
        base = Path(args[1] if len(args) > 1 and not args[1].startswith("--") else ROOT / "posts" / "published")
        rows = []
        dirs = [d for d in sorted(base.iterdir()) if (d / "post.json").exists()]
        metas = {d: json.loads((d / "post.json").read_text(encoding="utf-8")) for d in dirs}
        replaced = {m.get("update_of") for m in metas.values() if m.get("update_of")}
        for d in dirs:
            m = metas[d]
            if not m.get("update_of") and m.get("blogger_id") in replaced:
                continue  # 이미 보정된 원본은 건너뜀
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
