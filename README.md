# 📱 Slack Bot ipTime WOL & Remote PC Control System

슬랙(Slack)을 통해 **원격 컴퓨터 전원 켜기(WOL)** 및 부팅 후 **특정 파일/프로그램 실행**, **원격 컴퓨터 종료**를 제어하는 통합 AI 서비스 프로젝트입니다.

AI 코딩 어시스턴트(Antigravity 등)가 이 프로젝트를 한눈에 파악하고 확장할 수 있도록 전체 구조가 정의되어 있습니다.

---

## 🏗️ 프로젝트 전체 구조 (Project Structure)

```text
WOL/
├── app.py              # [클라우드 24/7 봇] Render.com 등 클라우드에서 실행되며 WOL 전원 켜기 담당
├── iptime_wol.py       # ipTime 공유기 웹 관리자 세션 로그인 및 WOL HTTP POST 발송 모듈
├── pc_agent.py         # [로컬 PC 에이전트] 윈도우 부팅 시 자동 실행되며 파일 실행 및 원격 종료 담당
├── commands.json       # 슬랙 명령어 ➔ 윈도우 실행 파일 경로 매핑 설정 파일 (새 파일 추가 시 여기 수정)
├── run_agent.bat       # 윈도우 시작프로그램(shell:startup) 등록용 실행 스크립트
├── requirements.txt    # 파이썬 라이브러리 의존성
├── Procfile            # Render.com 무료 웹 서비스 배포 설정
├── .gitignore          # 환경변수(.env) 유출 방지
└── .env                # 슬랙 토큰 및 ipTime 접속 정보 (GitHub 업로드금지)
```

---

## ⚙️ 2개의 핵심 봇 서비스 역할 분담

### 1. Cloud WOL Bot (`app.py`)
* **실행 환경**: Render.com (24시간 완전 무료 호스팅)
* **주요 역할**: 컴퓨터가 꺼져 있을 때 슬랙 메시지(`"컴터 켜줘"`)를 수신하고, ipTime 공유기 DDNS로 WOL 패킷을 보냅니다.
* **보안 기능**: `ALLOWED_SLACK_USER_ID` 설정으로 본인만 전원을 켤 수 있도록 제한 가능.

### 2. Local Windows Agent (`pc_agent.py`)
* **실행 환경**: 내 컴퓨터(Windows) 시작프로그램(`shell:startup`) 등록
* **주요 역할**: 부팅 완료 후 백그라운드에서 동작하며 특정 파일 실행 및 원격 종료 처리.
* **명령어 예시**:
  * `"닥터빌 켜줘"` ➔ `박주하_닥터빌.bat` + `박범준_닥터빌.bat` 둘 다 동시에 실행 🚀
  * `"박주하 켜줘"` ➔ `박주하_닥터빌.bat` 개별 실행
  * `"박범준 켜줘"` ➔ `박범준_닥터빌.bat` 개별 실행
  * `"컴터 꺼줘"` / `"컴퓨터 종료"` ➔ 윈도우 원격 종료 (`shutdown /s /t 10`)

---

## ➕ 새로운 파일/프로그램 추가하는 방법 (`commands.json`)

새로운 파일이나 프로그램을 슬랙으로 키고 싶을 때는 `commands.json` 파일만 수정하시면 됩니다:

```json
{
  "박주하": [
    "C:\\Users\\hyo02\\Downloads\\GitHub\\DVA\\박주하_닥터빌.bat"
  ],
  "박범준": [
    "C:\\Users\\hyo02\\Downloads\\GitHub\\DVA\\박범준_닥터빌.bat"
  ],
  "닥터빌": [
    "C:\\Users\\hyo02\\Downloads\\GitHub\\DVA\\박주하_닥터빌.bat",
    "C:\\Users\\hyo02\\Downloads\\GitHub\\DVA\\박범준_닥터빌.bat"
  ],
  "카카오톡": [
    "C:\\Program Files\\Kakao\\KakaoTalk.exe"
  ]
}
```

---

## 🔐 환경 변수 목록 (.env)

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
IPTIME_URL=http://hyo02040.iptime.org:14817
IPTIME_USER=hyo02040
IPTIME_PASS=jFLUK8GDtEr8ixY
TARGET_MAC=70-5D-CC-99-BF-7A
ALLOWED_SLACK_USER_ID=
```

---

## 🤖 Antigravity 바이브 코딩 가이드

Antigravity로 기능 추가 또는 수정 시 참고사항:
1. **WOL 관련 기능 수정**: `iptime_wol.py` 또는 `app.py` 수정 후 GitHub에 `git push` 하면 Render에 자동 반영됨.
2. **윈도우 제어 기능 수정**: `pc_agent.py` 또는 `commands.json` 수정 후 저장하면 로컬 에이전트가 반영함.
