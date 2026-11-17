"""tools/pages/pages.json 의 페이지를 블로그마다 반영한다(같은 제목 페이지가 있으면 내용 교체, 없으면 새로 만듦).
결과는 posts/audit/pages_fix.md"""
import json, os
from pathlib import Path
import requests
API = "https://www.googleapis.com/blogger/v3"
c = lambda n: os.environ.get(n, "").strip()
def token(ref):
    r = requests.post("https://oauth2.googleapis.com/token", data={"client_id": c("BLOGGER_CLIENT_ID"), "client_secret": c("BLOGGER_CLIENT_SECRET"), "refresh_token": ref, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status(); return r.json()["access_token"]
want = json.loads(Path("tools/pages/pages.json").read_text(encoding="utf-8"))
log = ["# 페이지 반영 결과", ""]
for acct, ref in (("main", c("BLOGGER_REFRESH_TOKEN")), ("it", c("IT_REFRESH_TOKEN"))):
    if not ref: continue
    H = {"Authorization": f"Bearer {token(ref)}"}
    for b in requests.get(f"{API}/users/self/blogs", headers=H, timeout=30).json().get("items", []):
        host = b["url"].split("//")[1].strip("/")
        if host not in want: continue
        cur = {p["title"]: p for p in requests.get(f"{API}/blogs/{b['id']}/pages", headers=H, params={"status": "live"}, timeout=30).json().get("items", [])}
        for title, html in want[host].items():
            if title in cur:
                r = requests.patch(f"{API}/blogs/{b['id']}/pages/{cur[title]['id']}", headers=H, json={"content": html}, timeout=30); act = "수정"
            else:
                r = requests.post(f"{API}/blogs/{b['id']}/pages", headers=H, json={"title": title, "content": html}, timeout=30); act = "새로 만듦"
            log.append(f"- {b.get('name')} · {title}: {act} {'성공' if r.ok else '실패 ' + str(r.status_code) + ' ' + r.text[:150]}" + (f" {r.json().get('url','')}" if r.ok else ""))
Path("posts/audit").mkdir(parents=True, exist_ok=True)
Path("posts/audit/pages_fix.md").write_text("\n".join(log), encoding="utf-8"); print("\n".join(log))
