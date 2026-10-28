"""
글폴더 안의 images.json을 읽어 썸네일(thumb.jpg)과 본문 카드(img1.jpg, img2.jpg ...)를 만듭니다.
사용: python tools/make_images.py posts/queue/<글폴더>

images.json 예시
{
  "thumb": {"top": "내일 새벽 3시", "main1": "금리 또 오르면", "main2": "내 대출이자 얼마?",
            "badge": "미국 FOMC 긴급 체크", "bottom": "기준금리 3.75~4.00%", "theme": "dark"},
  "cards": [
    {"title": "3가지 시나리오", "items": ["① 동결 | 시장 안도", "② 동결+인상 예고 | 달러 강세"], "theme": "light"},
    {"title": "이것만 체크", "items": ["환율", "12월 힌트"], "theme": "dark"}
  ]
}
theme: dark(검정 배경·노랑 강조) / light(흰 배경) / red(빨강 배경) / blue(파랑 배경)
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FD = "/usr/share/fonts/opentype/noto/"
THEMES = {
    "dark":  ("#0B0F1A", "#FFFFFF", "#FFD400", "#9AA3B5", "#FF3B30"),
    "light": ("#FFFFFF", "#111111", "#D32F2F", "#666666", "#1A73E8"),
    "red":   ("#C62828", "#FFFFFF", "#FFE082", "#FFCDD2", "#111111"),
    "blue":  ("#0D47A1", "#FFFFFF", "#FFD400", "#BBDEFB", "#FF3B30"),
}
_cache = {}
def font(weight, size):
    key = (weight, size)
    if key not in _cache:
        path = FD + f"NotoSansCJK-{weight}.ttc"
        f = None
        for i in range(8):
            try:
                t = ImageFont.truetype(path, size, index=i)
                if "KR" in t.getname()[0]:
                    f = t; break
            except Exception:
                break
        _cache[key] = f or ImageFont.truetype(path, size)
    return _cache[key]

def fit(d, text, weight, size, maxw):
    while size > 20 and d.textlength(text, font=font(weight, size)) > maxw:
        size -= 4
    return font(weight, size)

def center(d, y, text, f, fill, W):
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)

def thumb(spec, out):
    W, H = 1200, 800
    bg, fg, acc, sub, badge = THEMES.get(spec.get("theme", "dark"), THEMES["dark"])
    im = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 14], fill=acc)
    if spec.get("top"):
        center(d, 80, spec["top"], fit(d, spec["top"], "Bold", 64, W - 120), fg, W)
    center(d, 185, spec["main1"], fit(d, spec["main1"], "Black", 128, W - 80), acc, W)
    if spec.get("main2"):
        center(d, 345, spec["main2"], fit(d, spec["main2"], "Black", 128, W - 80), fg, W)
    if spec.get("badge"):
        f = fit(d, spec["badge"], "Black", 56, W - 260)
        bw = d.textlength(spec["badge"], font=f) + 100
        d.rounded_rectangle([(W - bw) / 2, 555, (W + bw) / 2, 660], radius=52, fill=badge)
        center(d, 570, spec["badge"], f, "#FFFFFF", W)
    if spec.get("bottom"):
        center(d, 700, spec["bottom"], fit(d, spec["bottom"], "Medium", 36, W - 120), sub, W)
    im.save(out, quality=86, optimize=True)

def card(spec, out):
    items = spec.get("items", [])
    W = 1200; H = 200 + 170 * len(items) + 60
    bg, fg, acc, sub, _ = THEMES.get(spec.get("theme", "light"), THEMES["light"])
    im = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(im)
    center(d, 55, spec["title"], fit(d, spec["title"], "Black", 58, W - 100), acc if bg != "#FFFFFF" else fg, W)
    y = 180
    box = "#F5F6F8" if bg == "#FFFFFF" else None
    for it in items:
        head, _, tail = it.partition("|")
        if box:
            d.rounded_rectangle([60, y, W - 60, y + 145], radius=26, fill=box)
            d.rounded_rectangle([60, y, 78, y + 145], radius=9, fill=acc)
        x = 110
        if tail.strip():
            d.text((x, y + 18), head.strip(), font=fit(d, head.strip(), "Black", 50, W - 200), fill=acc if box else fg)
            d.text((x, y + 85), tail.strip(), font=fit(d, tail.strip(), "Medium", 36, W - 200), fill=sub if not box else "#333333")
        else:
            d.text((x, y + 40), head.strip(), font=fit(d, head.strip(), "Bold", 52, W - 200), fill=fg if not box else "#111111")
        y += 170
    im.save(out, quality=86, optimize=True)

if __name__ == "__main__":
    folder = Path(sys.argv[1])
    spec = json.loads((folder / "images.json").read_text(encoding="utf-8"))
    thumb(spec["thumb"], folder / "thumb.jpg")
    for i, c in enumerate(spec.get("cards", []), 1):
        card(c, folder / f"img{i}.jpg")
    (folder / "images.json").unlink()
    print("이미지 생성 완료:", sorted(p.name for p in folder.glob("*.jpg")))
