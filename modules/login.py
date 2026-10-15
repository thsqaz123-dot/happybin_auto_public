"""
네이버 로그인 모듈 (v3)

QR 로그인 방식:
- ID/PW 입력 불필요 → CAPTCHA 문제 완전 회피
- 네이버 앱으로 QR 스캔 → 자동 로그인
- Persistent Context로 세션 유지
"""
import os
import time
from collections.abc import Callable

# build.bat가 이 경로에 고정 버전 Chromium을 설치한다. 개발 환경에서도
# 같은 위치를 사용해 시스템 Chrome 버전 차이를 없앤다.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

from playwright.sync_api import sync_playwright, Page, BrowserContext, Playwright

from modules.session_manager import (
    save_session,
    check_login_cookies,
    wait_for_login,
    is_session_file_valid,
)
from modules.user_manager import get_browser_dir
from modules.utils import get_screen_size, safe_goto


# 자동화 감지 우회 스크립트
STEALTH_SCRIPTS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
if (!window.chrome) { window.chrome = {}; }
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);
"""

# QR 로그인 직접 URL
QR_LOGIN_URL = "https://nid.naver.com/nidlogin.login?mode=qrcode&url=https%3A%2F%2Fwww.naver.com&locale=ko_KR&svctype=1"


def create_browser_context(username: str) -> tuple[Playwright, BrowserContext]:
    """
    Persistent Context 브라우저 생성.

    시스템 Chrome 대신 Playwright가 설치한 Chromium을 사용한다. 프로필
    자체가 로그인 캐시이므로 오래된 session.json 쿠키를 다시 주입하지 않는다.

    Returns:
        (playwright_instance, browser_context)
    """
    browser_dir = get_browser_dir(username)
    os.makedirs(browser_dir, exist_ok=True)

    print(f"[브라우저] 프로필 디렉토리: {browser_dir}")

    pw = sync_playwright().start()

    # 화면 크기에 따라 브라우저 위치/크기 결정 (CMD 오른쪽에 배치)
    screen_w, screen_h = get_screen_size()
    browser_x = int(screen_w * 0.45)
    browser_w = int(screen_w * 0.50) - 16  # 윈도우 테두리 보정
    browser_h = int(screen_h * 0.9)

    try:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=browser_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                f"--window-position={browser_x},0",
                f"--window-size={browser_w},{browser_h}",
            ],
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": browser_w - 20, "height": browser_h - 80},
            ignore_default_args=["enable-automation"],
        )
        print("[브라우저] 내장 Chromium 사용")
    except Exception as e:
        pw.stop()
        raise RuntimeError(
            "내장 Chromium을 실행할 수 없습니다. "
            "Playwright Chromium 설치 상태를 확인하세요."
        ) from e

    context.add_init_script(STEALTH_SCRIPTS)

    print("[브라우저] 실행 완료")
    return pw, context


def _navigate_to_qr(page: Page) -> bool:
    """QR 로그인 페이지로 이동"""
    print("[QR] QR 로그인 페이지로 이동합니다...")
    try:
        page.goto(QR_LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
        return True
    except Exception as e:
        print(f"[QR] QR 페이지 이동 실패: {e}")
        return False


def _is_qr_displayed(page: Page) -> bool:
    """QR 코드가 화면에 표시되는지 확인"""
    selectors = [
        "img.qr_img",
        "[class*='qrcode'] img",
        "img[src*='data:image']",
        ".qr_img",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                return True
        except Exception:
            continue
    return False


def _wait_for_qr_scan(page: Page, timeout: int = 300,
                      cancel_check: Callable[[], bool] | None = None) -> bool:
    """
    사용자가 QR을 스캔할 때까지 대기

    성공 조건:
    1. 쿠키 확인 (NID_AUT, NID_SES)
    2. URL 변경 (nid.naver.com → naver.com)
    """
    print(f"[QR] QR 스캔 대기 중... (최대 {timeout}초)")
    print("[QR] 네이버 앱으로 QR코드를 스캔해주세요!")

    start = time.time()
    while time.time() - start < timeout:
        if cancel_check and cancel_check():
            print("[QR] 로그인 대기를 중지했습니다.")
            return False
        # 1. 쿠키 확인 (가장 신뢰성 높음)
        if check_login_cookies(page):
            return True

        # 2. URL 확인 (보조)
        current_url = page.url
        if "naver.com" in current_url and "nid.naver.com" not in current_url:
            page.wait_for_timeout(1500)
            if check_login_cookies(page):
                return True

        # 3. QR 만료 확인 → 새로고침
        try:
            expired = page.locator("text=시간이 만료").first
            if expired.is_visible(timeout=500):
                print("[QR] QR 코드 만료. 새로고침합니다...")
                page.reload(wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
        except Exception:
            pass

        time.sleep(2)

    return False


def do_qr_login(page: Page, username: str,
                cancel_check: Callable[[], bool] | None = None) -> bool:
    """
    QR 로그인 실행

    흐름:
    1. QR 로그인 페이지로 이동
    2. QR 코드 표시 확인
    3. 사용자가 네이버 앱으로 스캔 대기
    4. 로그인 성공 → 세션 저장

    Returns:
        True: 로그인 성공
        False: 로그인 실패
    """
    # 1. QR 페이지 이동
    if not _navigate_to_qr(page):
        return False

    # 2. QR 코드 표시 확인
    if not _is_qr_displayed(page):
        print("[QR] QR 코드를 찾을 수 없습니다. ID 로그인 페이지로 전환합니다.")
        return False

    print("[QR] QR 코드가 표시되었습니다!")
    print("[QR] 네이버 앱 > 메뉴 > QR코드 로그인을 실행해주세요!")

    # 3. QR 스캔 대기
    if _wait_for_qr_scan(page, timeout=300, cancel_check=cancel_check):
        print("[QR] 로그인 성공!")
        save_session(page.context, username)
        return True

    print("[QR] QR 로그인 타임아웃")
    return False


def do_id_login(page: Page, username: str,
                cancel_check: Callable[[], bool] | None = None) -> bool:
    """
    ID/PW 로그인 (fallback)
    사용자가 직접 브라우저에서 입력
    """
    print("[로그인] ID/PW 로그인 페이지로 이동합니다.")
    print("[로그인] 브라우저에서 직접 로그인해주세요.")

    page.goto("https://nid.naver.com/nidlogin.login", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    if wait_for_login(page, timeout=300, cancel_check=cancel_check):
        print("[로그인] 로그인 성공!")
        save_session(page.context, username)
        return True

    return False


def do_login(context: BrowserContext, username: str,
             cancel_check: Callable[[], bool] | None = None) -> bool:
    """
    네이버 로그인 처리 (메인)

    흐름:
    1. 저장된 세션 확인
    2. 네이버 접속 → 쿠키로 로그인 상태 확인
    3. 미로그인 시 → QR 로그인 시도
    4. QR 실패 시 → ID/PW 로그인 (사용자 직접 입력)

    Returns:
        True: 로그인 성공
        False: 로그인 실패
    """
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(30000)

    # 1. 네이버 접속 → 로그인 상태 확인
    print("[로그인] 네이버 로그인 상태를 확인합니다...")
    # 네이버 첫 접속은 광고/보안 리소스 때문에 DOM 로드가 늦어질 수 있다.
    # 로그인 판정에는 문서 커밋과 쿠키만 필요하므로 재시도 가능한 탐색을 쓴다.
    if not safe_goto(page, "https://www.naver.com", wait_until="commit", timeout=30000):
        print("[로그인] 네이버 연결에 실패했습니다. 네트워크를 확인한 뒤 다시 시도하세요.")
        return False
    page.wait_for_timeout(3000)

    if check_login_cookies(page) and "nid.naver.com" not in page.url:
        print("[로그인] 이미 로그인되어 있습니다.")
        save_session(context, username)
        return True

    # 2. QR 로그인 시도
    print("[로그인] 로그인이 필요합니다.")
    if do_qr_login(page, username, cancel_check=cancel_check):
        return True

    if cancel_check and cancel_check():
        return False

    # 3. QR 실패 → ID/PW 로그인 (fallback)
    print("[로그인] QR 로그인 실패. ID/PW 로그인으로 전환합니다.")
    return do_id_login(page, username, cancel_check=cancel_check)


def check_and_relogin(context: BrowserContext, username: str,
                       cancel_check: Callable[[], bool] | None = None) -> bool:
    """
    작업 중 세션 만료 시 재로그인 처리

    Returns:
        True: 재로그인 성공
        False: 재로그인 실패
    """
    page = context.pages[0] if context.pages else context.new_page()

    # 현재 작업 페이지를 네이버 메인으로 강제 이동하지 않는다.
    # 두 인증 쿠키가 모두 있으면 해당 세션을 그대로 사용하고,
    # 실제 만료는 각 작업의 로그인 리디렉션 진단에서 처리한다.
    if check_login_cookies(page):
        return True

    print("\n[로그인] 세션이 만료되었습니다. 재로그인이 필요합니다.")

    # QR 로그인 시도
    if do_qr_login(page, username, cancel_check=cancel_check):
        return True

    if cancel_check and cancel_check():
        return False

    # QR 실패 → ID/PW fallback
    print("[로그인] QR 로그인 실패. ID/PW 로그인으로 전환합니다.")
    return do_id_login(page, username, cancel_check=cancel_check)


def get_login_status_summary(context: BrowserContext, username: str) -> str:
    """로그인 상태 요약 문자열 반환"""
    page = context.pages[0] if context.pages else context.new_page()

    if check_login_cookies(page):
        return "로그인됨"

    if is_session_file_valid(username):
        return "세션 파일 존재 (쿠키 만료 가능)"

    return "미로그인"


def verify_login(page: Page) -> dict:
    """
    현재 로그인 상태 상세 확인

    Returns:
        {
            "logged_in": bool,
            "method": "cookie" | "page" | "none",
            "auth_cookies": list,
        }
    """
    result = {
        "logged_in": False,
        "method": "none",
        "auth_cookies": [],
    }

    cookies = page.context.cookies()
    auth_cookies = [
        c for c in cookies
        if c["name"] in {"NID_AUT", "NID_SES"}
        and "naver" in c.get("domain", "")
    ]

    if {"NID_AUT", "NID_SES"}.issubset({c["name"] for c in auth_cookies}):
        result["logged_in"] = True
        result["method"] = "cookie"
        result["auth_cookies"] = [c["name"] for c in auth_cookies]
        return result

    try:
        page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=10000)
        page.wait_for_timeout(1500)
        login_link = page.locator("a:has-text('로그인')")
        if not login_link.is_visible(timeout=2000):
            result["logged_in"] = True
            result["method"] = "page"
    except Exception:
        pass

    return result
