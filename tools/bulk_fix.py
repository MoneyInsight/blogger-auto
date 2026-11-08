"""애드센스 대비 기존 글 일괄 정리 (tools/bulk_fix.json 을 push하면 GitHub Actions가 실행).
- mode "dry": 바꿀 내용만 posts/audit/bulk_fix_report.md 에 기록(블로거는 그대로)
- mode "apply": 실제로 블로거에 반영
작업: titles(글ID→새 제목), delete(글ID → 휴지통), draft(글ID → 비공개 초안으로 되돌림),
      clean=true 이면 모든 공개·예약 글 본문에서 틀에 박힌 문장·본문 링크를 정리한다."""
import json, os, re, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "tools" / "bulk_fix.json"
API = "https://www.googleapis.com/blogger/v3"
c = lambda n: os.environ.get(n, "").strip()

SEOFIX = re.compile(r"(?:(?<=>)|(?<=\.)|(?<=\. ))\s*([^<>.]{0,60}?)(?:에 대해 바로 따라 할 수 있도록 핵심부터 정리한다|, ?헷갈리기 쉬운 부분을 먼저 짚고 순서대로 정리(?:한다|했다|했습니다|합니다))\.")
OPENER = re.compile(r"이 글은 ([^<>]{4,160}?)(을|를) 위해 쓴 글(이다|입니다)\.")
PERSONA = re.compile(r"(?:(?<=>)|(?<=\. ))\s*(?:나는|저는) (?:생활용품 )?온라인 쇼핑몰을 운영하(?:는|며|면서)[^<>.]{0,40}?(?:아빠|가장|사업자)(?:다|이다|입니다)\.")


def has_batchim(s):
    ch = s.strip()[-1]
    return 0xAC00 <= ord(ch) <= 0xD7A3 and (ord(ch) - 0xAC00) % 28 != 0


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


def clean(html, title, seed):
    log = []
    def sf(m):
        kw = m.group(1).strip().rstrip(",")
        after = plain(html[m.end():m.end() + 600])[:160]
        if not kw or kw.replace(" ", "") in after.replace(" ", ""):
            log.append("삭제(틀 문장): " + plain(m.group(0)))
            return ""
        polite = "습니다" in m.group(0) or "합니다" in m.group(0)
        v = (seed // 3) % 3
        tail = [", 핵심부터 차례대로 정리했습니다.", ", 먼저 알아야 할 기준부터 적었습니다.", ", 실제로 해 볼 수 있는 순서로 담았습니다."][v] if polite else \
               [", 핵심부터 차례대로 정리했다.", ", 먼저 알아야 할 기준부터 적었다.", ", 실제로 해 볼 수 있는 순서로 담았다."][v]
        new = " " + kw + tail
        log.append(f"바꿈(틀 문장): {plain(m.group(0))} → {new.strip()}")
        return new
    html = SEOFIX.sub(sf, html)
    for m in PERSONA.finditer(html):
        log.append("삭제(반복 자기소개): " + plain(m.group(0)))
    html = PERSONA.sub("", html)

    def op(m):
        x, polite = m.group(1), m.group(3) == "입니다"
        v = seed % 3
        if polite:
            new = [x + ("이라면" if has_batchim(x) else "라면") + " 끝까지 읽어 보시길 바랍니다.",
                   x + "께 필요한 기준과 순서를 담았습니다.",
                   x + ("이라면" if has_batchim(x) else "라면") + " 아래 순서대로 확인해 보시면 됩니다."][v]
        else:
            new = [x + ("이라면" if has_batchim(x) else "라면") + " 끝까지 읽어 볼 만하다.",
                   x + "에게 필요한 기준과 순서를 담았다.",
                   x + ("이라면" if has_batchim(x) else "라면") + " 아래 순서대로 확인하면 된다."][v]
        log.append(f"바꿈(도입 문장): {m.group(0)} → {new}")
        return new
    html = OPENER.sub(op, html, count=1)
    # 본문 맨 앞에 제목을 글자로 한 번 더 쓴 줄 삭제
    t = re.escape(title.strip())
    m = re.search(r"<(p|h1|div)[^>]*>\s*(?:<[^>]+>\s*)*" + t + r"\s*(?:<[^>]+>\s*)*</\1>", html[:3000])
    if m:
        log.append("삭제(본문 속 제목 중복)")
        html = html.replace(m.group(0), "", 1)
    html2 = re.sub(r"<h1[^>]*>.*?</h1>", "", html, flags=re.S)
    if html2 != html:
        log.append("삭제(h1)")
        html = html2
    # 링크: '함께 읽으면' 묶음 삭제, 나머지 링크는 글자만 남김
    html2 = re.sub(r"<(p|div|h[2-4])[^>]*>[^<]*(?:함께 읽으면|같이 보면 좋은|관련 글)[\s\S]*?</\1>(\s*<(ul|ol)[^>]*>[\s\S]*?</\3>)?", "", html)
    if html2 != html:
        log.append("삭제(함께 읽으면 좋은 글 묶음)")
        html = html2
    n = len(re.findall(r"<a\s", html))
    if n:
        log.append(f"링크 {n}개 → 글자만 남김")
        html = re.sub(r"<a\s[^>]*>(.*?)</a>", r"\1", html, flags=re.S)
    html = re.sub(r"<p>\s*</p>", "", html)
    return html, log


def token(refresh):
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": c("BLOGGER_CLIENT_ID"), "client_secret": c("BLOGGER_CLIENT_SECRET"),
        "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    mode = cfg.get("mode", "dry")
    if mode == "done":
        print("이미 처리됨")
        return
    titles, delete, draft = cfg.get("titles", {}), set(cfg.get("delete", [])), set(cfg.get("draft", []))
    rep = [f"# 기존 글 일괄 정리 — mode={mode}\n"]
    cnt = {"제목": 0, "본문": 0, "삭제": 0, "비공개": 0, "실패": 0}
    for acct, ref in (("main", c("BLOGGER_REFRESH_TOKEN")), ("it", c("IT_REFRESH_TOKEN"))):
        if not ref:
            continue
        H = {"Authorization": f"Bearer {token(ref)}", "Content-Type": "application/json"}
        for b in requests.get(f"{API}/users/self/blogs", headers=H, timeout=30).json().get("items", []):
            rep.append(f"\n## {b['name']}\n")
            posts = []
            for status in ("live", "scheduled"):
                page = None
                while True:
                    p = {"maxResults": 100, "status": status, "fetchBodies": "true", "view": "ADMIN"}
                    if page:
                        p["pageToken"] = page
                    j = requests.get(f"{API}/blogs/{b['id']}/posts", headers=H, params=p, timeout=60).json()
                    posts += j.get("items", [])
                    page = j.get("nextPageToken")
                    if not page:
                        break
            for i, p in enumerate(posts):
                pid = p["id"]
                try:
                    if pid in delete:
                        rep.append(f"- 🗑 휴지통: {p['title']}")
                        if mode == "apply":
                            r = requests.delete(f"{API}/blogs/{b['id']}/posts/{pid}", headers=H, timeout=60)
                            r.raise_for_status()
                        cnt["삭제"] += 1
                        continue
                    if pid in draft:
                        rep.append(f"- 🔒 비공개 초안으로: {p['title']}")
                        if mode == "apply":
                            r = requests.post(f"{API}/blogs/{b['id']}/posts/{pid}/revert", headers=H, timeout=60)
                            r.raise_for_status()
                        cnt["비공개"] += 1
                        continue
                    body = {}
                    nt = titles.get(pid)
                    if nt and nt != p["title"]:
                        body["title"] = nt
                    if cfg.get("clean"):
                        html, log = clean(p.get("content", ""), p["title"], int(pid[-4:]) + i)
                        if log:
                            body["content"] = html
                    else:
                        log = []
                    if not body:
                        continue
                    rep.append(f"- {p['title']}" + (f"\n  - 새 제목: {nt}" if "title" in body else ""))
                    rep += [f"  - {x}" for x in log]
                    if mode == "apply":
                        r = requests.patch(f"{API}/blogs/{b['id']}/posts/{pid}", headers=H, data=json.dumps(body), timeout=60)
                        r.raise_for_status()
                    cnt["제목"] += "title" in body
                    cnt["본문"] += "content" in body
                except Exception as e:
                    cnt["실패"] += 1
                    rep.append(f"- ⚠️ 실패 {p.get('title')}: {e}")
    rep.insert(1, f"요약: {cnt}\n")
    (ROOT / "posts" / "audit").mkdir(parents=True, exist_ok=True)
    (ROOT / "posts" / "audit" / f"bulk_fix_{mode}.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print(cnt)
    if mode == "apply":
        cfg["mode"] = "done"
        CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
