# 해피빈 자동 수집기

Python과 Playwright를 사용하는 Windows 데스크톱 프로그램입니다. 로그인한
네이버 계정으로 블로그 글 발행, 카페 글 등록과 콩 수집을 수행합니다.

## 개발 환경

Python 3.10 이상이 필요합니다. Windows PowerShell에서:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python main.py --help
.\.venv\Scripts\python main.py
```

`PLAYWRIGHT_BROWSERS_PATH=0`으로 설치해야 로그인 모듈의 기본 브라우저
검색 위치와 일치합니다. 별도 경로를 쓰면 설치와 실행에 같은 값을 지정하세요.

Linux에서는 다음과 같이 의존성 설치와 CLI 점검을 할 수 있습니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=0 .venv/bin/python -m playwright install chromium
.venv/bin/python main.py --help
.venv/bin/python main.py --status
```

실제 자동화의 화면 크기 계산은 `ctypes.windll`을 사용하므로 Windows가
필요합니다. Linux GUI/전체 자동화 실행은 현재 지원되지 않습니다.

## 실행과 데이터

- 기본 실행: Windows UI
- `python main.py --cli --user 사용자명`: 자동화 실행
- `python main.py --status`: 로컬 세션 백업 상태
- `python main.py --list-users`: 등록 사용자 목록
- `python main.py --reset-login`: 해당 사용자의 세션과 브라우저 프로필 삭제

카페 작업은 환경변수 `HAPPYBIN_CAFE_ID`(숫자 ID)와
`HAPPYBIN_CAFE_URL`(카페 주소)을 둘 다 설정한 경우에만 실행합니다.
PowerShell에서 다음 예시를 자신의 카페 정보로 바꿔 설정하세요.

```powershell
$env:HAPPYBIN_CAFE_ID = "12345678"
$env:HAPPYBIN_CAFE_URL = "https://cafe.naver.com/your-cafe"
```

미설정 시 카페 글쓰기와 카페 메인 배너 스캔을 건너뜁니다. `.env` 파일은
자동으로 읽지 않습니다. 실행 전 목적지와 계정 권한을 확인하세요.
블로그는 비공개 발행을 시도하지만
현재 코드는 비공개 선택 성공 여부를 강제하지 않으므로 민감한 본문에 사용하지
마세요. 카페에는 실제 게시글이 등록됩니다.

`test_auto.py`, `test_blog_cafe.py`, `verify_*.py`, `check_banners.py`는
실제 로그인과 게시글 작성을 수행하는 수동 도구입니다. 자동 단위 테스트로
실행하지 마세요. 개인정보가 포함된 진단 캡처와 전용 디버그 스크립트는
공개 대상 소스에서 제거했습니다.

세션과 브라우저 프로필은 `%LOCALAPPDATA%/HappyBeanAuto/<사용자명>/`에
저장됩니다. `LOCALAPPDATA`가 없으면 `~/AppData/Local/HappyBeanAuto/`를
사용합니다. 쿠키 백업은 암호화되지 않은 로컬 파일이므로 OS 계정 권한으로
보호하고 저장소, 공유 폴더, 배포 ZIP에 포함하지 마세요.

## 공개 배포 범위

이 저장소는 검토한 소스만 새 이력으로 시작합니다. 인증된 페이지 캡처,
로그인 세션, 브라우저 프로필, 실행파일 배포 ZIP은 포함하지 않습니다.
현재 소스에는 `build.bat`가 없어 Windows 배포 빌드는 제공하지 않습니다.
라이선스는 아직 지정되어 있지 않습니다.
