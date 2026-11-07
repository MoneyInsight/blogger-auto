"""쿠팡 파트너스 API로 오늘의 추천 상품 링크를 모아 coupang/links.json에 저장한다.

GitHub Actions(.github/workflows/coupang-links.yml)가 매일 아침 실행한다.
필요한 저장소 Secrets: COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
블로그 글 작성 작업은 이 파일의 items를 순서대로 돌려 가며 글에 넣는다.
"""
import datetime as dt
import hashlib
import hmac
import json
import os
import sys
import time
from urllib.parse import urlencode

import requests

HOST = "https://api-gateway.coupang.com"
BASE = "/v2/providers/affiliate_open_api/apis/openapi"
OUT = os.path.join(os.path.dirname(__file__), "..", "coupang", "links.json")

# 날짜별로 돌려 쓰는 베스트 카테고리 (쿠팡 파트너스 카테고리 ID)
CATEGORIES = [
    (1014, "생활용품"), (1012, "식품"), (1013, "주방용품"), (1024, "헬스/건강식품"),
    (1016, "가전디지털"), (1010, "뷰티"), (1015, "홈인테리어"), (1017, "스포츠/레저"),
    (1011, "출산/유아동"), (1029, "반려동물용품"), (1021, "문구/오피스"), (1018, "자동차용품"),
]
PER_CATEGORY = 10
SUB_ID = "blog"


def auth_header(method: str, path: str, query: str, access: str, secret: str) -> str:
    signed = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    msg = signed + method + path + query
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return (f"CEA algorithm=HmacSHA256, access-key={access}, "
            f"signed-date={signed}, signature={sig}")


def call(path_tail: str, params: dict, access: str, secret: str):
    """경로가 v1 유무로 갈리는 경우가 있어 둘 다 시도한다."""
    query = urlencode(params)
    last = None
    for prefix in (BASE, BASE + "/v1"):
        path = prefix + path_tail
        headers = {"Authorization": auth_header("GET", path, query, access, secret),
                   "Content-Type": "application/json;charset=UTF-8"}
        r = requests.get(f"{HOST}{path}?{query}", headers=headers, timeout=20)
        if r.status_code == 404:
            last = r
            continue
        if r.status_code != 200:
            raise RuntimeError(f"{path_tail} HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        if str(body.get("rCode")) not in ("0", "None") and body.get("data") is None:
            raise RuntimeError(f"{path_tail} 오류: {body.get('rMessage')}")
        return body.get("data") or []
    raise RuntimeError(f"{path_tail} HTTP 404: {last.text[:200] if last else ''}")


def to_item(p: dict, source: str) -> dict | None:
    url = p.get("productUrl")
    name = (p.get("productName") or "").strip()
    if not url or not name:
        return None
    return {
        "name": name,
        "url": url,
        "image": p.get("productImage"),
        "price": p.get("productPrice"),
        "category": p.get("categoryName") or source,
        "rocket": bool(p.get("isRocket")),
        "source": source,
    }


def main() -> int:
    access = os.environ.get("COUPANG_ACCESS_KEY", "").strip()
    secret = os.environ.get("COUPANG_SECRET_KEY", "").strip()
    if not access or not secret:
        print("⚠️ COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 시크릿이 없습니다. 저장소 Settings → Secrets에 넣어 주세요.")
        return 1

    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    start = today.toordinal() % len(CATEGORIES)
    picks = [CATEGORIES[(start + i) % len(CATEGORIES)] for i in range(3)]

    items, errors, seen = [], [], set()

    def add(products, source):
        for p in products:
            it = to_item(p, source)
            if it and it["url"] not in seen:
                seen.add(it["url"])
                items.append(it)

    try:
        add(call("/products/goldbox", {"subId": SUB_ID}, access, secret)[:15], "골드박스")
    except Exception as e:  # noqa: BLE001
        errors.append(str(e))
    for cid, cname in picks:
        try:
            add(call(f"/products/bestcategories/{cid}",
                     {"limit": PER_CATEGORY, "subId": SUB_ID}, access, secret), cname)
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))

    for e in errors:
        print("⚠️", e)
    if not items:
        print("⚠️ 받은 상품이 없어 기존 links.json을 그대로 둡니다.")
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": today.isoformat(timespec="minutes"),
                   "categories": ["골드박스"] + [c for _, c in picks],
                   "count": len(items), "items": items}, f, ensure_ascii=False, indent=1)
    print(f"✅ 쿠팡 링크 {len(items)}개 저장 ({', '.join(['골드박스'] + [c for _, c in picks])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
