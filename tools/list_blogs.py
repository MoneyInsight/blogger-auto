"""메인 구글 계정의 블로거 블로그 목록(이름·주소·ID·글 수)을 posts/my_blogs.txt 로 저장합니다."""
import os, requests
from pathlib import Path
c = lambda n: os.environ.get(n, "").strip()
tok = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": c("BLOGGER_CLIENT_ID"), "client_secret": c("BLOGGER_CLIENT_SECRET"),
    "refresh_token": c("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30).json()["access_token"]
r = requests.get("https://www.googleapis.com/blogger/v3/users/self/blogs",
                 headers={"Authorization": f"Bearer {tok}"}, timeout=30)
lines = [f'{b.get("name")} | {b.get("url")} | {b.get("id")} | posts={b.get("posts",{}).get("totalItems")} | {b.get("published","")[:10]}'
         for b in r.json().get("items", [])] if r.ok else [f"ERROR {r.status_code} {r.text}"]
Path("posts").mkdir(exist_ok=True)
Path("posts/my_blogs.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
