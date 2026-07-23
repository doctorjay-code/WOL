import os
import re
import json
import subprocess
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WOL-LocalAgent")

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

@app.message(re.compile(r"(박주하|박범준|닥터빌|파일|실행|열어줘|꺼줘|종료)"))
def handle_pc_commands(message, say):
    text = message.get("text", "")
    user_id = message.get("user")
    commands = load_commands()

    logger.info(f"로컬 에이전트 명령 수신: '{text}' (유저: {user_id})")

    # 1. 윈도우 원격 종료 처리
    if "꺼줘" in text or "종료" in text:
        say("🖥️ **윈도우 종료 명령을 수신했습니다.** 10초 후 컴퓨터가 안전하게 종료됩니다.")
        os.system("shutdown /s /t 10")
        return

    # 2. 등록된 파일/그룹 실행 처리
    executed = False
    for name, paths in commands.items():
        if name in text:
            if isinstance(paths, str):
                paths = [paths]
            
            say(f"🚀 **`{name}` (총 {len(paths)}개 파일) 실행을 시작합니다!**")
            
            for path in paths:
                if os.path.exists(path):
                    say(f"▶️ 실행 중: `{path}`")
                    try:
                        subprocess.Popen(f'"{path}"', shell=True)
                    except Exception as e:
                        say(f"❌ 실행 실패 (`{path}`): {e}")
                else:
                    say(f"⚠️ 파일 경로를 찾을 수 없습니다: `{path}`")
            
            executed = True
            break

    # 3. 도움말 / 목록 안내
    if not executed or "목록" in text or "도움말" in text:
        file_list = []
        for key, val in commands.items():
            paths_str = ", ".join(val) if isinstance(val, list) else val
            file_list.append(f"• `{key}` ➔ `{paths_str}`")
        
        help_msg = (
            f"📋 **현재 등록된 파일/그룹 목록:**\n" + "\n".join(file_list) + "\n\n"
            f"**사용 가능한 명령어 예시:**\n"
            f"• `닥터빌 켜줘` ➔ **박주하 + 박범준 닥터빌 두 파일 모두 실행** 🚀\n"
            f"• `박주하 켜줘` ➔ 박주하_닥터빌.bat 개별 실행\n"
            f"• `박범준 켜줘` ➔ 박범준_닥터빌.bat 개별 실행\n"
            f"• `컴터 꺼줘` ➔ 윈도우 원격 종료"
        )
        say(help_msg)

if __name__ == "__main__":
    logger.info("🖥️ 윈도우 로컬 PC 에이전트 시작 중...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
