import os
import re
import json
import time
import logging
import threading
import socket
import winreg
from dotenv import load_dotenv
from slack_sdk import WebClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WOL-LocalAgent")

load_dotenv()

SLACK_BOT_TOKEN  = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL    = os.environ.get("SLACK_NOTIFY_CHANNEL", "C0BKDHNLATE")
WINDOWS_USERNAME = os.environ.get("WINDOWS_USERNAME", "")
WINDOWS_PASSWORD = os.environ.get("WINDOWS_PASSWORD", "")

CHANNEL_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".last_channel")
COMMANDS_FILE      = os.path.join(os.path.dirname(__file__), "commands.json")
WINLOGON_KEY       = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

BOT_START_TIME = time.time()
client = WebClient(token=SLACK_BOT_TOKEN)

# ─────────────────────────────────────────────
# 채널 캐시
# ─────────────────────────────────────────────

def load_last_channel() -> str:
    if os.path.exists(CHANNEL_CACHE_FILE):
        try:
            return open(CHANNEL_CACHE_FILE).read().strip()
        except Exception:
            pass
    return SLACK_CHANNEL

def save_last_channel(ch: str):
    try:
        open(CHANNEL_CACHE_FILE, 'w').write(ch)
    except Exception:
        pass

# ─────────────────────────────────────────────
# 자동 로그인 레지스트리
# ─────────────────────────────────────────────

def set_autologin_on() -> bool:
    if not WINDOWS_USERNAME or not WINDOWS_PASSWORD or "여기에_" in WINDOWS_PASSWORD:
        logger.warning("[AutoLogin] WINDOWS_PASSWORD 미설정 — 자동 로그인 생략")
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WINLOGON_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "AutoAdminLogon",  0, winreg.REG_SZ, "1")
            winreg.SetValueEx(k, "DefaultUserName", 0, winreg.REG_SZ, WINDOWS_USERNAME)
            winreg.SetValueEx(k, "DefaultPassword", 0, winreg.REG_SZ, WINDOWS_PASSWORD)
            winreg.SetValueEx(k, "AutoLogonCount",  0, winreg.REG_SZ, "1")
        logger.info("[AutoLogin] 자동 로그인 ON (다음 부팅 1회)")
        return True
    except PermissionError:
        logger.error("[AutoLogin] 권한 없음 — 관리자 권한 필요")
        return False
    except Exception as e:
        logger.error(f"[AutoLogin] 실패: {e}")
        return False

def clear_autologin():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WINLOGON_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "AutoAdminLogon", 0, winreg.REG_SZ, "0")
            for v in ("DefaultPassword", "AutoLogonCount"):
                try: winreg.DeleteValue(k, v)
                except FileNotFoundError: pass
        logger.info("[AutoLogin] 자동 로그인 OFF — 레지스트리 정리")
    except Exception as e:
        logger.error(f"[AutoLogin] 정리 실패: {e}")

# ─────────────────────────────────────────────
# 슬랙 전송
# ─────────────────────────────────────────────

def say(channel: str, text: str):
    try:
        client.chat_postMessage(channel=channel, text=text)
    except Exception as e:
        logger.error(f"슬랙 전송 실패: {e}")

def send_boot_notification():
    time.sleep(2)
    ch = load_last_channel()
    hostname = socket.gethostname()
    say(ch,
        f"\U0001f7e2 *PC 부팅 완료!*\n"
        f"\u2022 호스트명: `{hostname}`\n"
        f"\u2022 로컬 에이전트 시작됨 — 명령 대기 중\n"
        f"\u2022 도움말: `도움말`"
    )
    logger.info(f"부팅 알림 전송 완료 ({ch})")

# ─────────────────────────────────────────────
# 명령 처리
# ─────────────────────────────────────────────

def load_commands() -> dict:
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"commands.json 로드 에러: {e}")
    return {}

def handle_message(text: str, channel: str):
    save_last_channel(channel)
    commands = load_commands()
    logger.info(f"명령 처리: '{text}'")

    # 절전/종료
    if "꺼줘" in text or "종료" in text:
        autologin_ok = set_autologin_on()
        if autologin_ok:
            say(channel,
                "\U0001f319 *절전 모드로 전환합니다.*\n"
                "\u2022 3초 후 절전 상태로 들어갑니다.\n"
                "\u2022 다음 WOL 부팅 시 PIN 없이 자동 로그인됩니다. \U0001f511\u2192\U0001f513"
            )
        else:
            say(channel,
                "\U0001f319 *절전 모드로 전환합니다.*\n"
                "\u2022 3초 후 절전 상태로 들어갑니다."
            )
        def do_sleep():
            time.sleep(3)
            os.system('powershell -command "Add-Type -Assembly System.Windows.Forms; '
                      '[System.Windows.Forms.Application]::SetSuspendState(\'Suspend\', $false, $false)"')
        threading.Thread(target=do_sleep, daemon=True).start()
        return

    # 등록된 파일 실행
    for name, paths in commands.items():
        if name in text:
            if isinstance(paths, str):
                paths = [paths]
            say(channel, f"\U0001f680 *`{name}` ({len(paths)}개 파일) 실행 시작!*")
            for path in paths:
                if os.path.exists(path):
                    say(channel, f"\u25b6\ufe0f 실행 중: `{path}`")
                    try:
                        file_dir = os.path.dirname(path)
                        orig = os.getcwd()
                        try:
                            os.chdir(file_dir)
                            os.startfile(path)
                        finally:
                            os.chdir(orig)
                    except Exception as e:
                        say(channel, f"\u274c 실행 실패 (`{path}`): {e}")
                else:
                    say(channel, f"\u26a0\ufe0f 파일 없음: `{path}`")
            return

    # 도움말
    if "목록" in text or "도움말" in text:
        items = [f"\u2022 `{k}` \u27a1\ufe0f `{v}`" for k, v in commands.items()]
        say(channel, "\U0001f4cb *등록된 명령어:*\n" + "\n".join(items) +
            "\n\u2022 `꺼줘` \u27a1\ufe0f 절전 모드")

# ─────────────────────────────────────────────
# 슬랙 폴링 루프 (Socket Mode 대신 사용 — Render 봇과 충돌 없음)
# ─────────────────────────────────────────────

LOCAL_KEYWORDS = re.compile(r"(박주하|박범준|닥터빌|파일|실행|열어줘|꺼줘|종료|목록|도움말)")

def polling_loop():
    """
    Slack conversations.history API로 채널을 주기적으로 폴링.
    Socket Mode와 달리 Render 봇과 메시지 경쟁이 없음.
    """
    channel = load_last_channel()
    # 시작 시점 이후 메시지만 처리
    last_ts = str(BOT_START_TIME)
    logger.info(f"폴링 시작 (channel: {channel}, since: {last_ts})")

    while True:
        try:
            resp = client.conversations_history(
                channel=channel,
                oldest=last_ts,
                limit=10
            )
            messages = resp.get("messages", [])
            # 오래된 것부터 처리
            for msg in reversed(messages):
                ts  = msg.get("ts", "0")
                if float(ts) <= float(last_ts):
                    continue
                # 봇 메시지 무시
                if msg.get("bot_id") or msg.get("subtype"):
                    last_ts = ts
                    continue
                text = msg.get("text", "")
                if LOCAL_KEYWORDS.search(text):
                    logger.info(f"메시지 수신: '{text}' (ts={ts})")
                    handle_message(text, channel)
                last_ts = ts
        except Exception as e:
            logger.error(f"폴링 오류: {e}")

        time.sleep(2)  # 2초마다 폴링

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("\U0001f5a5\ufe0f 윈도우 로컬 PC 에이전트 시작 (폴링 모드)...")

    clear_autologin()
    threading.Thread(target=send_boot_notification, daemon=True).start()
    polling_loop()  # 메인 스레드에서 폴링
