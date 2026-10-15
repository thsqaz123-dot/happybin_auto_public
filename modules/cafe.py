"""
카페 글쓰기 모듈

진단 결과 기반 실제 셀렉터 사용:
  - 게시판선택: button:has-text("게시판을 선택해 주세요.")
  - 자유게시판: button.option:has-text("자유게시판")
  - 제목: textarea[placeholder="제목을 입력해 주세요."]
  - 본문: .se-content-guide (또는 [contenteditable="true"])
  - 등록: a.BaseButton:has-text("등록")
  - iframe 없음 (직접 페이지)

동선:
  글쓰기 진입 → 게시판선택 → 제목입력 → 본문입력 → 등록클릭 →
  등록 후 페이지 대기 → 콩배너 확인
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
import config
from content.templates import random_cafe_post
from modules.utils import safe_goto
from modules.session_manager import check_login_cookies
from modules.bean_banner import check_bean_banner_exists, hover_and_click_bean_banner


def _print_cafe_page_diagnostics(page: Page, response=None) -> None:
    """카페 진입/등록 실패 시 현재 페이지의 원인을 남긴다."""
    status = response.status if response else "응답 없음"
    try:
        title = page.title()
    except Exception:
        title = "확인 실패"

    try:
        text = " ".join(page.locator("body").inner_text(timeout=2000).split())[:300]
    except Exception:
        text = "확인 실패"

    print(f"[카페] 진단: HTTP={status}, URL={page.url}, 제목={title}")
    print(f"[카페] 진단: 페이지 메시지={text}")


def _wait_for_write_form(page: Page, timeout: int = 15000) -> bool:
    """카페 글쓰기 폼 로드 대기"""
    try:
        # 네이버 UI 문구가 바뀌어도 제목 필드가 나타나면 글쓰기 폼으로 판단한다.
        page.locator(
            'button:has-text("게시판을 선택해 주세요."):visible, '
            'textarea[placeholder="제목을 입력해 주세요."]:visible, '
            'textarea[placeholder*="제목"]:visible'
        ).first.wait_for(
            state="visible", timeout=timeout
        )
        return True
    except PlaywrightTimeout:
        print(f"[카페] 글쓰기 폼 로드 타임아웃 ({timeout / 1000:.0f}초)")
        return False


def _try_open_write_from_cafe_home(page: Page) -> bool:
    """직접 글쓰기 URL이 차단된 환경에서 카페 메인의 글쓰기 동선을 사용한다."""
    print("[카페] 카페 메인 글쓰기 동선으로 재시도...")
    if not safe_goto(page, config.CAFE_URL, wait_until="domcontentloaded", timeout=config.TIMEOUT):
        return False

    try:
        join_button = page.locator('a:has-text("카페 가입하기"):visible, '
                                   'button:has-text("카페 가입하기"):visible').first
        if join_button.is_visible(timeout=2000):
            print("[카페] 카페 가입/글쓰기 권한 필요: 해당 네이버 계정으로 카페에 가입하세요.")
            return False
    except Exception:
        pass

    for selector in ['a:has-text("글쓰기"):visible', 'button:has-text("글쓰기"):visible']:
        try:
            button = page.locator(selector).first
            button.click()
            return _wait_for_write_form(page, timeout=config.TIMEOUT)
        except Exception:
            continue
    return False


def navigate_to_write(page: Page) -> bool:
    """카페 글쓰기 페이지 진입"""
    if not config.CAFE_WRITE_URL:
        print("[카페] HAPPYBIN_CAFE_ID와 HAPPYBIN_CAFE_URL을 설정해야 합니다. 카페 작업을 건너뜁니다.")
        return False
    print("[카페] 글쓰기 페이지 이동...")
    response = safe_goto(
        page, config.CAFE_WRITE_URL, wait_until="domcontentloaded", timeout=config.TIMEOUT
    )
    if not response:
        print("[카페] 글쓰기 페이지 이동 실패")
        _print_cafe_page_diagnostics(page)
        return False
    page.wait_for_timeout(3000)

    if "nid.naver.com" in page.url:
        print("[카페] 로그인 페이지로 리디렉션됨")
        _print_cafe_page_diagnostics(page, response)
        return False

    if not check_login_cookies(page):
        print("[카페] 로그인 필요")
        _print_cafe_page_diagnostics(page, response)
        return False

    if not _wait_for_write_form(page, timeout=config.TIMEOUT):
        if _try_open_write_from_cafe_home(page):
            print("[카페] 카페 메인 경유 글쓰기 폼 로드 완료")
            return True
        _print_cafe_page_diagnostics(page, response)
        return False

    print("[카페] 글쓰기 폼 로드 완료")
    return True


def select_board(page: Page) -> bool:
    """자유게시판 선택"""
    try:
        board_btn = page.locator('button:has-text("게시판을 선택해 주세요.")').first
        if not board_btn.is_visible(timeout=5000):
            print("[카페] 게시판 이미 선택됨")
            return True

        board_btn.click(force=True)
        page.wait_for_timeout(2000)

        free_board = page.locator(
            'button.option:has-text("자유게시판"):visible, '
            '[role="option"]:has-text("자유게시판"):visible, '
            'button:has-text("자유게시판"):visible'
        ).first
        free_board.wait_for(state="visible", timeout=5000)
        free_board.click(force=True)

        page.locator('textarea[placeholder*="제목"]:visible').first.wait_for(
            state="visible", timeout=5000
        )

        print("[카페] 자유게시판 선택 완료")
        return True
    except Exception as e:
        print(f"[카페] 게시판 선택 실패: {e}")
        return False


def fill_content(page: Page, title: str, body: str) -> bool:
    """제목 + 본문 입력"""
    # 제목 입력
    try:
        title_input = page.locator(
            'textarea[placeholder="제목을 입력해 주세요."]:visible, '
            'textarea[placeholder*="제목"]:visible'
        ).first
        title_input.wait_for(state="visible", timeout=5000)
        title_input.click()
        page.wait_for_timeout(300)
        title_input.fill(title)
        print(f"[카페] 제목 입력 완료: {title[:30]}")
    except Exception as e:
        print(f"[카페] 제목 입력 실패: {e}")
        return False

    page.wait_for_timeout(500)

    # 본문 입력
    body_filled = False
    for sel in ['.se-content-guide', '[contenteditable="true"]', 'div[role="textbox"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click(force=True)
                page.wait_for_timeout(300)
                page.keyboard.type(body, delay=20)
                print(f"[카페] 본문 입력 완료 ({sel})")
                body_filled = True
                break
        except Exception:
            continue

    if not body_filled:
        print("[카페] 본문 입력 실패: 입력 가능한 요소 없음")
        return False

    return True


def submit(page: Page) -> bool:
    """
    등록 버튼 클릭 → 등록 후 페이지 대기

    등록 후 카페 글 보기 페이지로 전환된다.
    """
    # 등록 버튼 클릭 (a.BaseButton 우선)
    submitted = False
    for sel in ['a.BaseButton:has-text("등록")', 'button:has-text("등록")']:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=3000):
                btn.click(force=True)
                print("[카페] 등록 버튼 클릭")
                submitted = True
                break
        except Exception:
            continue

    if not submitted:
        print("[카페] 등록 버튼 미발견")
        _print_cafe_page_diagnostics(page)
        return False

    # 등록 후 페이지 전환 대기
    print("[카페] 등록 후 페이지 전환 대기...")
    for _ in range(8):
        current = page.url
        is_article_page = (
            ("/articles/" in current and "/write" not in current)
            or "ArticleRead.nhn" in current
        )
        if is_article_page:
            print(f"[카페] 등록 완료! 현재 URL: {current}")
            return True
        page.wait_for_timeout(1000)

    print(f"[카페] 등록 후 게시글 페이지 미전환: {page.url}")
    _print_cafe_page_diagnostics(page)
    return False


def check_bean_banner_after_submit(page: Page, actually_click: bool = True) -> tuple[bool, bool]:
    """등록 후 늦게 로드되는 콩배너를 재탐색하고 클릭한다.

    Returns:
        ``(banner_found, banner_clicked)``
    """
    page.bring_to_front()
    for attempt in range(1, 11):
        # 카페는 배너가 비동기로 붙고 iframe 안에서 렌더링되기도 한다.
        # 각 프레임을 한 번씩 스크롤해 lazy load를 유도한 후 재검사한다.
        for frame in page.frames:
            try:
                frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                frame.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass
        page.wait_for_timeout(1500)

        check = check_bean_banner_exists(page)
        if not check["exists"]:
            print(f"[카페] 콩배너 로드 대기 중... ({attempt}/10)")
            continue

        print(f"[카페] 등록 후 콩배너 발견! (type='{check['container_id']}')")
        result = hover_and_click_bean_banner(page, actually_click=actually_click)
        if result["clicked"]:
            print("[카페] 콩배너 클릭 완료!")
            return True, True
        if result["clickable"]:
            if not actually_click:
                print("[카페] 콩배너 감지 완료 (확인 모드, 클릭 안 함)")
                return True, False
            print("[카페] 클릭은 시도했지만 기부콩 적립 완료를 확인하지 못했습니다.")
            return True, False

        print("[카페] 콩배너는 감지됐지만 클릭 요소를 찾지 못했습니다.")
        return True, False

    print("[카페] 등록 후 15초 동안 콩배너를 찾지 못했습니다.")
    return False, False


def do_cafe_write(page: Page, actually_click_banner: bool = True) -> dict:
    """
    카페 글쓰기 전체 흐름.

    Args:
        actually_click_banner: True면 콩배너 실제 클릭 (획득), False면 존재만 확인

    Returns:
        {
            "write_success": bool,
            "banner_found": bool,
            "banner_clicked": bool,
        }
    """
    result = {
        "write_success": False,
        "banner_found": False,
        "banner_clicked": False,
    }

    title, body = random_cafe_post()

    # 1. 글쓰기 페이지 진입
    if not navigate_to_write(page):
        return result

    # 2. 게시판 선택
    if not select_board(page):
        return result

    # 3. 제목 + 본문 입력
    if not fill_content(page, title, body):
        return result

    # 4. 등록
    if not submit(page):
        return result

    result["write_success"] = True

    # 5. 등록된 글 페이지에서 콩배너를 충분히 기다린 뒤 확인한다.
    result["banner_found"], result["banner_clicked"] = check_bean_banner_after_submit(
        page, actually_click=actually_click_banner
    )

    return result
