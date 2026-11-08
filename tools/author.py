"""글 끝 '글쓴이 Evan' 소개 상자. publish.py(새 글·수정)와 bulk_fix.py(기존 글)가 사용한다."""
RAW = "https://raw.githubusercontent.com/MoneyInsight/blogger-auto/main/assets/author/{}.png"
P = "온라인 쇼핑몰을 운영하는 1인 사업자이자 두 아이 아빠다."
INTRO = {
    "main": "온라인 쇼핑몰을 운영하는 1인 사업자이자 두 아이 아빠입니다. 세금·통장·저축처럼 직접 부딪히는 돈 문제를 국세청·금융감독원 같은 공식 자료로 확인해 정리합니다.",
    "car": P + " 차량 관리와 운전·자동차 행정을 공공기관 안내로 확인해 정리한다.",
    "life": P + " 집안일과 생활비 고민을 공식 안내와 제품 설명서로 확인해 정리한다.",
    "ittech": P + " 업무에 쓰는 PC·보안·AI 도구를 공식 문서로 확인해 정리한다.",
    "it": P + " 스마트폰·앱·통신 문제를 제조사와 공식 안내로 확인해 정리한다.",
    "edu": P + " 부모가 자주 고민하는 육아·교육 문제를 공식 자료와 함께 정리한다.",
    "welfare": P + " 지금 신청할 수 있는 정부지원·복지 제도를 정부 공식 공고로 확인해 정리한다.",
    "health": P + " 일상 건강 습관을 질병관리청·식약처 같은 공식 기준으로 확인해 정리한다. 의료인이 아니므로 진단과 치료는 전문의와 상담하길 권한다.",
}
BY_URL = {"durion0506": "main", "cardurion": "car", "lifetipdurion": "life", "ittechdurion0506": "ittech",
          "itdigitaldream": "it", "bestbabyeducation": "edu", "govermentnwelfare": "welfare", "goodwellbeinghealth": "health"}


def box(blog):
    blog = blog if blog in INTRO else "main"
    return ('<div class="author-box" style="display:flex;gap:14px;align-items:center;border:1px solid #e6e8eb;'
            'border-radius:12px;padding:14px 16px;margin:28px 0 8px;">'
            f'<img class="author-avatar" src="{RAW.format(blog)}" alt="글쓴이 Evan" width="64" height="64" '
            'style="width:64px;height:64px;max-width:64px;border-radius:50%;flex:none;margin:0;" />'
            '<div><p style="margin:0;font-weight:700;">글쓴이 Evan</p>'
            f'<p style="margin:4px 0 0;font-size:14px;color:#555;line-height:1.6;">{INTRO[blog]}</p></div></div>')


def add(html, blog):
    if "author-box" in html:
        return html
    return html.rstrip() + "\n" + box(blog)
