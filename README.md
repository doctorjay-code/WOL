# 📱 Slack Bot ipTime WOL (컴퓨터 원격 부팅 봇)

슬랙(Slack)에서 `"컴터 켜줘"`, `"컴퓨터 켜줄래?"`, `"PC 부팅해줘"` 등의 자연어를 입력하면, **ipTime 공유기의 원격 WOL 기능**을 호출하여 집에 있는 PC 전원을 켜주는 **24/7 무료 슬랙 봇** 프로젝트입니다.

---

## 🛠️ 프로젝트 구조

```
WOL/
├── app.py              # 슬랙 봇 메인 실행 파일 (Socket Mode, 자연어 처리)
├── iptime_wol.py       # ipTime 공유기 세션 로그인 및 WOL HTTP 요청 모듈
├── requirements.txt    # 파이썬 라이브러리 목록
├── Procfile            # Render 배포 설정 파일
├── .gitignore          # 비밀번호/토큰 유출 방지용 설정
└── .env.example        # 환경 변수 템플릿
```

---

## 📋 1단계: ipTime 공유기 사전 설정 (3분 소요)

1. 웹 브라우저에서 ipTime 관리자 페이지(`http://192.168.0.1`) 접속
2. **[고급 설정] ➔ [특수기능] ➔ [DDNS 설정]**
   - 호스트 이름(예: `myhome.iptime.org`)과 사용자 이메일 입력 후 등록
3. **[고급 설정] ➔ [보안 기능] ➔ [공유기 접속/보안 관리]**
   - **원격 관리 포트 사용** 체크
   - 포트 번호 입력 (기본 8080 대신 `38472` 같은 **임의의 5자리 숫자** 권장)
4. **[고급 설정] ➔ [특수기능] ➔ [WOL 기능]**
   - 켜고자 하는 PC의 **MAC 주소** 등록 및 확인

> 💡 **완성된 접속 주소 예시:** `http://myhome.iptime.org:38472`

---

## 📱 2단계: Slack App 생성 및 토큰 발급 (5분 소요)

1. [Slack API 페이지](https://api.slack.com/apps) 접속 후 **[Create New App]** ➔ **[From scratch]** 클릭
2. App Name 지정 후 워크스페이스 선택
3. **[Settings] ➔ [Basic Information]**
   - App-Level Tokens ➔ **[Generate Token and Scopes]** 클릭
   - Token Name 입력 및 Scope에 `connections:write` 추가 ➔ **Generate**
   - 생성된 **`SLACK_APP_TOKEN`** (`xapp-...`) 복사
4. **[Settings] ➔ [Socket Mode]**
   - **Enable Socket Mode** 스위치를 **ON**으로 변경
5. **[Features] ➔ [OAuth & Permissions]**
   - Bot Token Scopes 항목에 다음 4개 권한 추가:
     - `chat:write`
     - `app_mentions:read`
     - `channels:history`
     - `im:history`
   - 맨 위 **[Install to Workspace]** 버튼 클릭 후 허용
   - 생성된 **`SLACK_BOT_TOKEN`** (`xoxb-...`) 복사
6. **[Features] ➔ [App Home]**
   - Messages Tab ➔ **[Allow users to send Slash commands and messages from the messages tab]** 체크

---

## 🐙 3단계: GitHub에 저장소 올리기

1. GitHub 접속 후 새 Repository 생성 (예: `WOL-Slack-Bot`)
2. 내 컴퓨터의 `WOL` 폴더에서 명령 프롬프트(CMD) / 터미널 열기:

```bash
git init
git add .
git commit -m "Add ipTime WOL Slack Bot"
git branch -M main
git remote add origin https://github.com/내아이디/WOL-Slack-Bot.git
git push -u origin main
```

---

## 🚀 4단계: Render.com 24시간 무료 배포 (3분 소요)

1. [Render.com](https://render.com) 접속 후 **GitHub 계정으로 로그인**
2. **[New +]** ➔ **[Background Worker]** (또는 Web Service) 선택
3. 방금 올린 GitHub 저장소 선택
4. 기본 설정 확인:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Instance Type**: `Free`
5. **[Environment Variables]** 항목에 아래 값들을 추가:

| Key | Value 예시 | 설명 |
| :--- | :--- | :--- |
| `SLACK_BOT_TOKEN` | `xoxb-1234...` | 슬랙 봇 토큰 |
| `SLACK_APP_TOKEN` | `xapp-1234...` | 슬랙 앱 토큰 |
| `IPTIME_URL` | `http://myhome.iptime.org:38472` | ipTime DDNS 주소 + 포트 |
| `IPTIME_USER` | `admin` | ipTime 공유기 관리자 아이디 |
| `IPTIME_PASS` | `my_password` | ipTime 공유기 관리자 비밀번호 |
| `TARGET_MAC` | `AA:BB:CC:DD:EE:FF` | 켜고자 하는 PC의 MAC 주소 |
| `ALLOWED_SLACK_USER_ID` | `U12345678` | *(선택)* 본인 슬랙 유저 ID (보안용) |

6. 맨 아래 **[Create Background Worker]** 클릭!
7. 1분 후 Render 로그에 `⚡ Slack Bot (Socket Mode) 시작 중...` 메시지가 뜨면 완벽하게 완성됩니다! 🎉

---

## 💬 슬랙 사용법

슬랙 채널이나 봇과의 1:1 대화방에서 아래처럼 편하게 메시지를 보내보세요.

* `"컴터 켜줘"`
* `"컴퓨터 켜줄래?"`
* `"PC 부팅해줘"`
* `"컴 켜라"`
* `"도움말"`
