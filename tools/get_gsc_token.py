"""
구글 서치콘솔 '사이트맵 재제출' 권한 열쇠(GSC_REFRESH_TOKEN) 만들기 — 내 PC에서 한 번만 실행
(파이썬만 있으면 됨. 추가 설치 없음)

윈도우 실행 방법
  1) 명령 프롬프트(cmd)에서:  python get_gsc_token.py
  2) 블로거 발행에 쓰는 OAuth 클라이언트 ID / 보안 비밀번호를 붙여넣기
  3) 브라우저가 열리면 메인 구글 계정(durion0506)으로 로그인 → 허용
  4) 화면에 나온 긴 값을 GitHub 저장소 Settings > Secrets > Actions 에
     이름 GSC_REFRESH_TOKEN 으로 저장
  5) (IT 계정 블로그도 점검하려면) 한 번 더 실행해서 IT 계정으로 로그인 →
     값을 GSC_IT_REFRESH_TOKEN 이름으로 저장

이 열쇠로 하는 일: 사이트맵 재제출(index_ping.py) + 매일 색인 여부 점검(index_check.py)

※ OAuth 클라이언트 유형이 '데스크톱 앱'이어야 합니다.
※ 구글 클라우드 콘솔에서 'Google Search Console API'를 '사용'으로 켜 두세요.
"""

import json
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"
SCOPES = "https://www.googleapis.com/auth/webmasters https://www.googleapis.com/auth/blogger"

client_id = input("OAuth 클라이언트 ID: ").strip()
client_secret = input("OAuth 클라이언트 보안 비밀번호: ").strip()
state = secrets.token_urlsafe(16)

auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
    "scope": SCOPES, "access_type": "offline", "prompt": "consent", "state": state,
})

code_box = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if q.get("state", [""])[0] == state and "code" in q:
            code_box["code"] = q["code"][0]
            msg = "완료! 이 창을 닫고 명령 프롬프트로 돌아가세요."
        else:
            msg = "실패: " + q.get("error", ["알 수 없음"])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<h2>{msg}</h2>".encode("utf-8"))

    def log_message(self, *a):
        pass


print("\n브라우저에서 구글 로그인 후 '허용'을 눌러 주세요...")
webbrowser.open(auth_url)
print("(브라우저가 안 열리면 아래 주소를 복사해서 여세요)\n" + auth_url + "\n")
server = HTTPServer(("127.0.0.1", PORT), Handler)
while "code" not in code_box:
    server.handle_request()

data = urllib.parse.urlencode({
    "code": code_box["code"], "client_id": client_id, "client_secret": client_secret,
    "redirect_uri": REDIRECT, "grant_type": "authorization_code",
}).encode()
res = json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data).read())

print("\n아래 값을 GitHub Secrets 에 GSC_REFRESH_TOKEN 이름으로 저장하세요:\n")
print(res.get("refresh_token", "(refresh_token 없음 — 다시 실행해 주세요) " + json.dumps(res)))
input("\n엔터를 누르면 종료합니다.")
