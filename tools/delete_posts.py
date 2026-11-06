"""tools/delete_posts.json 에 적힌 글 주소를 블로거에서 삭제합니다(메인 구글 계정 블로그).
형식: {"urls": ["https://블로그.blogspot.com/2026/11/글.html", ...]}
결과는 posts/delete_report.txt 에 남고, 처리 후 목록은 비워집니다."""
import json, os
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "tools" / "delete_posts.json"
API = "https://www.googleapis.com/blogger/v3"
c = lambda n: os.environ.get(n, "").strip()

tok = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": c("BLOGGER_CLIENT_ID"), "client_secret": c("BLOGGER_CLIENT_SECRET"),
    "refresh_token": c("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=30).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

urls = json.loads(LIST.read_text(encoding="utf-8")).get("urls", [])
out = []
for url in urls:
    try:
        u = urlparse(url)
        blog = requests.get(f"{API}/blogs/byurl", params={"url": f"https://{u.netloc}/"}, headers=H, timeout=30)
        blog.raise_for_status()
        bid = blog.json()["id"]
        post = requests.get(f"{API}/blogs/{bid}/posts/bypath", params={"path": u.path}, headers=H, timeout=30)
        if post.status_code == 404:
            out.append(f"이미 없음  {url}")
            continue
        post.raise_for_status()
        p = post.json()
        d = requests.delete(f"{API}/blogs/{bid}/posts/{p['id']}", headers=H, timeout=30)
        out.append(("삭제 완료  " if d.status_code in (200, 204) else f"삭제 실패 {d.status_code} {d.text[:150]}  ")
                   + f"{url} | {p.get('title', '')}")
    except Exception as e:
        out.append(f"오류 {e}  {url}")

(ROOT / "posts" / "delete_report.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
LIST.write_text(json.dumps({"urls": []}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("\n".join(out))
