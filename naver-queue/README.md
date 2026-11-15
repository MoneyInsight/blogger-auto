# 네이버 반자동 임시저장 큐 (soomnbreath)
- 폴더명 `naver-queue/soomnbreath/YYYYMMDD-HH/` (KST 정각) → PC 프로그램이 그 시각이 되면 내려받아 네이버 임시저장
- 각 폴더: post.json, thumb.jpg, img1.jpg (선택 img2.jpg)
- post.json 키: label, title, thumb, images, tags, html (소제목 h3 다음 <p><br></p> 한 줄 띄우기, 본문 링크 없음)
- 발행 시각: 06 07 08 11 12 13 15 17 19 20 21시
- 카드 이미지: python3 naver-queue/make_card.py out.jpg "줄1|줄2|줄3" "하단문구"
