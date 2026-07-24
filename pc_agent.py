import os
import re
import json
import time
import logging
import threading
import socket
import winreg
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WOL-LocalAgent")

# 에이전트 시작 시각 기록 (부팅 전 쌓여있던 옛날 슬랙 메시지 실행 방지용)
BOT_START_TIME = time.time()

load_dotenv()

SLACK_BOT_TOKEN   = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN   = os.environ.get("SLACK_APP_TOKEN")
WINDOWS_USERNAME  = os.environ.get("WINDOWS_USERNAME", "")
WINDOWS_PASSWORD  = os.environ.get("WINDOWS_PASSWORD", "")

CHANNEL_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".last_channel")
COMMANDS_FILE      = os.path.join(os.path.dirname(__file__), "commands.json")
WINLOGON_KEY       = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

# ─────────────────────────────────────────────
# 자동 로그인 레지스트리 헬퍼
# ─────────────────────────────────────────────

def set_autologin_on():
    """
    레지스트리에 자동 로그인 플래그를 설정합니다.
    WOL로 PC가 켜지면 PIN 없이 자동으로 로그인됩니다.
    (절전/종료 명령 직전에 호출)
    """
    if not WINDOWS_USERNAME or not WINDOWS_PASSWORD or "여기에_" in WINDOWS_PASSWORD:
        logger.warning("[AutoLogin] WINDOWS_USERNAME/PASSWORD가 .env에 설정되지 않아 자동 로그인 생략")
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WINLOGON_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AutoAdminLogon",   0, winreg.REG_SZ, "1")
            winreg.SetValueEx(key, "DefaultUserName",  0, winreg.REG_SZ, WINDOWS_USERNAME)
            winreg.SetValueEx(key, "DefaultPassword",  0, winreg.REG_SZ, WINDOWS_PASSWORD)
            # 딱 1회만 자동 로그인 (AutoLogonCount=1 → 소진 후 자동으로 비활성화됨)
            winreg.SetValueEx(key, "AutoLogonCount",   0, winreg.REG_SZ, "1")
        logger.info("[AutoLogin] 자동 로그인 ON (다음 부팅 1회만)")
        return True
    except PermissionError:
        logger.error("[AutoLogin] 레지스트리 쓰기 권한 없음 — 관리자 권한으로 실행해야 합니다")
        return False
    except Exception as e:
        logger.error(f"[AutoLogin] 설정 실패: {e}")
        return False

def clear_autologin():
    """
    레지스트리에서 자동 로그인 정보를 제거합니다.
    pc_agent 시작 시 호출하여 보안을 복구합니다.
    (AutoLogonCount=1 설정으로 Windows가 자동 제거하지만, 이중 보호)
    """
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WINLOGON_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AutoAdminLogon",  0, winreg.REG_SZ, "0")
            # DefaultPassword 삭제 (민감 정보 즉시 제거)
            try:
                winreg.DeleteValue(key, "DefaultPassword")
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteValue(key, "AutoLogonCount")
            except FileNotFoundError:
                pass
        logger.info("[AutoLogin] 자동 로그인 OFF — 레지스트리 정리 완료")
    except PermissionError:
        logger.error("[AutoLogin] 레지스트리 정리 권한 없음 — 관리자 권한 필요")
    except Exception as e:
        logger.error(f"[AutoLogin] 정리 실패: {e}")

# ─────────────────────────────────────────────
# 채널 캐시 헬퍼
# ─────────────────────────────────────────────

def load_commands() -> dict:
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"commands.json 로드 에러: {e}")
    return {}

def save_last_channel(channel_id: str):
    try:
        with open(CHANNEL_CACHE_FILE, 'w') as f:
            f.write(channel_id)
    except Exception:
        pass

def load_last_channel() -> str | None:
    if os.path.exists(CHANNEL_CACHE_FILE):
        try:
            with open(CHANNEL_CACHE_FILE, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return os.environ.get("SLACK_NOTIFY_CHANNEL")

# ─────────────────────────────────────────────
# 부팅 완료 슬랙 알림
# ─────────────────────────────────────────────

def send_boot_notification():
    """PC 부팅 완료 시 슬랙 알림 전송 (소켓 연결 완료 대기 후)"""
    time.sleep(3)
    channel = load_last_channel()
    if not channel:
        logger.warning("부팅 알림: 저장된 채널 없음 — 생략")
        return
    try:
        hostname = socket.gethostname()
        client = WebClient(token=SLACK_BOT_TOKEN)
        client.chat_postMessage(
            channel=channel,
            text=(
                f"\U0001f7e2 *PC 부팅 완료!*\n"
                f"\u2022 호스트명: `{hostname}`\n"
                f"\u2022 로컬 에이전트가 정상 시작되었습니다.\n"
                f"\u2022 이제 명령을 입력하실 수 있습니다. (도움말: `도움말`)"
            )
        )
        logger.info(f"슬랙 부팅 완료 알림 전송 성공 (channel: {channel})")
    except Exception as e:
        logger.error(f"슬랙 부팅 완료 알림 전송 실패: {e}")

# ─────────────────────────────────────────────
# Slack 봇
# ─────────────────────────────────────────────

app = App(token=SLACK_BOT_TOKEN)

@app.message(re.compile(r"(박주하|박범준|닥터빌|파일|실행|열어줘|꺼줘|종료|목록|도움말)"))
def handle_pc_commands(message, say):
    # 1. 봇 메시지 무시
    if message.get("bot_id") or message.get("subtype") in ["bot_message", "message_changed", "channel_join"]:
        return

    # 2. 부팅 전 쌓인 이전 메시지 무시
    msg_ts = float(message.get("ts", 0))
    if msg_ts < (BOT_START_TIME - 5.0):
        logger.info(f"이전 메시지 무시 (ts: {msg_ts})")
        return

    text       = message.get("text", "")
    user_id    = message.get("user")
    channel_id = message.get("channel")
    commands   = load_commands()

    if channel_id:
        save_last_channel(channel_id)

    logger.info(f"명령 수신: '{text}' (유저: {user_id})")

    # 3. 절전/종료 처리
    if "꺼줘" in text or "종료" in text:
        autologin_ok = set_autologin_on()

        if autologin_ok:
            say(
                "\U0001f319 *절전 모드로 전환합니다.*\n"
                "\u2022 3초 후 절전 상태로 들어갑니다.\n"
                "\u2022 다음에 슬랙으로 켤 때 PIN 없이 자동 로그인됩니다. \U0001f511\u2192\U0001f513"
            )
        else:
            say(
                "\U0001f319 *절전 모드로 전환합니다.*\n"
                "\u2022 3초 후 절전 상태로 들어갑니다.\n"
                "\u26a0\ufe0f 자동 로그인 설정 실패 — 수동 PIN 입력이 필요할 수 있습니다."
            )

        def async_sleep_mode():
            time.sleep(3)
            os.system(
                'powershell -command "Add-Type -Assembly System.Windows.Forms; '
                '[System.Windows.Forms.Application]::SetSuspendState(\'Suspend\', $false, $false)"'
            )

        threading.Thread(target=async_sleep_mode, daemon=True).start()
        return

    # 4. 등록된 파일/그룹 실행
    for name, paths in commands.items():
        if name in text:
            if isinstance(paths, str):
                paths = [paths]
            say(f"\U0001f680 **`{name}` (총 {len(paths)}개 파일) 실행을 시작합니다!**")
            for path in paths:
                if os.path.exists(path):
                    say(f"\u25b6\ufe0f 실행 중: `{path}`")
                    try:
                        file_dir = os.path.dirname(path)
                        original_dir = os.getcwd()
                        try:
                            os.chdir(file_dir)
                            os.startfile(path)
                        finally:
                            os.chdir(original_dir)
                    except Exception as e:
                        say(f"\u274c 실행 실패 (`{path}`): {e}")
                else:
                    say(f"\u26a0\ufe0f 파일 없음: `{path}`")
            return

    # 5. 도움말
    if "목록" in text or "도움말" in text:
        file_list = [f"\u2022 `{key}` \u27a1\ufe0f `{val}`" for key, val in commands.items()]
        say("\U0001f4cb **등록된 명령어 목록:**\n" + "\n".join(file_list))


if __name__ == "__main__":
    logger.info("\U0001f5a5\ufe0f 윈도우 로컬 PC 에이전트 시작 중...")

    # 부팅 시 자동 로그인 플래그 즉시 제거 (보안 복구)
    clear_autologin()

    # 슬랙 부팅 완료 알림 (백그라운드)
    threading.Thread(target=send_boot_notification, daemon=True).start()

    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
