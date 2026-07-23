# Ggeolmu Language Pro (Web Version)

Ggeolmu Language Pro는 유튜브 영상을 보며 모르는 단어를 바로바로 찾아볼 수 있는 어학 학습 플랫폼입니다.
기존 로컬 앱 방식에서 벗어나, 어디서든 접속 가능한 **4-Tier 기반 웹 애플리케이션(Django + PostgreSQL + Redis + Kafka)** 으로 업그레이드 되었습니다.

---

## 🏗 아키텍처 (4-Tier)

- **WEB (Frontend)**: 반응형 Glassmorphism UI (HTML/CSS/JS)
- **WAS (Backend)**: Django 4.2 (사용자 관리, 유튜브 자막 파싱 API 등)
- **Database / Cache**: PostgreSQL (회원 정보), Redis (자막 데이터 캐싱)
- **Manager**: 분리된 SQL 파일(queries/)을 통한 모니터링 로그 기록 (Kafka 연동 준비 완료)

---

## 🚀 로컬 환경 실행 가이드

### 1. 인프라 실행 (Docker)
PostgreSQL, Redis, Kafka를 도커를 이용해 백그라운드에서 실행합니다. (도커 데스크탑이 켜져 있어야 합니다.)
```bash
docker-compose up -d
```

### 2. 가상환경 및 의존성 패키지 설치
Python 가상환경을 활성화하고 최신 패키지들을 설치합니다.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 데이터베이스 마이그레이션 (선택)
(현재 로컬 테스트는 `sqlite3`로 동작하도록 설정되어 있습니다. `.env` 파일을 수정하면 Docker의 PostgreSQL로 바로 연결됩니다.)
```bash
python manage.py migrate
```

### 4. 서버 실행
개발용 서버를 포트 8000번으로 띄웁니다.
```bash
python manage.py runserver
```

### 5. 웹사이트 접속
브라우저를 열고 아래 주소로 접속합니다.
**👉 [http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 💡 주요 기능

- **회원 시스템**: 이름, 아이디, 비밀번호로 가입하면 UUID 기반의 고유 식별 코드가 발급됩니다.
- **스마트 캐싱 (Redis)**: 한 번 분석된 유튜브 자막은 1시간(3600초) 동안 캐시되어, 다음 요청 시 즉시 로딩됩니다.
- **데이터 파이프라인 (Kafka)**: 사용자가 영상을 로드할 때마다 로그 이벤트가 Message Queue에 적재되어, 추후 데이터 분석이나 스트리밍에 활용 가능합니다.
- **안전한 모니터링 (Manager)**: SQL Injection을 방지하기 위해 로깅 쿼리는 모두 분리된 `.sql` 파일로만 실행되도록 설계되었습니다.
