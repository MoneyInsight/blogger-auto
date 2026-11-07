"""블로그 상품 링크 아래에 붙일 '미리보기 카드'용 썸네일을 만든다.

- 쿠팡: coupang/links.json 각 상품의 productImage를 받아 coupang/img/c{번호}.jpg 로 저장
- 브랜드 커넥트: coupang/brandconnect.json 의 링크를 열어 og:title·og:image를 읽고
  coupang/img/b{번호}.jpg 와 coupang/brandconnect_cards.json 에 저장
GitHub Actions(쿠팡 파트너스 링크 갱신)에서 tools/coupang_links.py 다음에 실행된다.
"""
import html
import io
import json
import os
import re

import requests
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), "..", "coupang")
IMG = os.path.join(ROOT, "img")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})


def save_thumb(url: str, path: str) -> bool:
    try:
        r = S.get(url, timeout=20)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        im.thumbnail((600, 600))
        im.save(path, "JPEG", quality=80, optimize=True, progressive=True)
        return True
    except Exception as e:  # noqa: BLE001
        print("  이미지 실패:", url[:80], e)
        return False


def og(page: str, prop: str) -> str | None:
    m = re.search(rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\']([^"\']+)', page) or \
        re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{prop}["\']', page)
    return html.unescape(m.group(1)).strip() if m else None


def coupang_cards() -> None:
    p = os.path.join(ROOT, "links.json")
    if not os.path.exists(p):
        return
    d = json.load(open(p, encoding="utf-8"))
    for f in os.listdir(IMG):
        if f.startswith("c"):
            os.remove(os.path.join(IMG, f))
    ok = 0
    for i, it in enumerate(d["items"]):
        rel = f"img/c{i}.jpg"
        if it.get("image") and save_thumb(it["image"], os.path.join(ROOT, rel)):
            it["thumb"] = rel
            ok += 1
        else:
            it.pop("thumb", None)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 쿠팡 카드 썸네일 {ok}/{len(d['items'])}개")


def brandconnect_cards() -> None:
    """coupang/brandconnect.json: [{"url", "image"(사용자가 준 이미지 주소), "title"(선택)}]"""
    src = os.path.join(ROOT, "brandconnect.json")
    if not os.path.exists(src):
        return
    links = json.load(open(src, encoding="utf-8"))
    for f in os.listdir(IMG):
        if f.startswith("b"):
            os.remove(os.path.join(IMG, f))
    cards = []
    for i, it in enumerate(links):
        it = it if isinstance(it, dict) else {"url": it}
        rel = f"img/b{i}.jpg"
        card = {"url": it["url"], "title": it.get("title"), "site": "smartstore.naver.com · 네이버 쇼핑",
                "thumb": rel if it.get("image") and save_thumb(it["image"], os.path.join(ROOT, rel)) else None}
        print(f"  B{i}: {card['url']} / 썸네일 {'O' if card['thumb'] else 'X'}")
        cards.append(card)
    json.dump(cards, open(os.path.join(ROOT, "brandconnect_cards.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"✅ 브랜드 커넥트 카드 {sum(1 for c in cards if c['thumb'])}/{len(cards)}개")


if __name__ == "__main__":
    os.makedirs(IMG, exist_ok=True)
    coupang_cards()
    brandconnect_cards()
