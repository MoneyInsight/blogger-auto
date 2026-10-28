"""
제목 후킹 검사기 — 발행 전에 반드시 통과해야 함.
사용: python tools/check_title.py "제목" "메인 키워드"
통과하면 'PASS', 아니면 고칠 점을 출력하고 종료코드 1.
"""
import re, sys

EMOTION = ["털린", "털릴", "놓쳤", "놓친", "날린", "날릴", "싹둑", "뚝", "확", "역전", "폭탄", "함정",
           "후회", "결국", "경고", "몰랐", "충격", "급등", "급락", "비상", "위험", "손해", "독", "주의"]
TARGET = ["라면", "이라면", "있다면", "했다면", "샀다면", "중이라면", "한다면", "먹는다면", "쓴다면",
          "직장인", "부모님", "40대", "50대", "30대", "20대", "60대", "주부", "자녀", "아이", "무주택", "집주인", "세입자",
          "아이폰", "갤럭시", "유저", "사용자", "개발자", "쓰는 사람", "깔았다면", "바꿨다면", "켜 뒀다면"]
PUNCH = {
    "손해회피": ["손해", "날린", "털", "놓친", "놓쳤", "후회"],
    "반전": ["오히려", "반전", "알고 보니", "그런데", "의외"],
    "궁금증": ["?", "이유", "1위", "정체", "비밀"],
    "경고": ["절대", "하지 마", "속지 마", "경고", "주의"],
    "마감": ["까지", "D-", "마감", "오늘", "이번 주", "당장"],
    "비교": [" vs ", "VS", "보다", "차이"],
    "나만몰랐다": ["벌써", "남들은", "나만", "몰랐"],
}
BAD_TAIL = ["정리", "알아보기", "알아보자", "의미", "결과", "확인", "방법", "총정리", "가이드", "체크리스트", "꿀팁", "해야 할 일"]

def check(title, kw):
    issues, score = [], 0
    n = len(title)
    if 35 <= n <= 55: score += 1
    else: issues.append(f"길이 {n}자 → 35~55자로")
    head = title[:15]
    if kw and kw.replace(" ", "")[:4] in head.replace(" ", ""): score += 1
    else: issues.append(f"앞 15자('{head}')에 메인 키워드 '{kw}'를 넣기")
    if re.search(r"\d", head): score += 1
    else: issues.append("앞 15자 안에 가장 센 숫자 넣기")
    if any(t in title for t in TARGET): score += 1
    else: issues.append("대상 지목 넣기 (예: '○○ 있다면', '직장인이라면', '부모님이 ○○한다면')")
    if any(e in title for e in EMOTION): score += 1
    else: issues.append("감정 단어 1개 이상 (털린다·놓쳤다·날린다·폭탄·함정·후회·결국·경고·몰랐다 등)")
    hit = [k for k, ws in PUNCH.items() if any(w in title for w in ws)]
    if re.search(r"\d+(\.\d+)?\s*(%|배|만|억|원|공기|개월|년|위|명|kg|kcal)", title): hit.append("숫자충격")
    if len(hit) >= 2: score += 1
    else: issues.append(f"펀치 공식 2개 이상 겹치기 (지금: {hit or '없음'}) — 손해회피/반전/궁금증/경고/마감/비교/나만몰랐다")
    tail = title.rstrip(" ?!.…")[-6:]
    if not any(b in tail for b in BAD_TAIL) and title.rstrip()[-1:] in "?!…" or any(x in title[-8:] for x in ["이유는", "1위", "결국", "의외", "뒤집", "폭탄", "함정", "무섭", "위험", "끝났", "사라진", "터진", "날린다", "털린다", "놓쳤다"]):
        score += 1
    else: issues.append("끝을 궁금증·충격으로 끊기 ('…이유는?', '…1위는 의외', '…결국 ○○'), 설명형 꼬리 금지")
    return score, issues

if __name__ == "__main__":
    title = sys.argv[1]; kw = sys.argv[2] if len(sys.argv) > 2 else ""
    score, issues = check(title, kw)
    if score >= 7:
        print(f"PASS ({score}/7)"); sys.exit(0)
    print(f"FAIL ({score}/7) — 제목을 다시 써서 재검사:")
    for i in issues: print(" -", i)
    sys.exit(1)
