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
        center(d, 80, spec["top"], fit(d, spec["top"], "Bold", 64, W - 240), fg, W)
    center(d, 185, spec["main1"], fit(d, spec["main1"], "Black", 128, W - 240), acc, W)
    if spec.get("main2"):
        center(d, 345, spec["main2"], fit(d, spec["main2"], "Black", 128, W - 240), fg, W)
    if spec.get("badge"):
        f = fit(d, spec["badge"], "Black", 56, W - 400)
        bw = d.textlength(spec["badge"], font=f) + 100
        d.rounded_rectangle([(W - bw) / 2, 555, (W + bw) / 2, 660], radius=52, fill=badge)
        center(d, 570, spec["badge"], f, "#FFFFFF", W)
    if spec.get("bottom"):
        center(d, 700, spec["bottom"], fit(d, spec["bottom"], "Medium", 36, W - 240), sub, W)
    im.save(out, quality=86, optimize=True)

def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > maxw and cur:
            lines.append(cur); cur = ch.lstrip()
        else:
            cur += ch
    if cur: lines.append(cur)
    return lines

def card(spec, out):
    items = spec.get("items", [])
    W = 1200; PAD = 130; maxw = W - 2 * PAD - 40
    bg, fg, acc, sub, _ = THEMES.get(spec.get("theme", "light"), THEMES["light"])
    tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    rows = []
    for it in items:
        head, _, tail = it.partition("|")
        f = font("Bold", 54)
        hl = wrap(tmp, head.strip(), f, maxw)
        tl = wrap(tmp, tail.strip(), font("Medium", 40), maxw) if tail.strip() else []
        rows.append((hl, tl, 50 + 70 * len(hl) + 56 * len(tl)))
    H = 190 + sum(r[2] + 25 for r in rows) + 50
    im = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(im)
    tf = fit(d, spec["title"], "Black", 62, W - 2 * PAD)
    center(d, 55, spec["title"], tf, acc if bg != "#FFFFFF" else fg, W)
    y = 170
    box = "#F5F6F8" if bg == "#FFFFFF" else None
    for hl, tl, h in rows:
        if box:
            d.rounded_rectangle([PAD - 40, y, W - PAD + 40, y + h], radius=26, fill=box)
            d.rounded_rectangle([PAD - 40, y, PAD - 22, y + h], radius=9, fill=acc)
        ty = y + 28
        for l in hl:
            d.text((PAD, ty), l, font=font("Bold", 54), fill=(acc if tl and box else (fg if not box else "#111111")))
            ty += 70
        for l in tl:
            d.text((PAD, ty), l, font=font("Medium", 40), fill=(sub if not box else "#333333"))
            ty += 56
        y += h + 25
    im.save(out, quality=86, optimize=True)

if __name__ == "__main__":
    folder = Path(sys.argv[1])
    spec = json.loads((folder / "images.json").read_text(encoding="utf-8"))
    thumb(spec["thumb"], folder / "thumb.jpg")
    for i, c in enumerate(spec.get("cards", []), 1):
        card(c, folder / f"img{i}.jpg")
    (folder / "images.json").unlink()
    print("이미지 생성 완료:", sorted(p.name for p in folder.glob("*.jpg")))
