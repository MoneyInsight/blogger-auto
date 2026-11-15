# 사용법: python3 make_card.py 출력파일.jpg "줄1|줄2|줄3" "하단 문구" [스타일번호]
# 네이버용 1080x1080 고급형 카드. 스타일번호 생략 시 무작위 (매번 다른 디자인)
import sys, random
from PIL import Image, ImageDraw, ImageFont
F = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
STYLES = [  # 배경, 포인트, 글자, 보조
    ('#0f1b2d', '#e8c46a', '#ffffff', '#c9c9c9'), ('#1b1b1b', '#d4af37', '#f5f5f5', '#aaaaaa'),
    ('#f7f1e6', '#8b5e34', '#2b2118', '#6d5c4b'), ('#0b3d2e', '#f2d27a', '#ffffff', '#cfe3da'),
    ('#2a0f1f', '#ff9eb5', '#ffffff', '#e0c3cd'), ('#ffffff', '#1e40af', '#111827', '#4b5563'),
    ('#111827', '#38bdf8', '#ffffff', '#9ca3af'), ('#3b0764', '#fbbf24', '#ffffff', '#ddd6fe'),
]
out, lines, sub = sys.argv[1], sys.argv[2].split('|'), sys.argv[3]
st = STYLES[int(sys.argv[4]) % len(STYLES)] if len(sys.argv) > 4 else random.choice(STYLES)
bg, acc, fg, sb = st
im = Image.new('RGB', (1080, 1080), bg); d = ImageDraw.Draw(im)
lay = random.randint(0, 2)
if lay == 0: d.rectangle([60, 60, 1020, 1020], outline=acc, width=6)
elif lay == 1: d.rectangle([0, 0, 1080, 28], fill=acc); d.rectangle([0, 1052, 1080, 1080], fill=acc)
else: d.rectangle([90, 250, 104, 830], fill=acc)
size = 104 if max(len(l) for l in lines) <= 7 else 86
f = ImageFont.truetype(F, size, index=1); s = ImageFont.truetype(F, 42, index=1)
y = 540 - len(lines) * (size + 30) // 2 - 40
for i, l in enumerate(lines):
    w = d.textlength(l, font=f)
    x = (1080 - w) / 2 if lay != 2 else 150
    d.text((x, y), l, font=f, fill=acc if i == 1 else fg); y += size + 30
w = d.textlength(sub, font=s)
d.text(((1080 - w) / 2 if lay != 2 else 150, 840), sub, font=s, fill=sb)
im.save(out, quality=85, optimize=True)
