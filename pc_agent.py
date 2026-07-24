import os
import re
import json
import time
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
COMMANDS_FILE   = os.path.join(os.path.dirname(__file__), "commands.json")

app = App(token=SLACK_BOT_TOKEN)

def load_commands() -> dict:
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

@app.message(re.compile(r".*"))
def handle_messages(message, say):
    # 봇 자신의 메시지는 무시
    if message.get("bot_id") or message.get("subtype"):
        return

    text = message.get("text", "").strip()
    commands = load_commands()

    # 1. PC 절전 (꺼줘 / 꺼 / 종료)
    if any(k in text for k in ["꺼줘", "종료", "꺼"]):
        say("🌙 *3초 후 윈도우 절전 모드를 실행합니다.*")
        time.sleep(3)
        os.system('powershell -command "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState(\'Suspend\', $false, $false)"')
        return

    # 2. 등록된 배치파일/프로그램 실행
    for name, paths in commands.items():
        if name in text:
            if isinstance(paths, str):
                paths = [paths]
            say(f"🚀 *`{name}` ({len(paths)}개 파일) 실행 시작!*")
            for path in paths:
                if os.path.exists(path):
                    say(f"▶️ 실행: `{path}`")
                    file_dir = os.path.dirname(path)
                    orig_dir = os.getcwd()
                    try:
                        os.chdir(file_dir)
                        os.startfile(path)
                    finally:
                        os.chdir(orig_dir)
                else:
                    say(f"⚠️ 파일 없음: `{path}`")
            return

    # 3. 목록 / 도움말
    if "목록" in text or "도움말" in text:
        items = [f"• `{k}` ➔ `{v}`" for k, v in commands.items()]
        say("📋 *등록된 명령어 목록:*\n" + "\n".join(items) + "\n• `꺼줘` / `꺼` ➔ 절전 모드")

if __name__ == "__main__":
    print("[INFO] Slack Local PC Agent Starting...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
