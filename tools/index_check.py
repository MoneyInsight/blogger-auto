"""
구글 '실제 색인 여부' 매일 점검 프로그램 (서치콘솔 URL 검사 API)
- GitHub Actions에서 하루 1번 실행됩니다 (.github/workflows/index-check.yml).
- 모든 블로그의 공개 글을 하나씩 구글에 물어봐서 '색인됨 / 안 됨 / 이유'를 기록합니다.
- 한 번 '색인됨'이 확인된 글은 7일 동안 다시 묻지 않습니다(한도 절약).

필요한 Secrets
  GSC_REFRESH_TOKEN     : 메인 구글 계정(durion0506)으로 tools/get_gsc_token.py 실행해서 받은 값
  GSC_IT_REFRESH_TOKEN  : (선택) IT 계정 블로그용 — 같은 프로그램을 IT 계정으로 한 번 더 실행
  BLOGGER_CLIENT_ID / BLOGGER_CLIENT_SECRET / BLOGGER_REFRESH_TOKEN / IT_REFRESH_TOKEN : 기존 값

결과
  posts/index_status.json : 글별 상태(다음 실행·SEO 보정 작업이 읽음)
  posts/index_status.md   : 블로그별 요약 + 색인 안 된 글 목록
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "posts" / "index_status.json"
REPORT = ROOT / "posts" / "index_status.md"
KST = timezone(timedelta(hours=9))

BLOGGER = "https://www.googleapis.com/blogger/v3"
WM = "https://www.googleapis.com/webmasters/v3"
INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"

RECHECK_INDEXED_DAYS = 7     # 색인 확인된 글은 7일 뒤에 다시 확인
MAX_CHECKS_PER_BLOG = 200    # 하루 블로그당 최대 검사 수(구글 한도 2,000의 10%)

STATE_KO = {
    "Submitted and indexed": "색인됨",
    "Indexed, not submitted in sitemap": "색인됨",
    "Crawled - currently not indexed": "크롤링됐지만 색인 안 됨(글 품질·중복 의심)",
    "Discovered - currently not indexed": "발견됐지만 아직 크롤링 전",
    "URL is unknown to Google": "구글이 아직 모름",
    "Duplicate without user-selected canonical": "중복 글로 판단됨",
    "Duplicate, Google chose different canonical than user": "중복 글로 판단됨",
    "Page with redirect": "리디렉션 페이지",
    "Excluded by ‘noindex’ tag": "noindex 태그로 제외",
    "Soft 404": "내용 부족(소프트 404)",
    "Not found (404)": "페이지 없음(404)",
}


def env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if "=" in v and v.split("=", 1)[0].strip().isupper():
        v = v.split("=", 1)[1]
    v = v.strip().strip('"').strip("'").strip()
    return v.split()[0] if v else ""


def access_token(refresh_token: str) -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("BLOGGER_CLIENT_ID"),
        "client_secret": env("BLOGGER_CLIENT_SECRET"),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def my_blogs(tok):
    r = requests.get(f"{BLOGGER}/users/self/blogs", headers=H(tok), timeout=30)
    r.raise_for_status()
    return [{"id": b["id"], "name": b.get("name", ""), "url": b["url"].replace("http://", "https://")}
            for b in r.json().get("items", [])]


def live_posts(tok, blog_id):
    """공개된 글 전부(페이지 넘김)."""
    out, page = [], None
    while True:
        params = {"status": "live", "fetchBodies": "false", "maxResults": 500,
                  "orderBy": "published", "fields": "nextPageToken,items(url,title,published)"}
        if page:
            params["pageToken"] = page
        r = requests.get(f"{BLOGGER}/blogs/{blog_id}/posts", params=params, headers=H(tok), timeout=60)
        r.raise_for_status()
        j = r.json()
        out += [{"url": p["url"].replace("http://", "https://"), "title": p.get("title", ""),
                 "published": p.get("published", "")} for p in j.get("items", [])]
        page = j.get("nextPageToken")
        if not page:
            return out


def gsc_sites(tok):
    r = requests.get(f"{WM}/sites", headers=H(tok), timeout=30)
    r.raise_for_status()
    return {s["siteUrl"]: s.get("permissionLevel", "") for s in r.json().get("siteEntry", [])}


def ensure_site(tok, sites, blog_url):
    """서치콘솔에 블로그가 없으면 추가(블로거 주인 계정이면 자동 소유 확인됨). 반환: (siteUrl, 문제 메시지)"""
    url = blog_url.rstrip("/") + "/"
    for cand in (url, url.replace("https://", "http://")):
        if cand in sites:
            if sites[cand] == "siteUnverifiedUser":
                return None, "서치콘솔 소유 확인 필요"
            return cand, ""
    r = requests.put(f"{WM}/sites/{quote(url, safe='')}", headers=H(tok), timeout=30)
    if r.status_code not in (200, 204):
        return None, f"서치콘솔 등록 실패 {r.status_code}"
    sites.update(gsc_sites(tok))
    if sites.get(url, "siteUnverifiedUser") == "siteUnverifiedUser":
        return None, "서치콘솔에 추가했지만 소유 확인 필요"
    requests.put(f"{WM}/sites/{quote(url, safe='')}/sitemaps/{quote(url + 'sitemap.xml', safe='')}",
                 headers=H(tok), timeout=30)
    return url, ""


def inspect(tok, site, url):
    for attempt in range(3):
        r = requests.post(INSPECT, headers=H(tok), json={"inspectionUrl": url, "siteUrl": site,
                                                           "languageCode": "ko"}, timeout=60)
        if r.status_code == 429:
            time.sleep(20 * (attempt + 1))
            continue
        if r.status_code != 200:
            return {"error": f"{r.status_code} {r.text[:120]}"}
        res = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
        return {"verdict": res.get("verdict", ""), "state": res.get("coverageState", ""),
                "crawled": res.get("lastCrawlTime", "")}
    return {"error": "429 한도 초과"}


def state_ko(rec):
    if "error" in rec:
        return "확인 실패: " + rec["error"]
    s = rec.get("state", "")
    if rec.get("verdict") == "PASS":
        return "색인됨"
    for en, ko in STATE_KO.items():
        if s.startswith(en.split(" (")[0]):
            return ko
    return s or rec.get("verdict", "알 수 없음")


def main():
    now = datetime.now(timezone.utc)
    stamp = now.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    data = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}

    pairs = [("메인 계정", env("BLOGGER_REFRESH_TOKEN"), env("GSC_REFRESH_TOKEN")),
             ("IT 계정", env("IT_REFRESH_TOKEN"), env("GSC_IT_REFRESH_TOKEN"))]
    summary, problems = [], []

    for acc, blog_rt, gsc_rt in pairs:
        if not blog_rt:
            continue
        if not gsc_rt:
            summary.append(f"| {acc} 블로그들 | - | - | - | 건너뜀: {'GSC_REFRESH_TOKEN' if acc == '메인 계정' else 'GSC_IT_REFRESH_TOKEN'} 없음 |")
            continue
        try:
            btok, gtok = access_token(blog_rt), access_token(gsc_rt)
            blogs, sites = my_blogs(btok), gsc_sites(gtok)
        except Exception as e:
            summary.append(f"| {acc} | - | - | - | 토큰/목록 실패: {e} |")
            continue

        for b in blogs:
            site, msg = ensure_site(gtok, sites, b["url"])
            try:
                posts = live_posts(btok, b["id"])
            except Exception as e:
                summary.append(f"| {b['name']} | - | - | - | 글 목록 실패: {e} |")
                continue
            if not site:
                summary.append(f"| {b['name']} | {len(posts)} | - | - | {msg} |")
                continue

            checked = 0
            for p in posts:
                old = data.get(p["url"], {})
                if old.get("verdict") == "PASS":
                    try:
                        last = datetime.fromisoformat(old["checked_utc"])
                        if now - last < timedelta(days=RECHECK_INDEXED_DAYS):
                            continue
                    except (KeyError, ValueError):
                        pass
                if checked >= MAX_CHECKS_PER_BLOG:
                    break
                rec = inspect(gtok, site, p["url"])
                checked += 1
                rec.update({"blog": b["name"], "title": p["title"], "published": p["published"],
                            "checked_utc": now.isoformat(), "checked": stamp})
                if "error" in rec and old:          # 확인 실패면 이전 결과 유지
                    old["last_error"] = rec["error"]
                    continue
                data[p["url"]] = rec

            mine = [data[p["url"]] for p in posts if p["url"] in data]
            ok = sum(1 for r in mine if r.get("verdict") == "PASS")
            summary.append(f"| {b['name']} | {len(posts)} | {ok} | {len(posts) - ok} | 오늘 검사 {checked}건 |")
            for p in posts:
                r = data.get(p["url"])
                if r and r.get("verdict") != "PASS":
                    problems.append((b["name"], p["published"][:10], state_ko(r), p["title"], p["url"]))

    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(1 for r in data.values() if r.get("verdict") == "PASS")
    lines = [f"# 구글 색인 점검 — {stamp} (한국시간)", "",
             f"색인됨 {total}개 / 확인한 글 {len(data)}개", "",
             "| 블로그 | 공개 글 | 색인됨 | 안 됨 | 메모 |", "|---|---|---|---|---|"]
    lines += summary or ["| - | - | - | - | 확인할 블로그 없음 |"]
    lines += ["", "## 색인 안 된 글 (오래된 순)", "", "| 블로그 | 발행일 | 상태 | 제목 |", "|---|---|---|---|"]
    problems.sort(key=lambda x: x[1])
    lines += [f"| {n} | {d} | {s} | {t} |" for n, d, s, t, _ in problems[:150]] or ["| - | - | 모두 색인됨 | - |"]
    lines += ["", "※ 새 글은 보통 며칠~몇 주 뒤에 색인된다. 발행 7일이 지나도 '크롤링됐지만 색인 안 됨'이면 글 보강 대상이다."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12 + len(summary)]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[색인 점검 오류] {e}")
        sys.exit(0)
