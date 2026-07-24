# -*- coding: utf-8 -*-
"""
DVA 구조 기반 Slack 로컬 PC 에이전트 (Tkinter GUI 창 적용)
- 윈도우 native WM_DELETE_WINDOW 이벤트를 가로채 X 버튼 클릭 시 0초 즉시 숨김 + 100% 슬랙 종료 알림 전송
- 바탕화면/작업표시줄에 예쁜 윈도우 창 표출 및 실시간 슬랙 로그 표시
"""

import os
import re
import json
import time
import socket
import atexit
import signal
import sys
import urllib.request
import urllib.parse
import threading
import logging
import tkinter as tk
from tkinter import scrolledtext
from dotenv import load_dotenv

from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WOL-LocalAgent")

load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
SLACK_CHANNEL   = os.environ.get("SLACK_NOTIFY_CHANNEL", "C0BKDHNLATE")
COMMANDS_FILE   = os.path.join(os.path.dirname(__file__), "commands.json")

web_client = WebClient(token=SLACK_BOT_TOKEN)
is_shutdown_sent = False

def load_commands() -> dict:
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"commands.json 로드 실패: {e}")
    return {}

def send_direct_slack_message(text: str):
    """0.01초 초고속 Direct HTTP REST 발송"""
    try:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8"
        }
        data = json.dumps({"channel": SLACK_CHANNEL, "text": text}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass
    except Exception as e:
        logger.error(f"Direct Slack 발송 실패: {e}")

def send_message(channel: str, text: str, thread_ts: str = None):
    try:
        web_client.chat_postMessage(channel=channel, text=text, thread_ts=thread_ts)
    except Exception as e:
        logger.error(f"Slack 메시지 발송 실패: {e}")

def send_shutdown_notification(reason: str = "로컬 에이전트가 종료되었습니다."):
    """에이전트 종료 시 한 줄 슬랙 알림"""
    global is_shutdown_sent
    if is_shutdown_sent:
        return
    is_shutdown_sent = True
    send_direct_slack_message(f"🔴 {reason}")

def kill_previous_instances():
    """새 에이전트 실행 시 기존에 켜져 있던 이전 pc_agent.py 조용히 자동 닫기"""
    my_pid = os.getpid()
    try:
        ps_cmd = f'powershell -command "Get-WmiObject Win32_Process | Where-Object {{$_.CommandLine -like \'*pc_agent.py*\' -and $_.ProcessId -ne {my_pid}}} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"'
        os.system(ps_cmd)
    except Exception as e:
        logger.error(f"이전 프로세스 정리 실패: {e}")

def kill_doctorbill_processes() -> int:
    """닥터빌(DVA main.py 및 chromedriver) 프로세스 종료"""
    killed_count = 0
    try:
        ps_cmd = 'powershell -command "Get-WmiObject Win32_Process | Where-Object {$_.CommandLine -like \'*main.py*\' -or $_.Name -eq \'chromedriver.exe\'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"'
        os.system(ps_cmd)
        killed_count += 1
    except Exception as e:
        logger.error(f"닥터빌 프로세스 종료 중 오류: {e}")
    return killed_count

DOCTORBILL_TARGETS = ["닥터빌", "박주하", "박범준", "디바", "DVA", "dva"]

class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Slack PC Agent")
        self.root.geometry("520x350")
        self.root.configure(bg="#1E1E1E")

        # 헤더 레이블
        header = tk.Label(
            root,
            text="🟢 Slack 로컬 PC 에이전트 가동 중",
            font=("Malgun Gothic", 12, "bold"),
            bg="#1E1E1E",
            fg="#4CAF50",
            pady=10
        )
        header.pack()

        # 로그 텍스트 영역
        self.log_area = scrolledtext.ScrolledText(
            root,
            width=60,
            height=13,
            font=("Consolas", 9),
            bg="#252526",
            fg="#D4D4D4",
            insertbackground="white"
        )
        self.log_area.pack(padx=10, pady=5)
        self.log_msg("시스템 초기화 완료. 슬랙 메시지 실시간 대기 중...\n" + "="*50)

        # WM_DELETE_WINDOW (X 버튼 닫기) 이벤트 100% 가로채기
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def log_msg(self, msg: str):
        def _append():
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(0, _append)

    def on_close(self):
        """X 버튼 클릭 시 0.001초 만에 창 숨김 -> 슬랙 종료 알림 전송 -> 종료"""
        try:
            self.root.withdraw()  # 사용자 눈앞에서 즉시 0초 만에 창 완전히 숨기기
        except Exception:
            pass

        # 백그라운드 슬랙 알림 100% 발송
        send_shutdown_notification("로컬 에이전트가 종료되었습니다.")
        
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

gui_app = None

def handle_socket_request(client: SocketModeClient, req: SocketModeRequest):
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.send_socket_mode_response(response)

    if req.type == "events_api":
        event = req.payload.get("event", {})
        event_type = event.get("type")

        if event.get("bot_id") or event.get("subtype") in ["bot_message", "channel_join"]:
            return

        if event_type in ["app_mention", "message"]:
            text = event.get("text", "").strip()
            channel_id = event.get("channel")
            thread_ts = event.get("ts")

            if not text or not channel_id:
                return

            if gui_app:
                gui_app.log_msg(f"Slack 메시지 수신: '{text}'")
            logger.info(f"메시지 수신: '{text}' (채널: {channel_id})")
            commands = load_commands()

            # 1. 컴터 전체 절전 모드 ("컴터 꺼줘" / "컴퓨터 꺼")
            if any(pc_word in text for pc_word in ["컴터", "컴퓨터"]) and any(act_word in text for act_word in ["꺼줘", "종료", "꺼"]):
                if gui_app:
                    gui_app.log_msg("-> 윈도우 컴퓨터 전체 절전 모드 실행")
                send_message(channel_id, "🌙 *3초 후 윈도우 절전 모드를 실행합니다.*")
                time.sleep(1)
                send_shutdown_notification("로컬 에이전트가 종료되었습니다.")
                time.sleep(2)
                os.system('powershell -command "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState(\'Suspend\', $false, $false)"')
                return

            # 2. 닥터빌(DVA) 프로그램만 개별 종료
            if any(target in text for target in DOCTORBILL_TARGETS) and any(action in text for action in ["꺼줘", "종료", "꺼", "닫아"]):
                if gui_app:
                    gui_app.log_msg("-> 닥터빌(DVA) 프로그램 종료")
                kill_doctorbill_processes()
                send_message(channel_id, "🛑 *닥터빌(DVA) 프로그램을 종료했습니다.*")
                return

            # 3. 단독 "꺼" / "꺼줘" / "종료"
            if text.strip() in ["꺼줘", "종료", "꺼"]:
                if gui_app:
                    gui_app.log_msg("-> 닥터빌(DVA) 프로그램 종료")
                kill_doctorbill_processes()
                send_message(channel_id, "🛑 *닥터빌(DVA) 프로그램을 종료했습니다.*")
                return

            # 4. 등록된 파일/프로그램 실행 (닥터빌, 박주하, 박범준, 디바, DVA, ㄱㄱ 등)
            for name, paths in commands.items():
                if name.lower() in text.lower():
                    if isinstance(paths, str):
                        paths = [paths]
                    if gui_app:
                        gui_app.log_msg(f"-> '{name}' 실행 ({len(paths)}개 파일)")
                    send_message(channel_id, f"🚀 *`{name}` ({len(paths)}개 파일) 실행을 시작합니다!*")
                    for path in paths:
                        if os.path.exists(path):
                            if gui_app:
                                gui_app.log_msg(f"   └ 실행: {path}")
                            send_message(channel_id, f"▶️ 실행 중: `{path}`")
                            file_dir = os.path.dirname(path)
                            orig_dir = os.getcwd()
                            try:
                                os.chdir(file_dir)
                                os.startfile(path)
                            finally:
                                os.chdir(orig_dir)
                        else:
                            if gui_app:
                                gui_app.log_msg(f"   └ 오류 (파일없음): {path}")
                            send_message(channel_id, f"⚠️ 파일 경로를 찾을 수 없습니다: `{path}`")
                    return

            # 5. 명령어 목록 / 도움말
            if any(k in text for k in ["목록", "도움말", "명령어"]):
                if gui_app:
                    gui_app.log_msg("-> 도움말 출력")
                items = [f"• `{k}` ➔ `{v}`" for k, v in commands.items()]
                help_text = (
                    "📋 *등록된 명령어 목록:*\n" +
                    "\n".join(items) +
                    "\n\n*종료 및 전원 명령어:*" +
                    "\n• `꺼줘` / `꺼` / `닥터빌 꺼줘` ➔ 닥터빌(DVA) 프로그램만 종료" +
                    "\n• `컴터 꺼줘` / `컴퓨터 꺼` ➔ 윈도우 컴퓨터 전체 절전 모드"
                )
                send_message(channel_id, help_text)

def start_slack_socket():
    """슬랙 소켓 리스너 백그라운드 스레드 가동"""
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.error(".env 파일에 토큰이 없습니다.")
        return

    socket_client = SocketModeClient(app_token=SLACK_APP_TOKEN, web_client=web_client)
    socket_client.socket_mode_request_listeners.append(handle_socket_request)
    socket_client.connect()

    # 가동 알림 전송 (한 줄)
    send_direct_slack_message("🟢 로컬 에이전트가 가동되었습니다.")

def main():
    global gui_app

    # 이전 프로세스 정리
    kill_previous_instances()

    atexit.register(send_shutdown_notification)

    # 슬랙 소켓 백그라운드 스레드 시작
    t = threading.Thread(target=start_slack_socket, daemon=True)
    t.start()

    # 메인 GUI 창 가동 (Tkinter Native Window)
    root = tk.Tk()
    gui_app = AgentGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
