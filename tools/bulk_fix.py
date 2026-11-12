"""애드센스 대비 기존 글 일괄 정리 (tools/bulk_fix.json 을 push하면 GitHub Actions가 실행).
- mode "dry": 바꿀 내용만 posts/audit/bulk_fix_report.md 에 기록(블로거는 그대로)
- mode "apply": 실제로 블로거에 반영
작업: titles(글ID→새 제목), delete(글ID → 휴지통), draft(글ID → 비공개 초안으로 되돌림),
      clean=true 이면 모든 공개·예약 글 본문에서 틀에 박힌 문장·본문 링크를 정리한다."""
import json, os, re, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "tools" / "bulk_fix.json"
API = "https://www.googleapis.com/blogger/v3"
c = lambda n: os.environ.get(n, "").strip()

SEOFIX = re.compile(r"(?:(?<=>)|(?<=\.)|(?<=\. ))\s*([^<>.]{0,60}?)(?:에 대해 바로 따라 할 수 있도록 핵심부터 정리한다|, ?헷갈리기 쉬운 부분을 먼저 짚고 순서대로 정리(?:한다|했다|했습니다|합니다))\.")
OPENER = re.compile(r"이 글은 ([^<>]{4,160}?)(을|를) 위해 쓴 글(이다|입니다)\.")
PERSONA = re.compile(r"(?:(?<=>)|(?<=\. ))\s*(?:나는|저는) (?:생활용품 )?온라인 쇼핑몰을 운영하(?:는|며|면서)[^<>.]{0,40}?(?:아빠|가장|사업자)(?:다|이다|입니다)\.")


DETPL = re.compile(r"(?:(?<=>)|(?<=\.)|(?<=\n))[ \t]*[^<>.\n]{0,220}?(?:"
                   r"꼭 알아야 할 기준과 순서 중심으로 정리(?:한다|했다|했습니다|합니다)"
                   r"|, ?핵심부터 차례대로 정리했(?:다|습니다)"
                   r"|, ?실제로 해 볼 수 있는 순서로 담았(?:다|습니다)"
                   r"|, ?먼저 알아야 할 기준부터 적었(?:다|습니다)"
                   r"|에 대해 바로 따라 할 수 있도록 핵심부터 정리(?:했습니다|한다|했다)"
                   r"|라면 끝까지 읽어 볼 만하다|라면 끝까지 읽어 보시길 바랍니다"
                   r"|라면 아래 순서대로 확인하면 된다|라면 아래 순서대로 확인해 보시면 됩니다"
                   r"|(?:에게|께) 필요한 기준과 순서를 담았(?:다|습니다))\.")
PERS2 = re.compile(r"(?:나는 |저는 )?온라인 쇼핑몰(?:을 (?:혼자 )?운영하(?:며|면서|는)|에서 생활용품을 팔며)[^<>.,]{0,40}?(?:가장|아빠)(?:으로서|로서|인)\s*")


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
            scope = cfg.get("scope")  # 예: "itdigitaldream" — 아래 두 작업은 이 블로그에만 적용
            in_scope = bool(scope) and (scope == "*" or scope in b.get("url", ""))
            if in_scope and cfg.get("dedupe"):  # 같은 제목 글은 1개만 남기고 삭제(keep 목록의 글ID 우선)
                keep, groups = set(cfg.get("keep", [])), {}
                for p in sorted(posts, key=lambda x: x.get("published", "")):
                    groups.setdefault(re.sub(r"\s+", "", p.get("title", "")), []).append(p)
                for g in groups.values():
                    if len(g) > 1:
                        k = next((x for x in g if x["id"] in keep), g[0])
                        delete |= {x["id"] for x in g if x["id"] != k["id"]}
            if in_scope and cfg.get("delete_drafts"):  # 비공개(초안) 글 전체 삭제
                import time
                page = None
                while True:
                    q = {"maxResults": 100, "status": "draft", "fetchBodies": "false", "view": "ADMIN"}
                    if page:
                        q["pageToken"] = page
                    j = requests.get(f"{API}/blogs/{b['id']}/posts", headers=H, params=q, timeout=60).json()
                    for d in j.get("items", []):
                        rep.append(f"- 🗑 초안 삭제: {d.get('title')}")
                        if mode == "apply":
                            try:
                                r = requests.delete(f"{API}/blogs/{b['id']}/posts/{d['id']}", headers=H, timeout=60)
                                r.raise_for_status()
                                time.sleep(0.4)
                            except Exception as e:
                                cnt["실패"] += 1
                                rep.append(f"  - ⚠️ 실패: {e}")
                                continue
                        cnt["삭제"] += 1
                    page = j.get("nextPageToken")
                    if not page or mode == "apply" and not j.get("items"):
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
                    if cfg.get("detpl"):  # 틀에 박힌 도입 문장 삭제(+ first 에 적힌 새 첫 문장으로 교체), 반복 자기소개 구절 삭제
                        cur = body.get("content", p.get("content", ""))
                        head, tail = cur[:3000], cur[3000:]
                        nf, st = cfg.get("first", {}).get(pid), {"done": False}
                        def rm(m):
                            log.append("틀 문장 삭제: " + plain(m.group(0))[:70])
                            if nf and not st["done"]:
                                st["done"] = True
                                log.append("새 첫 문장: " + nf[:60])
                                return (" " if m.group(0)[:1].isspace() and m.start() and head[m.start() - 1] != ">" else "") + nf
                            return ""
                        head2 = DETPL.sub(rm, head)
                        if nf and not st["done"]:
                            log.append("⚠️ 새 첫 문장 넣을 자리 못 찾음")
                        h3 = PERS2.sub("", head2)
                        if h3 != head2:
                            log.append("반복 자기소개 구절 삭제")
                        h3 = re.sub(r"<p>\s*</p>\n?", "", h3)
                        if h3 != head:
                            body["content"] = h3 + tail
                    for o, n in cfg.get("replace", {}).get(pid, []):  # 문장 단위 본문 교체
                        cur = body.get("content", p.get("content", ""))
                        if o in cur:
                            body["content"] = cur.replace(o, n, 1)
                            log.append(f"문장 교체: {o[:30]}… → {n[:40]}")
                        else:
                            log.append(f"⚠️ 못 찾음(문장): {o[:40]}")
                    for o, n in cfg.get("h2", {}).get(pid, {}).items():  # 소제목 교체
                        cur = body.get("content", p.get("content", ""))
                        new_c, k = re.subn(r"(<h2[^>]*>\s*)" + re.escape(o) + r"(\s*(?:<br[^>]*>)?\s*</h2>)", lambda m: m.group(1) + n + m.group(2), cur, count=1)
                        if k:
                            body["content"] = new_c
                            log.append(f"소제목 교체: {o} → {n}")
                        else:
                            log.append(f"⚠️ 못 찾음(소제목): {o}")
                    if cfg.get("h2_unprefix"):  # 검사 도구가 기계적으로 붙인 '키워드, 소제목' 꼴을 원래 소제목으로
                        cur = body.get("content", p.get("content", ""))
                        tt = p["title"].replace(" ", "")
                        H2P = r"(<h2[^>]*>\s*)([^<,]{2,26}), ([^<]{6,80}?)(\s*(?:<br[^>]*>)?\s*</h2>)"
                        pres = [m.group(2).strip() for m in re.finditer(H2P, cur)]
                        def unp(m):
                            pre, rest = m.group(2), m.group(3)
                            toks = [t[:2] for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", pre)]
                            # 같은 글에서 같은 머리말이 2번 이상 붙은 경우만(자연스러운 '가, 나' 소제목은 건드리지 않음)
                            if pres.count(pre.strip()) >= 2 and toks and all(t in tt for t in toks) and len(rest.strip()) >= 6:
                                log.append(f"소제목 앞 키워드 떼기: {pre}, {rest.strip()[:30]}")
                                return m.group(1) + rest.strip()[:1].upper() + rest.strip()[1:] + m.group(4)
                            return m.group(0)
                        new_c = re.sub(H2P, unp, cur)
                        if new_c != cur:
                            body["content"] = new_c
                    if cfg.get("author"):
                        import author
                        key = next((v for k, v in author.BY_URL.items() if f"//{k}." in b.get("url", "")), "main")
                        cur = body.get("content", p.get("content", ""))
                        new = author.add(cur, key)
                        if new != cur:
                            body["content"] = new
                            log.append(f"글쓴이 상자 추가({key})")
                    if not body:
                        if log:
                            rep.append(f"- {p['title']}")
                            rep += [f"  - {x}" for x in log]
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
