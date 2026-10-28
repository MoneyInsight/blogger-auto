"""
구글 블로거(블로그스팟) 자동 발행 스크립트
- GitHub Actions에서 실행됩니다.
- posts/queue/<글폴더>/ 안의 post.json + post.html + 이미지를 읽어서 블로거에 발행합니다.
- 발행이 끝난 글폴더는 posts/published/ 로 옮겨집니다.

글폴더 구성 예시
  posts/queue/2026-10-28-0700-economy/
    post.json   {"title": "제목", "labels": ["경제", "주식"], "publish_at": "2026-10-28T07:00:00+09:00"}
    post.html   본문 HTML (이미지는 <img src="thumb.jpg"> 처럼 파일 이름만 써도 됨)
    thumb.jpg   첫 번째 이미지 = 블로거 대표이미지(썸네일)
    img1.jpg ...

publish_at 을 미래 시각으로 넣으면 블로거 '예약 발행'으로 올라가고,
비워 두면 즉시 공개 발행됩니다.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "posts" / "queue"
DONE = ROOT / "posts" / "published"
FAILED = ROOT / "posts" / "failed"

CLIENT_ID = os.environ["BLOGGER_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "").strip()
BLOG_URL = os.environ.get("BLOGGER_BLOG_URL", "").strip()

REPO = os.environ.get("GITHUB_REPOSITORY", "")
SHA = os.environ.get("GITHUB_SHA", "main")

API = "https://www.googleapis.com/blogger/v3"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def get_access_token() -> str:
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if r.status_code != 200:
        sys.exit(
            "[오류] 구글 토큰 갱신 실패: "
            + r.text
            + "\n→ OAuth 동의 화면이 '테스트' 상태면 7일마다 토큰이 만료됩니다. '프로덕션'으로 게시 후 get_token.py를 다시 실행하세요."
        )
    return r.json()["access_token"]


def resolve_blog_id(token: str) -> str:
    if BLOG_ID:
        return BLOG_ID
    if not BLOG_URL:
        sys.exit("[오류] BLOGGER_BLOG_ID 또는 BLOGGER_BLOG_URL 중 하나를 Secrets에 넣어 주세요.")
    r = requests.get(
        f"{API}/blogs/byurl",
        params={"url": BLOG_URL},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def image_url(folder: Path, name: str) -> str:
    """저장소에 올라간 이미지를 커밋 고정 주소로 바꿉니다 (나중에 폴더를 옮겨도 깨지지 않음)."""
    rel = (folder / name).relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{REPO}/{SHA}/{rel}"


def build_html(folder: Path) -> str:
    html = (folder / "post.html").read_text(encoding="utf-8")
    local_images = {p.name for p in folder.iterdir() if p.suffix.lower() in IMG_EXT}

    def swap(m):
        src = m.group(2)
        name = src.split("/")[-1]
        if not src.startswith(("http://", "https://", "data:")) and name in local_images:
            return f'{m.group(1)}{image_url(folder, name)}{m.group(3)}'
        return m.group(0)

    return re.sub(r'(<img[^>]*?\ssrc=["\'])([^"\']+)(["\'])', swap, html, flags=re.I)


def publish(token: str, blog_id: str, folder: Path) -> dict:
    meta = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    body = {
        "kind": "blogger#post",
        "title": meta["title"],
        "content": build_html(folder),
    }
    if meta.get("labels"):
        body["labels"] = meta["labels"]
    if meta.get("publish_at"):
        body["published"] = meta["publish_at"]  # 미래 시각이면 예약 발행

    r = requests.post(
        f"{API}/blogs/{blog_id}/posts/",
        params={"isDraft": "true" if meta.get("draft") else "false"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=60,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"{r.status_code} {r.text}")
    return r.json()


def move(folder: Path, dest_root: Path):
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / folder.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(folder), str(dest))
    return dest


def git_commit(msg: str):
    subprocess.run(["git", "config", "user.name", "blogger-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "blogger-bot@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", "-A", "posts"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push"], check=True)


def main():
    folders = sorted(p for p in QUEUE.glob("*") if p.is_dir() and (p / "post.json").exists())
    if not folders:
        print("발행할 글이 없습니다.")
        return

    token = get_access_token()
    blog_id = resolve_blog_id(token)
    ok, fail = 0, 0

    for folder in folders:
        try:
            res = publish(token, blog_id, folder)
            meta_path = folder / "post.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta.update({"blogger_id": res.get("id"), "url": res.get("url"), "status": res.get("status")})
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            move(folder, DONE)
            print(f"[발행 완료] {meta['title']} → {res.get('url') or res.get('status')}")
            ok += 1
        except Exception as e:
            (folder / "error.txt").write_text(str(e), encoding="utf-8")
            move(folder, FAILED)
            print(f"[발행 실패] {folder.name}: {e}")
            fail += 1

    git_commit(f"블로거 발행: 성공 {ok}건, 실패 {fail}건")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
