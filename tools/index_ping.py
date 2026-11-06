"""
발행된 새 글을 검색엔진에 자동으로 알려 주는 '색인 요청' 프로그램
- GitHub Actions에서 2시간마다 + 발행 직후에 실행됩니다.
- 블로거 API로 '실제로 공개된(live)' 글만 모읍니다 → 예약 글은 공개되는 시점에 처리됩니다.
- 이미 알린 주소는 posts/indexed.json 에 기록해서 두 번 보내지 않습니다.

검색엔진별 처리
  1) Bing  : 공식 URL 제출 API (Secrets: BING_API_KEY)   → 빙·다음(카카오)·DuckDuckGo 유입
  2) Google: 서치콘솔 API로 사이트맵 재제출 (Secrets: GSC_REFRESH_TOKEN, 없으면 건너뜀)
  3) Naver : 공개 API가 없어 posts/naver_submit.txt 에 새 주소를 모아 둡니다
             → 서치어드바이저 [요청 > 웹 페이지 수집]에 붙여넣기

어떤 단계가 실패해도 다른 블로그·다른 검색엔진은 계속 진행합니다(발행에는 영향 없음).
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "posts" / "indexed.json"
REPORT = ROOT / "posts" / "index_report.md"
NAVER = ROOT / "posts" / "naver_submit.txt"
KST = timezone(timedelta(hours=9))

BLOGGER = "https://www.googleapis.com/blogger/v3"
BING = "https://ssl.bing.com/webmaster/api.svc/json"
GSC = "https://www.googleapis.com/webmasters/v3"

LOOKBACK_DAYS = 14      # 처음 실행 때 최근 14일 글까지만 알림(오래된 글 폭탄 방지)
BING_BATCH_MAX = 100    # 한 번에 보낼 최대 주소 수(블로그당)


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


def my_blogs(token: str) -> list:
    r = requests.get(f"{BLOGGER}/users/self/blogs",
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return [{"id": b["id"], "name": b.get("name", ""), "url": b["url"]} for b in r.json().get("items", [])]


def live_posts(token: str, blog_id: str) -> list:
    """공개된 글만(예약·임시저장 제외) 최신순으로."""
    r = requests.get(f"{BLOGGER}/blogs/{blog_id}/posts", params={
        "status": "live", "fetchBodies": "false", "maxResults": 50, "orderBy": "published",
    }, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return [{"url": p["url"], "title": p.get("title", ""), "published": p.get("published", "")}
            for p in r.json().get("items", [])]


def is_recent(published: str, now: datetime) -> bool:
    try:
        t = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return True
    return now - t <= timedelta(days=LOOKBACK_DAYS)


def bing_submit(api_key: str, site: str, urls: list) -> str:
    r = requests.post(f"{BING}/SubmitUrlbatch", params={"apikey": api_key},
                      json={"siteUrl": site, "urlList": urls[:BING_BATCH_MAX]}, timeout=30)
    if r.status_code == 200:
        return "ok"
    msg = r.text[:200]
    if "NotAuthorized" in msg or "not verified" in msg.lower():
        return "실패: 빙 웹마스터에 이 블로그가 등록·인증되지 않음"
    if "Quota" in msg:
        return "실패: 오늘 빙 제출 한도 초과(내일 자동 재시도)"
    return f"실패: {r.status_code} {msg}"


def gsc_sitemap(token: str, site: str) -> str:
    sitemap = site.rstrip("/") + "/sitemap.xml"
    r = requests.put(f"{GSC}/sites/{quote(site, safe='')}/sitemaps/{quote(sitemap, safe='')}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code in (200, 204):
        return "ok"
    if r.status_code == 403:
        return "실패: 서치콘솔에 이 블로그가 등록되지 않았거나 권한 없음"
    return f"실패: {r.status_code} {r.text[:200]}"


def main():
    now = datetime.now(timezone.utc)
    done = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    bing_key = env("BING_API_KEY")
    gsc_refresh = env("GSC_REFRESH_TOKEN")

    accounts = [("메인 계정", env("BLOGGER_REFRESH_TOKEN"))]
    if env("IT_REFRESH_TOKEN"):
        accounts.append(("IT 계정", env("IT_REFRESH_TOKEN")))

    gsc_token = None
    if gsc_refresh:
        try:
            gsc_token = access_token(gsc_refresh)
        except Exception as e:
            print(f"[구글] 서치콘솔 토큰 갱신 실패: {e}")

    rows, naver_new = [], []
    for acc_name, refresh in accounts:
        if not refresh:
            continue
        try:
            tok = access_token(refresh)
            blogs = my_blogs(tok)
        except Exception as e:
            rows.append(f"| {acc_name} | - | - | 블로그 목록 실패: {e} | - |")
            continue
        for b in blogs:
            try:
                posts = live_posts(tok, b["id"])
            except Exception as e:
                rows.append(f"| {b['name']} | 0 | - | 글 목록 실패: {e} | - |")
                continue
            recent = [p for p in posts if is_recent(p["published"], now)]
            new = [p for p in recent if p["url"] not in done]                         # 처음 보는 글
            bing_todo = [p for p in recent if done.get(p["url"], {}).get("bing") != "ok"]  # 빙 미완료(재시도 포함)
            if not new and not (bing_key and bing_todo):
                continue

            bing = (bing_submit(bing_key, b["url"], [p["url"] for p in bing_todo])
                    if bing_key and bing_todo else "건너뜀(BING_API_KEY 없음)" if not bing_key else "-")
            google = ("-" if not new else
                      gsc_sitemap(gsc_token, b["url"]) if gsc_token else "건너뜀(GSC_REFRESH_TOKEN 없음)")

            stamp = now.astimezone(KST).strftime("%Y-%m-%d %H:%M")
            for p in new:
                done[p["url"]] = {"blog": b["name"], "title": p["title"], "at": stamp, "google": google}
            if bing != "-":
                for p in bing_todo:
                    done[p["url"]]["bing"] = bing   # ok 가 아니면 다음 실행 때 다시 보냄
            naver_new += [f"{p['url']}    # {b['name']} | {p['title']}" for p in new]
            rows.append(f"| {b['name']} | {len(new)} | {bing} | {google} | {b['url']} |")

    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")

    stamp = now.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    if naver_new:
        old = NAVER.read_text(encoding="utf-8") if NAVER.exists() else ""
        NAVER.write_text(f"## {stamp} 새 글 (네이버 서치어드바이저 > 요청 > 웹 페이지 수집에 한 줄씩 붙여넣기)\n"
                         + "\n".join(naver_new) + "\n\n" + old, encoding="utf-8")

    report = [f"# 색인 요청 결과 — {stamp} (한국시간)", "",
              "| 블로그 | 새 글 | Bing 제출 | Google 사이트맵 | 주소 |", "|---|---|---|---|---|"]
    report += rows or ["| - | 0 | 새로 공개된 글 없음 | - | - |"]
    report += ["", f"누적 알림 완료 글: {len(done)}개", "네이버용 주소 목록: posts/naver_submit.txt"]
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 색인 요청 실패가 다른 작업을 막지 않도록
        print(f"[색인 요청 오류] {e}")
        sys.exit(0)
