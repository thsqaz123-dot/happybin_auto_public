"""
세션/쿠키 관리 모듈

네이버 로그인 세션을 파일로 저장/복원합니다.
- Playwright의 storage_state 활용
- 쿠키 기반 로그인 상태 확인
"""
import os
import json
import time
from collections.abc import Callable
from datetime import datetime
from playwright.sync_api import Page, BrowserContext

# 네이버 인증 관련 쿠키 이름
NAVER_AUTH_COOKIES = {"NID_AUT", "NID_SES"}

# 브라우저 프로필이 로그인 캐시의 주 저장소다. session.json은 보조 백업이다.
from modules.paths import get_app_data_dir

USER_DATA_ROOT = get_app_data_dir()


def get_session_path(username: str) -> str:
    """세션 파일 경로 반환"""
    return os.path.join(USER_DATA_ROOT, username, "session.json")


def save_session(context: BrowserContext, username: str) -> str:
    """로그인 성공 후 세션 저장"""
    session_path = get_session_path(username)
    os.makedirs(os.path.dirname(session_path), exist_ok=True)
    context.storage_state(path=session_path)
    print(f"[세션] 저장 완료: {session_path}")
    return session_path


def is_session_file_valid(username: str) -> bool:
    """세션 파일에 아직 사용할 수 있는 인증 쿠키가 있는지 확인한다."""
    session_path = get_session_path(username)
    if not os.path.exists(session_path):
        return False

    # 파일 내 인증 쿠키 존재 확인
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        now = time.time()
        auth_cookie_names = set()
        for cookie in cookies:
            expires = cookie.get("expires", -1)
            valid_expiry = expires in (-1, 0) or (
                isinstance(expires, (int, float)) and expires > now
            )
            if cookie.get("name") in NAVER_AUTH_COOKIES and valid_expiry:
                auth_cookie_names.add(cookie["name"])
        if not NAVER_AUTH_COOKIES.issubset(auth_cookie_names):
            print("[세션] 필수 인증 쿠키 없음")
            return False
        return True
    except (json.JSONDecodeError, IOError):
        return False


def check_login_cookies(page: Page) -> bool:
    """두 인증 쿠키가 모두 있는지 확인한다."""
    cookies = page.context.cookies()
    auth_cookie_names = {
        c["name"] for c in cookies
        if c["name"] in NAVER_AUTH_COOKIES
        and "naver" in c.get("domain", "")
    }
    return NAVER_AUTH_COOKIES.issubset(auth_cookie_names)


def check_login_by_page(page: Page) -> bool:
    """네이버 메인 응답과 인증 쿠키를 함께 확인한다."""
    try:
        page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
    except Exception:
        return False

    return check_login_cookies(page) and "nid.naver.com" not in page.url


def wait_for_login(page: Page, timeout: int = 300,
                   cancel_check: Callable[[], bool] | None = None) -> bool:
    """
    사용자가 직접 로그인할 때까지 대기

    로그인 성공 감지 방식:
    1. 쿠키 확인 (NID_AUT, NID_SES) - 가장 신뢰성 높음
    2. URL 변경 (nid.naver.com → naver.com) - 보조 수단

    Returns:
        True: 로그인 성공
        False: 타임아웃
    """
    print("[세션] 로그인 대기 중... (최대 %d초)" % timeout)
    start = time.time()

    while time.time() - start < timeout:
        if cancel_check and cancel_check():
            print("[세션] 로그인 대기를 중지했습니다.")
            return False
        # 1. 쿠키 확인 (우선)
        if check_login_cookies(page):
            print("[세션] 로그인 감지 (쿠키)")
            return True

        # 2. URL 확인 (보조)
        current_url = page.url
        if "naver.com" in current_url and "nid.naver.com" not in current_url:
            # nid 페이지를 벗어났으면 로그인 성공 가능성 높음
            page.wait_for_timeout(2000)
            if check_login_cookies(page):
                print("[세션] 로그인 감지 (URL + 쿠키 확인)")
                return True

        time.sleep(2)

    print("[세션] 로그인 대기 타임아웃")
    return False


def detect_captcha(page: Page) -> list:
    """
    CAPTCHA 감지

    Returns:
        CAPTCHA 요소 리스트 (없으면 빈 리스트)
    """
    found = []

    # 선택자 기반 감지
    captcha_selectors = [
        "#captcha",
        ".captcha",
        "[class*='captcha']",
        "[id*='captcha']",
        "img[src*='captcha']",
        "[class*='visualCaptcha']",
    ]
    for sel in captcha_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                found.append(sel)
        except Exception:
            pass

    # 텍스트 기반 감지
    captcha_texts = ["자동입력 방지", "보안문자", "CAPTCHA"]
    for text in captcha_texts:
        try:
            el = page.locator(f"text={text}").first
            if el.is_visible(timeout=500):
                found.append(f"text:{text}")
        except Exception:
            pass

    return found


def clear_session(username: str) -> None:
    """세션 파일 삭제"""
    session_path = get_session_path(username)
    if os.path.exists(session_path):
        os.remove(session_path)
        print(f"[세션] 세션 파일 삭제: {session_path}")


def get_session_info(username: str) -> dict:
    """세션 파일 정보 반환"""
    session_path = get_session_path(username)
    if not os.path.exists(session_path):
        return {"exists": False}

    mtime = os.path.getmtime(session_path)
    age = time.time() - mtime

    try:
        with open(session_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        auth_cookies = [c for c in cookies if c["name"] in NAVER_AUTH_COOKIES]
        return {
            "exists": True,
            "age_days": age / 86400,
            "total_cookies": len(cookies),
            "auth_cookies": [c["name"] for c in auth_cookies],
            "expired": not is_session_file_valid(username),
        }
    except (json.JSONDecodeError, IOError):
        return {"exists": True, "corrupted": True}
