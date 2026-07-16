# Ggeolmu Language Pro

Ggeolmu Language Pro는 유튜브 영상을 보며 효율적으로 언어 학습을 할 수 있도록 도와주는 로컬 웹 애플리케이션입니다. 영상과 연동된 인터랙티브 자막(스크립트)을 제공하며, 모르는 단어에 마우스를 올리면 즉석에서 번역 및 발음을 확인할 수 있습니다.

## 🚀 주요 기능 (Features)

- **유튜브 자막 자동 추출**: 유튜브 URL만 입력하면 해당 영상의 자막을 자동으로 불러옵니다.
- **인터랙티브 스크립트 뷰어**: 스크립트의 특정 문장이나 단어를 클릭하면 영상이 해당 위치로 즉시 이동하여 재생됩니다.
- **실시간 단어 번역 (Hover-to-Translate)**: 모르는 단어 위에 마우스를 올리면 구글 번역 기반의 뜻과 발음(독음) 툴팁이 제공됩니다.
- **북마크릿 (바로가기 지원)**: 유튜브 시청 중 북마크릿을 클릭하면 현재 보고 있는 영상을 즉시 Language Pro 환경으로 전환해 줍니다.
- **키보드 단축키 지원**: 스페이스바(Space)를 눌러 언제든 편리하게 영상을 재생하거나 일시정지할 수 있습니다.
- **로컬 커스텀 도메인**: 복잡한 포트 번호 없이 `http://ggeolmu-language.com` 주소로 깔끔하게 접속할 수 있도록 DNS 설정 자동화 스크립트를 지원합니다.

## 🛠 기술 스택 (Tech Stack)

- **Frontend**: HTML5, Vanilla CSS (Glassmorphism UI), Vanilla JavaScript (YouTube IFrame API 연동)
- **Backend**: Python 3 (내장 `http.server` 모듈), `youtube-transcript-api`
- **Automation (Mac)**: AppleScript 기반의 Mac 전용 자동화 앱 (`.app`) 제공

## 📁 디렉토리 구조 (Structure)

- `LanguageLearner/` : 메인 웹 애플리케이션 소스 코드 (HTML, CSS, JS, Python 서버 코드)
  - `server.py` : 포트 80에서 동작하는 로컬 백엔드 서버
  - `index.html` & `app.js` & `style.css` : 프론트엔드 UI 및 로직
- `run_app.py` : 관리자 권한으로 백엔드 서버를 실행하는 파이썬 런처 스크립트
- `Set_Local_DNS.app` / `Unset_Local_DNS.app` : 로컬 테스트용 커스텀 도메인을 `/etc/hosts`에 등록/해제하는 Mac 전용 앱
- `Start_Server.app` / `Stop_Server.app` : 더블클릭만으로 서버를 켜고 끄는 Mac 자동화 런처

## ⚙️ 실행 방법 (How to Run)

1. **Mac 전용 (권장 방식)**:
   - 프로젝트 루트 폴더에 있는 `Start_Server.app`을 더블클릭하여 실행합니다. (비밀번호 입력 필요)
   - 서버가 켜지면 브라우저를 열고 `http://ggeolmu-language.com` 으로 접속합니다.
   - 사용이 끝나면 `Stop_Server.app`을 더블클릭하여 서버를 안전하게 종료합니다.

2. **수동 실행**:
   - 터미널을 열고 파이썬 런처를 실행합니다: `sudo python3 run_app.py`

## 💡 Pro Tip
제공되는 북마크릿(즐겨찾기 버튼) 기능을 크롬 즐겨찾기 바에 등록해 두면, 일반 유튜브 창에서 영상을 보다가도 버튼 한 번 클릭으로 학습 환경으로 전환할 수 있습니다.
