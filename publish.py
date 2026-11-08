"""
구글 블로거(블로그스팟) 자동 발행 스크립트
- GitHub Actions에서 실행됩니다.
- posts/queue/<글폴더>/ 안의 post.json + post.html + 이미지를 읽어서 블로거에 발행합니다.
- 발행이 끝난 글폴더는 posts/published/ 로 옮겨집니다.

글폴더 구성 예시
  posts/queue/2026-10-28-0700-economy/
    post.json   {"title": "제목", "labels": ["경제", "주식"], "publish_at": "2026-10-28T07:00:00+09:00"}
                IT 블로그(itdigitaldream)로 보낼 글은 "blog": "it" 추가
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

def _clean(name: str) -> str:
    """'BLOGGER_X = 값' 처럼 줄 전체를 붙여넣었거나 공백·따옴표가 섞여도 값만 꺼냅니다."""
    v = os.environ.get(name, "").strip()
    if "=" in v and v.split("=", 1)[0].strip().startswith(("BLOGGER_", "IT_")):
        v = v.split("=", 1)[1]
    v = v.strip().strip('"').strip("'").strip()
    return v.split()[0] if v else ""


CLIENT_ID = _clean("BLOGGER_CLIENT_ID")
CLIENT_SECRET = _clean("BLOGGER_CLIENT_SECRET")
REFRESH_TOKEN = _clean("BLOGGER_REFRESH_TOKEN")
BLOG_ID = _clean("BLOGGER_BLOG_ID")
BLOG_URL = os.environ.get("BLOGGER_BLOG_URL", "").strip()

# IT 블로그(itdigitaldream) — 다른 구글 계정. post.json 에 "blog": "it" 이면 이쪽으로 발행
IT_REFRESH_TOKEN = _clean("IT_REFRESH_TOKEN")
IT_BLOG_ID = _clean("IT_BLOG_ID")

# 건강·생활 블로그 — 메인과 같은 구글 계정(같은 인증키). post.json 에 "blog": "health" 이면 이쪽으로 발행
HEALTH_BLOG_ID = _clean("HEALTH_BLOG_ID") or "2761363091680251968"

# 추가 블로그(메인과 같은 구글 계정): blogs.json 에 {"키": "https://주소.blogspot.com/"} 로 등록하면
# post.json 의 "blog": "키" 글이 그 블로그로 발행됩니다.
try:
    EXTRA_BLOGS = {k: v for k, v in json.loads((Path(__file__).resolve().parent / "blogs.json").read_text(encoding="utf-8")).items() if not k.startswith("_") and v}
except FileNotFoundError:
    EXTRA_BLOGS = {}

REPO = os.environ.get("GITHUB_REPOSITORY", "")
SHA = os.environ.get("GITHUB_SHA", "main")

API = "https://www.googleapis.com/blogger/v3"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def get_access_token(refresh_token: str = None) -> str:
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token or REFRESH_TOKEN,
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


def blog_id_by_url(token: str, url: str) -> str:
    r = requests.get(f"{API}/blogs/byurl", params={"url": url},
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


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

    html = re.sub(r'(<img[^>]*?\ssrc=["\'])([^"\']+)(["\'])', swap, html, flags=re.I)

    def responsive(m):
        if "author-avatar" in m.group(0):
            return m.group(0)
        tag = re.sub(r'\s(?:style|width|height)=("[^"]*"|\'[^\']*\')', '', m.group(0))
        tag = re.sub(r'\s*/?>$', '', tag)
        return tag + ' style="max-width:100%;width:100%;height:auto;display:block;margin:0 auto;" />'

    html = re.sub(r'<img\b[^>]*>', responsive, html, flags=re.I)
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import author
        meta = json.loads((folder / "post.json").read_text(encoding="utf-8"))
        b = str(meta.get("blog", "main")).lower()
        html = author.add(html, b)
    except Exception as e:
        print("작성자 상자 추가 건너뜀:", e)
    return html


def clamp_window(ts: str) -> str:
    """예약 시각을 한국시간 08:00~22:00 안으로 맞춥니다(밖이면 같은 날 안의 랜덤 시각으로 이동)."""
    import random
    from datetime import datetime, timezone, timedelta
    kst = timezone(timedelta(hours=9))
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(kst)
    except ValueError:
        return ts
    minutes = t.hour * 60 + t.minute
    if 8 * 60 <= minutes <= 22 * 60:
        return ts
    if minutes > 22 * 60:
        new = t.replace(hour=random.randint(19, 21), minute=random.randint(0, 59), second=0, microsecond=0)
    else:
        new = t.replace(hour=random.randint(8, 9), minute=random.randint(0, 59), second=0, microsecond=0)
    return new.isoformat()


def update(token: str, blog_id: str, folder: Path, meta: dict) -> dict:
    """post.json에 "update_of": 글ID 가 있으면 새 글 대신 기존 글을 수정합니다 (라벨·제목·본문)."""
    body = {}
    if "labels" in meta:
        body["labels"] = meta["labels"]
    if meta.get("title"):
        body["title"] = meta["title"]
    if (folder / "post.html").exists():
        body["content"] = build_html(folder)
    r = requests.patch(
        f"{API}/blogs/{blog_id}/posts/{meta['update_of']}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text}")
    return r.json()


def seo_check(folder: Path):
    """색인·노출 점검 90점 미만이면 발행하지 않음(h1·alt는 자동 수정 후 재점검)."""
    sys.path.insert(0, str(ROOT / "tools"))
    import seo_gate
    total, checks, kw = seo_gate.score(folder)
    if total < seo_gate.PASS:
        seo_gate.autofix(folder, kw)
        total, checks, kw = seo_gate.score(folder)
    rep = seo_gate.report(folder, total, checks)
    print(rep)
    if total < seo_gate.PASS:
        raise RuntimeError("[SEO 점검 미달 — 발행 보류] 아래 항목을 고친 뒤 이 폴더를 posts/queue/ 로 다시 옮겨 push 한다.\n"
                           "검사: python tools/seo_gate.py <폴더> --fix\n" + rep)


def publish(token: str, blog_id: str, folder: Path) -> dict:
    meta = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    if (folder / "post.html").exists() and not meta.get("skip_seo_gate"):
        seo_check(folder)
    if meta.get("update_of"):
        return update(token, blog_id, folder, meta)
    body = {
        "kind": "blogger#post",
        "title": meta["title"],
        "content": build_html(folder),
    }
    if meta.get("labels"):
        body["labels"] = meta["labels"]
    if meta.get("publish_at"):
        body["published"] = clamp_window(meta["publish_at"])  # 미래 시각이면 예약 발행

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

    targets = {}  # "main" / "it" → (token, blog_id), 필요할 때 한 번만 발급

    def target(name):
        if name not in targets:
            if name in EXTRA_BLOGS:  # blogs.json 에 등록된 블로그 — 주소로 ID 조회
                tok = get_access_token()
                targets[name] = (tok, blog_id_by_url(tok, EXTRA_BLOGS[name]))
            elif name == "welfare":  # 정부지원·복지 블로그 — 메인과 같은 구글 계정, 주소로 ID 조회
                tok = get_access_token()
                targets[name] = (tok, blog_id_by_url(tok, "https://govermentnwelfare.blogspot.com/"))
            elif name == "edu":  # 육아·교육 블로그 — 메인과 같은 구글 계정
                targets[name] = (get_access_token(), "3607854023992740453")
            elif name == "ittech":  # 메인과 같은 구글 계정, 주소로 블로그 ID 조회
                tok = get_access_token()
                targets[name] = (tok, blog_id_by_url(tok, "https://ittechdurion0506.blogspot.com/"))
            elif name == "health":
                targets[name] = (get_access_token(), HEALTH_BLOG_ID)
            elif name == "it":
                if not (IT_REFRESH_TOKEN and IT_BLOG_ID):
                    raise RuntimeError("IT 블로그 Secrets(IT_REFRESH_TOKEN, IT_BLOG_ID)가 비어 있음")
                try:
                    targets[name] = (get_access_token(IT_REFRESH_TOKEN), IT_BLOG_ID)
                except SystemExit as e:  # IT 열쇠 문제가 경제·건강 글까지 막지 않게
                    raise RuntimeError(f"IT 블로그 {e.code}")
            else:
                tok = get_access_token()
                targets[name] = (tok, resolve_blog_id(tok))
        return targets[name]

    ok, fail = 0, 0

    for folder in folders:
        try:
            meta0 = json.loads((folder / "post.json").read_text(encoding="utf-8"))
            b = str(meta0.get("blog", "")).lower()
            which = b if (b in ("it", "health", "ittech", "edu", "welfare") or b in EXTRA_BLOGS) else "main"
            token, blog_id = target(which)
            res = publish(token, blog_id, folder)
            meta_path = folder / "post.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta.update({"blogger_id": res.get("id"), "url": res.get("url"), "status": res.get("status")})
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            move(folder, DONE)
            print(f"[완료] {meta.get('title') or res.get('title')} → {res.get('url') or res.get('status')}")
            ok += 1
        except Exception as e:
            (folder / "error.txt").write_text(str(e), encoding="utf-8")
            move(folder, FAILED)
            print(f"[발행 실패] {folder.name}: {e}")
            fail += 1

    git_commit(f"블로거 발행: 성공 {ok}건, 실패 {fail}건")
    if fail:
        sys.exit(1)


def report_fatal(msg: str):
    """치명적 오류를 저장소에 남겨서 Claude가 원인을 읽을 수 있게 합니다 (열쇠 값은 남기지 않음)."""
    msg += f"\n(BLOG_ID 숫자 여부 {BLOG_ID.isdigit()}, CLIENT_ID 형식 정상 {CLIENT_ID.endswith('.apps.googleusercontent.com')})"
    for v in (CLIENT_SECRET, REFRESH_TOKEN, IT_REFRESH_TOKEN):
        if v:
            msg = msg.replace(v, "***")
    (ROOT / "posts").mkdir(exist_ok=True)
    (ROOT / "posts" / "last_error.txt").write_text(msg, encoding="utf-8")
    try:
        git_commit("블로거 발행 오류 기록")
    except Exception:
        pass
    print(msg)
    sys.exit(1)


if __name__ == "__main__":
    missing = [n for n, v in (("BLOGGER_CLIENT_ID", CLIENT_ID), ("BLOGGER_CLIENT_SECRET", CLIENT_SECRET), ("BLOGGER_REFRESH_TOKEN", REFRESH_TOKEN)) if not v]
    if missing:
        report_fatal("[오류] Secrets가 비어 있음: " + ", ".join(missing))
    try:
        main()
    except SystemExit as e:
        if e.code not in (0, None, 1) and isinstance(e.code, str):
            report_fatal(e.code)
        raise
    except Exception as e:
        import traceback
        report_fatal("[오류] " + "".join(traceback.format_exception(e)))
