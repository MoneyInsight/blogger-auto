"""두 구글 계정(메인·IT)의 모든 블로거 블로그에서 공개·예약 글 전체를 받아 posts/audit/live.json 으로 저장합니다.
애드센스 점검(중복·반복 제목·분량·문체) 용. 본문은 태그를 뺀 글자만 저장합니다."""
import json, os, re
from pathlib import Path
import requests

API = "https://www.googleapis.com/blogger/v3"
c = lambda n: os.environ.get(n, "").strip()


def token(refresh):
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": c("BLOGGER_CLIENT_ID"), "client_secret": c("BLOGGER_CLIENT_SECRET"),
        "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


out = {"blogs": []}
for acct, ref in (("main", c("BLOGGER_REFRESH_TOKEN")), ("it", c("IT_REFRESH_TOKEN"))):
    if not ref:
        continue
    try:
        H = {"Authorization": f"Bearer {token(ref)}"}
        blogs = requests.get(f"{API}/users/self/blogs", headers=H, timeout=30).json().get("items", [])
    except Exception as e:
        out["blogs"].append({"account": acct, "error": str(e)})
        continue
    for b in blogs:
        posts, page = [], None
        for status in ("live", "scheduled"):
            page = None
            while True:
                p = {"maxResults": 100, "status": status, "fetchBodies": "true", "view": "ADMIN"}
                if page:
                    p["pageToken"] = page
                r = requests.get(f"{API}/blogs/{b['id']}/posts", headers=H, params=p, timeout=60)
                if not r.ok:
                    posts.append({"error": f"{status} {r.status_code} {r.text[:200]}"})
                    break
                j = r.json()
                for it in j.get("items", []):
                    html = it.get("content", "")
                    posts.append({"id": it["id"], "status": it.get("status"), "url": it.get("url"),
                                  "title": it.get("title"), "published": it.get("published"),
                                  "labels": it.get("labels", []), "links": len(re.findall(r"<a\s", html)),
                                  "h2": re.findall(r"<h2[^>]*>(.*?)</h2>", html, flags=re.S)[:8],
                                  "text": plain(html)})
                page = j.get("nextPageToken")
                if not page:
                    break
        out["blogs"].append({"account": acct, "id": b["id"], "name": b.get("name"), "url": b.get("url"), "posts": posts})

Path("posts/audit").mkdir(parents=True, exist_ok=True)
Path("posts/audit/live.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
for b in out["blogs"]:
    print(b.get("name"), len(b.get("posts", [])), b.get("error", ""))
