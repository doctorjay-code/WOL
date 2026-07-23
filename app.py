import os
import re
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from iptime_wol import send_iptime_wol

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WOL-SlackBot")

# 환경변수 로드 (.env 파일이 있으면 읽어옴)
load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
ALLOWED_SLACK_USER_ID = os.environ.get("ALLOWED_SLACK_USER_ID")

IPTIME_URL = os.environ.get("IPTIME_URL")
IPTIME_USER = os.environ.get("IPTIME_USER")
IPTIME_PASS = os.environ.get("IPTIME_PASS")

# 타겟 PC의 진짜 실물 LAN 랜카드 MAC 주소
TARGET_MAC = "0C-9D-92-62-81-1D"

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    logger.error("필수 슬랙 토큰(SLACK_BOT_TOKEN, SLACK_APP_TOKEN)이 설정되지 않았습니다.")

app = App(token=SLACK_BOT_TOKEN)

# Render Web Service 포트 바인딩용 미니 HTTP 서버 (Render 포트 스캔 즉시 통과용)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("ipTime WOL Slack Bot is Running Live!".encode('utf-8'))

    def log_message(self, format, *args):
        pass

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"🌐 Render 포트 감지용 웹서버 시작 (Port: {port})")
    server.serve_forever()

def is_authorized(user_id: str) -> bool:
    """보안검사: 특정 사용자만 컴퓨터를 켤 수 있도록 제한 (설정된 경우)"""
    if not ALLOWED_SLACK_USER_ID:
        return True
    return user_id == ALLOWED_SLACK_USER_ID

@app.message(re.compile(r"(컴터|컴퓨터|pc|PC|피씨|컴).*(켜|부팅)"))
def handle_turn_on_pc(message, say):
    # 봇 메시지 및 서브타입 메시지 무시 (중복 실행 방지)
    if message.get("bot_id") or message.get("subtype") in ["bot_message", "message_changed", "channel_join"]:
        return

    user_id = message.get("user")
    user_text = message.get("text", "")

    logger.info(f"사용자({user_id})로부터 컴터 켜기 요청 수신: '{user_text}'")

    if not is_authorized(user_id):
        say(f"⚠️ <@{user_id}>님은 컴퓨터 전원 명령 권한이 없습니다.")
        return

    # 슬랙 타임아웃(3초) 재시도 및 중복 메시지 전송 방지를 위해 먼저 즉시 1회 답변 전송
    say(f"🤖 <@{user_id}>님의 요청을 확인했습니다. ipTime 공유기를 통해 컴퓨터 부팅(WOL) 명령을 전송합니다...")

    # 백그라운드 쓰레드에서 WOL 발송 처리 (진짜 랜카드 MAC 0C-9D-92-62-81-1D 및 70-5D-CC-99-BF-7A 동시 타격)
    def async_wol():
        target_macs = ["0C-9D-92-62-81-1D", "70-5D-CC-99-BF-7A"]
        success_macs = []

        for mac in target_macs:
            success, _ = send_iptime_wol(
                iptime_url=IPTIME_URL,
                username=IPTIME_USER,
                password=IPTIME_PASS,
                target_mac=mac
            )
            if success:
                success_macs.append(mac)

        if success_macs:
            say(f"✅ **부팅 명령 성공!**\nipTime 공유기를 통해 타겟 컴퓨터(MAC: `{', '.join(success_macs)}`)에 WOL 켜기 명령을 보냈습니다!\n잠시 후 윈도우가 부팅됩니다. 💻")
        else:
            say(f"❌ **부팅 명령 실패**\nipTime 설정(DDNS 주소, 원격포트, 비밀번호)을 확인해 주세요.")

    threading.Thread(target=async_wol, daemon=True).start()

if __name__ == "__main__":
    threading.Thread(target=start_health_check_server, daemon=True).start()
    
    logger.info("⚡ Slack Bot (Socket Mode) 시작 중...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
