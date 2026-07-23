import os
import re
import json
import time
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WOL-LocalAgent")

# 에이전트 시작 시각 기록 (부팅 전 쌓여있던 옛날 슬랙 메시지 실행 방지용)
BOT_START_TIME = time.time()

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

COMMANDS_FILE = os.path.join(os.path.dirname(__file__), "commands.json")

def load_commands() -> dict:
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"commands.json 로드 에러: {e}")
    return {}

app = App(token=SLACK_BOT_TOKEN)

@app.message(re.compile(r"(박주하|박범준|닥터빌|파일|실행|열어줘|꺼줘|종료|목록|도움말)"))
def handle_pc_commands(message, say):
    # 1. 봇 메시지 무시
    if message.get("bot_id") or message.get("subtype") in ["bot_message", "message_changed", "channel_join"]:
        return

    # 2. 부팅 전에 슬랙에 올라왔던 옛날 큐 메시지 무시
    msg_ts = float(message.get("ts", 0))
    if msg_ts < (BOT_START_TIME - 5.0):
        logger.info(f"부팅 전 쌓여있던 이전 메시지 무시됨 (ts: {msg_ts})")
        return

    text = message.get("text", "")
    user_id = message.get("user")
    commands = load_commands()

    logger.info(f"로컬 에이전트 사용자 명령 수신: '{text}' (유저: {user_id})")

    # 3. 윈도우 원격 절전 모드 처리 (옵션 A: WOL 100% 보장 및 2초 부팅)
    if "꺼줘" in text or "종료" in text:
        say("🌙 **윈도우 절전 모드(Sleep)를 실행합니다.** 3초 후 컴퓨터가 절전 상태로 들어갑니다. (나중에 슬랙 '컴터 켜줘' 입력 시 2초 만에 즉시 부팅됩니다!)")
        time.sleep(3)
        os.system('powershell -command "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState(\'Suspend\', $false, $false)"')
        return

    # 4. 등록된 파일/그룹 실행 처리
    for name, paths in commands.items():
        if name in text:
            if isinstance(paths, str):
                paths = [paths]
            
            say(f"🚀 **`{name}` (총 {len(paths)}개 파일) 실행을 시작합니다!**")
            
            for path in paths:
                if os.path.exists(path):
                    say(f"▶️ 실행 중: `{path}`")
                    try:
                        file_dir = os.path.dirname(path)
                        original_dir = os.getcwd()
                        try:
                            os.chdir(file_dir)
                            os.startfile(path)
                        finally:
                            os.chdir(original_dir)
                    except Exception as e:
                        say(f"❌ 실행 실패 (`{path}`): {e}")
                else:
                    say(f"⚠️ 파일 경로를 찾을 수 없습니다: `{path}`")
            return

    # 5. 명시적 도움말
    if "목록" in text or "도움말" in text:
        file_list = [f"• `{key}` ➔ `{val}`" for key, val in commands.items()]
        say("📋 **등록된 명령어 목록:**\n" + "\n".join(file_list))

if __name__ == "__main__":
    logger.info("🖥️ 윈도우 로컬 PC 에이전트 시작 중...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
