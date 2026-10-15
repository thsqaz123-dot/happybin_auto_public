# AGENTS.md

이 저장소는 AI(코딩 에이전트)와 함께 유지보수됩니다. 아래 규칙을 반드시 따릅니다.

## 자동 커밋 규칙 (필수)

AI는 **코드를 수정할 때마다 즉시 커밋**해야 합니다.

1. 파일을 생성/수정/삭제하는 작업을 완료할 때마다 하나의 논리적 단위로 커밋한다.
2. 여러 파일을 동시에 바꾸더라도, 하나의 목적(기능/버그픽스/리팩터)에 해당하면 한 커밋으로 묶는다.
3. 커밋 없이 여러 변경을 쌓아두지 않는다. "수정 → 검증 → 커밋"을 반복한다.
4. 사용자가 명시적으로 요청하지 않는 한 `git push`는 하지 않아도 되지만, 커밋은 항상 남긴다.

## 커밋 메시지 규칙

Conventional Commits 형식을 사용한다.

```
<type>: <요약 (한국어 또는 영어, 72자 이내)>

<본문 - 변경 이유/맥락 (선택)>
```

- `feat`: 새 기능
- `fix`: 버그 수정
- `refactor`: 동작 변화 없는 리팩터
- `docs`: 문서 변경
- `test`: 테스트 추가/수정
- `chore`: 빌드/설정/기타

예시:
```
fix: 카페 글쓰기 등록 버튼 셀렉터 fallback 추가
feat: 해피빈 오늘의 Pick 콩 수집 로직 추가
```

## 보안 규칙 (필수)

- `user_data/` (크롬 프로필, 쿠키, 로그인 세션)는 **절대 커밋하지 않는다**. `.gitignore`에 포함되어 있다.
- 네이버 계정 비밀번호, 인증 토큰, API 키 등 **민감 정보를 코드/커밋에 포함하지 않는다**.
- 새 시크릿이 필요하면 환경 변수나 `.env`(gitignore 처리)로 관리한다.

## 프로젝트 개요

네이버 해피빈 콩 자동 수집기 (Playwright Persistent Context 기반).

### 아키텍처 (v2)

- `main.py` — 진입점 (기본 UI, 선택적 CLI)
- `automation.py` — UI/CLI 공통 실행 흐름
- `ui.py` — 실행·중지·로그인 초기화·진행 로그 Windows UI
- `config.py` — 공통 설정 (카페 등)
- `modules/paths.py` — 경로 해결 유틸리티 (exe/개발 환경 대응)
- `modules/login.py` — 로그인 모듈 (Persistent Context + 자동화 감지 우회)
- `modules/user_manager.py` — 사용자별 데이터 디렉토리 관리
- `modules/session_manager.py` — 쿠키/세션 저장/복원
- `modules/blog.py` — 블로그 글쓰기
- `modules/cafe.py` — 카페 글쓰기
- `modules/happybean.py` — 해피빈 콩 수집
- `modules/utils.py` — 유틸리티
- `content/templates.py` — 글 제목/본문 템플릿

### 로그인 방식

- **QR 로그인 (기본)**: 네이버 앱으로 QR 스캔 → CAPTCHA 없이 로그인
- **ID/PW 로그인 (fallback)**: QR 실패 시 사용자가 직접 브라우저에서 입력
- **고정 Chromium 사용**: Playwright Chromium — 시스템 Chrome 설치·버전과 무관
- **Persistent Context**: Playwright가 직접 브라우저 관리 (CDP 불필요)
- **자동화 감지 우회**: `--disable-blink-features=AutomationControlled` + init_script
- **쿠키 기반 감지**: NID_AUT, NID_SES 쿠키로 로그인 상태 확인

### 사용자 데이터

각 사용자는 `%LOCALAPPDATA%/HappyBeanAuto/{username}/`에 데이터를 가짐:
- `user_config.json`: 사용자 설정 (자동 생성)
- `session.json`: 로그인 세션 (쿠키)
- `browser/`: Chromium 프로필 (Persistent Context)

기존 실행 폴더의 `user_data/`는 첫 실행 때 위 경로로 자동 복사한다.

## 실행

```
pip install -r requirements.txt
playwright install chromium

# 일반 실행: Windows UI
python main.py

# 콘솔 실행
python main.py --cli --user 홍길동

# 로그인 세션 초기화
python main.py --reset-login

# 상태 확인
python main.py --status
```

## 카페 목적지

`HAPPYBIN_CAFE_ID`와 `HAPPYBIN_CAFE_URL` 환경변수로 설정한다.
미설정 시 카페 작업은 건너뛴다. 개인·조직의 실제 목적지를 기본값이나
예제에 커밋하지 않는다.

## 빌드

현재 공개 저장소는 소스만 제공하며 `build.bat`와 배포 ZIP은 포함하지 않는다.

## 주의사항

- 네이버 로그인 시 CAPTCHA가 발생할 수 있음 → QR 로그인으로 회피
- 세션 유효성은 인증 쿠키와 실제 서비스 로그인 상태에 따라 결정된다.
