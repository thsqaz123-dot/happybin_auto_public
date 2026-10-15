"""
블로그 글쓰기 모듈

진단 결과 기반 실제 셀렉터 사용:
  - iframe: mainFrame
  - 제목: .se-documentTitle .se-text-paragraph (tag=P, contentEditable=inherit)
  - 본문: .se-component:not(.se-documentTitle) .se-text-paragraph
  - 발행: button.publish_btn__m9KHH (text='발행')
  - 비공개: label[for="open_private"]
  - 최종확인: button.confirm_btn__WEaBq 또는 button[data-testid="seOnePublishBtn"]

동선:
  글쓰기 진입 → 초안팝업 닫기 → 제목입력 → 본문입력 → 발행클릭 →
  비공개선택 → 최종발행 → 발행된 글 페이지 대기 → 콩배너 확인
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from urllib.parse import parse_qs, urlparse
from content.templates import random_blog_post
from modules.utils import safe_goto
from modules.session_manager import check_login_cookies
from modules.bean_banner import check_bean_banner_exists, hover_and_click_bean_banner

BLOG_WRITE = "https://blog.naver.com/GoBlogWrite.naver"


def _get_main_frame(page: Page):
    """mainFrame iframe 반환"""
    for frame in page.frames:
        if frame.name == "mainFrame":
            return frame
    return None


def _dismiss_draft_popup(page: Page):
    """초안 팝업 → 취소 (최대 3회)"""
    frame = _get_main_frame(page)
    if not frame:
        return

    for _ in range(3):
        dismissed = False
        for loc in [
            frame.locator("button.se-popup-button-cancel"),
            page.locator("button.se-popup-button-cancel"),
        ]:
            try:
                btn = loc.first
                if btn.is_visible(timeout=2000):
                    btn.click(force=True)
                    page.wait_for_timeout(800)
                    dismissed = True
                    print("[블로그] 초안 팝업 → 취소")
                    break
            except Exception:
                pass
        if not dismissed:
            break


def _dismiss_help_popup(page: Page):
    """에디터 우측의 작성 도움말 패널을 닫아 발행 버튼을 가리지 않게 한다."""
    frame = _get_main_frame(page)
    scopes = [scope for scope in (frame, page) if scope]
    selectors = [
        "button.se-help-panel-close-button",
        'button:has-text("닫기")',
        '[class*="help"][class*="panel"] button[class*="close"]',
        '[class*="guide"][class*="panel"] button[class*="close"]',
        '[class*="tutorial"] button[class*="close"]',
        '[class*="help"] button[aria-label*="닫기"]',
        '[class*="guide"] button[aria-label*="닫기"]',
    ]

    for scope in scopes:
        for selector in selectors:
            try:
                btn = scope.locator(selector).first
                if (btn.is_visible(timeout=500)
                        and btn.inner_text(timeout=500).strip() in {"", "닫기"}):
                    btn.click(force=True)
                    page.wait_for_timeout(300)
                    print("[블로그] 작성 도움말 패널 닫기")
                    return
            except Exception:
                continue


def _wait_for_editor(page: Page, timeout: int = 15000) -> bool:
    """에디터(mainFrame 내 제목 입력란) 로드 대기"""
    try:
        page.wait_for_timeout(2000)
        frame = _get_main_frame(page)
        if not frame:
            page.wait_for_timeout(3000)
            frame = _get_main_frame(page)
        if not frame:
            print("[블로그] mainFrame을 찾을 수 없습니다")
            return False

        title_el = _title_locator(frame)
        title_el.wait_for(state="visible", timeout=timeout)
        return True
    except PlaywrightTimeout:
        print("[블로그] 에디터 로드 타임아웃")
        return False


def _title_locator(frame):
    """현재 스마트에디터 버전별 제목 입력 요소를 찾는다."""
    for selector in [
        ".se-documentTitle [contenteditable='true']",
        ".se-documentTitle .se-text-paragraph",
        "[data-placeholder*='제목'][contenteditable='true']",
    ]:
        locator = frame.locator(selector).first
        try:
            if locator.is_visible(timeout=1000):
                return locator
        except Exception:
            continue
    return frame.locator(".se-documentTitle .se-text-paragraph").first


def _write_and_verify(locator, value: str, label: str, delay: int) -> bool:
    """대상 locator에 직접 입력한 뒤 에디터에 실제 반영됐는지 확인한다."""
    try:
        locator.click(timeout=5000)
        locator.press("Control+A")
        locator.press("Backspace")
        locator.press_sequentially(value, delay=delay)
        if value.strip() in locator.inner_text(timeout=3000).strip():
            return True
        print(f"[블로그] {label} 입력 검증 실패")
    except Exception as exc:
        print(f"[블로그] {label} 직접 입력 실패: {exc}")

    try:
        locator.evaluate("""(node, text) => {
            node.focus();
            node.textContent = text;
            node.dispatchEvent(new InputEvent('input', {
                bubbles: true, inputType: 'insertText', data: text
            }));
            node.dispatchEvent(new Event('change', { bubbles: true }));
        }""", value)
        if value.strip() in locator.inner_text(timeout=3000).strip():
            print(f"[블로그] {label} fallback 입력 완료")
            return True
    except Exception as exc:
        print(f"[블로그] {label} fallback 입력 실패: {exc}")
    return False


def _has_title(frame) -> bool:
    try:
        return bool(_title_locator(frame).inner_text(timeout=2000).strip())
    except Exception:
        return False


def navigate_to_write(page: Page) -> bool:
    """블로그 글쓰기 페이지 진입 + 에디터 로드 대기"""
    print("[블로그] 글쓰기 페이지 이동...")
    if not safe_goto(page, BLOG_WRITE, wait_until="domcontentloaded"):
        print("[블로그] 글쓰기 페이지 이동 실패")
        return False
    page.wait_for_timeout(3000)

    if not check_login_cookies(page):
        print("[블로그] 로그인 필요")
        return False

    _dismiss_draft_popup(page)

    if not _wait_for_editor(page):
        return False

    _dismiss_help_popup(page)

    print("[블로그] 에디터 로드 완료")
    return True


def fill_editor(page: Page, title: str, body: str) -> bool:
    """제목 + 본문 입력"""
    frame = _get_main_frame(page)
    if not frame:
        print("[블로그] mainFrame 없음")
        return False

    _dismiss_draft_popup(page)
    _dismiss_help_popup(page)

    # 제목 입력
    try:
        title_el = _title_locator(frame)
        title_el.wait_for(state="visible", timeout=5000)
        if not _write_and_verify(title_el, title, "제목", 30):
            return False
        print(f"[블로그] 제목 입력 완료: {title[:30]}")
    except Exception as e:
        print(f"[블로그] 제목 입력 실패: {e}")
        return False

    page.wait_for_timeout(500)

    # 본문 입력
    try:
        body_el = frame.locator(
            ".se-component:not(.se-documentTitle) .se-text-paragraph"
        ).first
        body_el.wait_for(state="visible", timeout=5000)
        if not _write_and_verify(body_el, body, "본문", 20):
            return False
        print("[블로그] 본문 입력 완료")
    except Exception as e:
        print(f"[블로그] 본문 입력 실패: {e}")
        return False

    return True


def publish(page: Page) -> bool:
    """
    발행 클릭 → 비공개 선택 → 최종 발행 → 발행된 글 페이지 대기

    발행 후 페이지가 https://blog.naver.com/blogId/postId 형태로 전환된다.

    주의: locator().click(force=True)는 React synthetic event를 트리거하지 못하므로
          frame.evaluate()로 DOM 직접 click을 사용한다.
    """
    frame = _get_main_frame(page)
    if not frame:
        print("[블로그] mainFrame 없음")
        return False

    if not _has_title(frame):
        print("[블로그] 제목이 비어 있어 발행하지 않습니다.")
        return False

    _dismiss_draft_popup(page)
    _dismiss_help_popup(page)

    # 1차 발행 버튼 클릭 (JS evaluate - React 이벤트 트리거 보장)
    try:
        result = frame.evaluate("""
            () => {
                const btn = document.querySelector('button.publish_btn__m9KHH')
                    || [...document.querySelectorAll('button')].find((button) =>
                        button.textContent.trim() === '발행' && !button.disabled
                    );
                if (!btn) return 'not_found';
                btn.click();
                return 'clicked';
            }
        """)
        if result == "not_found":
            print("[블로그] 발행 버튼 미발견")
            return False
        print("[블로그] 1차 발행 버튼 클릭")
    except Exception as e:
        print(f"[블로그] 발행 버튼 클릭 실패: {e}")
        return False

    page.wait_for_timeout(3000)

    # 발행 팝업 확인
    try:
        popup = frame.evaluate("""
            () => {
                const priv = document.querySelector('label[for="open_private"]');
                const confirm = document.querySelector('button[data-testid="seOnePublishBtn"]')
                             || document.querySelector('button.confirm_btn__WEaBq');
                return { has_private: !!priv, has_confirm: !!confirm };
            }
        """)
        if not popup['has_private'] and not popup['has_confirm']:
            print("[블로그] 발행 팝업 미열림, 재시도...")
            _dismiss_help_popup(page)
            frame.evaluate("""() => {
                const b = document.querySelector('button.publish_btn__m9KHH')
                    || [...document.querySelectorAll('button')].find((button) =>
                        button.textContent.trim() === '발행' && !button.disabled
                    );
                if (b) b.click();
            }""")
            page.wait_for_timeout(3000)
    except Exception:
        pass

    # 비공개 라디오 선택 (JS evaluate)
    try:
        frame.evaluate("""
            () => {
                const label = document.querySelector('label[for="open_private"]');
                if (label) label.click();
            }
        """)
        page.wait_for_timeout(300)
        print("[블로그] 비공개 선택 완료")
    except Exception:
        print("[블로그] 비공개 선택 스킵")

    # 최종 발행 확인 버튼 (JS evaluate)
    published = False
    try:
        result = frame.evaluate("""
            () => {
                const sels = [
                    'button[data-testid="seOnePublishBtn"]',
                    'button.confirm_btn__WEaBq',
                    'button.se-popup-button-confirm',
                ];
                for (const s of sels) {
                    const b = document.querySelector(s);
                    if (b) { b.click(); return 'clicked:' + s; }
                }
                return 'not_found';
            }
        """)
        if result.startswith("clicked"):
            print("[블로그] 최종 발행 확인 클릭")
            published = True
        else:
            print("[블로그] 최종 발행 버튼 미발견")
    except Exception as e:
        print(f"[블로그] 최종 발행 클릭 실패: {e}")

    if not published:
        return False

    # 발행 후 페이지 전환 대기
    print("[블로그] 발행 후 페이지 전환 대기...")
    page.wait_for_timeout(5000)

    for _ in range(6):
        # 스마트에디터는 top page가 아니라 mainFrame만 게시글 URL로
        # 바꾸는 경우가 있어 두 URL을 모두 확인한다.
        for current in (page.url, frame.url):
            parsed = urlparse(current)
            path_parts = [part for part in parsed.path.split("/") if part]
            query = parse_qs(parsed.query)
            is_post_url = (
                parsed.netloc == "blog.naver.com"
                and ((len(path_parts) >= 2 and path_parts[-1].isdigit())
                     or bool(query.get("logNo")))
            )
            if is_post_url:
                print(f"[블로그] 발행 완료! 현재 URL: {current}")
                return True
        page.wait_for_timeout(2000)

    print(f"[블로그] URL 미전환 (page={page.url}, frame={frame.url})")
    return False


def check_bean_banner_after_publish(page: Page, actually_click: bool = True) -> bool:
    """
    발행된 글 페이지에서 콩배너(floatingda_content/home) 확인.

    floatingda_content: 글 작성 후 이미 확장된 상태로 뜸 (호버 불필요)
    floatingda_home: 메인페이지 축소형 (호버 필요)
    """
    # 배너 로딩 대기 (동적 로드이므로 충분히 대기)
    page.wait_for_timeout(3000)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(2000)

    check = check_bean_banner_exists(page)
    if not check["exists"]:
        print("[블로그] 발행 후 콩배너 없음")
        return False

    print(f"[블로그] 발행 후 콩배너 발견! (type='{check['container_id']}')")
    result = hover_and_click_bean_banner(page, actually_click=actually_click)

    if result["clicked"]:
        print("[블로그] 콩배너 클릭 완료!")
        return True
    elif result["clickable"]:
        if not actually_click:
            print("[블로그] 콩배너 감지 완료 (확인 모드, 클릭 안 함)")
            return True
        print("[블로그] 클릭은 시도했지만 기부콩 적립 완료를 확인하지 못했습니다.")
        return False
    else:
        print("[블로그] 콩배너 확장됨 but 클릭 불가")
        return False


def do_blog_write(page: Page, actually_click_banner: bool = True) -> dict:
    """
    블로그 글쓰기 전체 흐름.

    Args:
        actually_click_banner: True면 콩배너 실제 클릭 (획득), False면 존재만 확인

    Returns:
        {
            "write_success": bool,   # 글 작성 성공 여부
            "banner_found": bool,    # 콩배너 존재 여부
            "banner_clicked": bool,  # 콩배너 클릭 여부
        }
    """
    result = {
        "write_success": False,
        "banner_found": False,
        "banner_clicked": False,
    }

    title, body = random_blog_post()

    # 1. 글쓰기 페이지 진입
    if not navigate_to_write(page):
        return result

    # 2. 제목 + 본문 입력
    if not fill_editor(page, title, body):
        return result

    # 3. 발행
    if not publish(page):
        return result

    result["write_success"] = True

    # 4. 발행된 글 페이지에서 콩배너 확인 (floatingda_content - 동적 로드)
    check = check_bean_banner_exists(page)
    result["banner_found"] = check["exists"]

    if check["exists"]:
        banner_clicked = check_bean_banner_after_publish(page, actually_click=actually_click_banner)
        result["banner_clicked"] = banner_clicked
    else:
        # floatingda_content가 동적으로 로드되지 않는 경우 (Playwright 자동화 감지)
        # 블로그 메인 페이지에서 floatingda_home 확인 (fallback)
        print("[블로그] 발행 후 floatingda_content 없음 → 블로그 메인에서 floatingda_home 확인...")
        safe_goto(page, "https://section.blog.naver.com/BlogHome.naver?directoryNo=0&currentPage=1&groupId=0",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        check_main = check_bean_banner_exists(page)
        if check_main["exists"]:
            result["banner_found"] = True
            print(f"[블로그] 메인에서 floatingda_home 발견! (alt='{check_main['alt_text']}')")
            hover_result = hover_and_click_bean_banner(page, actually_click=actually_click_banner)
            result["banner_clicked"] = hover_result["clicked"] if actually_click_banner else False
            if not actually_click_banner and hover_result["clickable"]:
                print("[블로그] 메인 콩배너 감지 완료 (확인 모드, 클릭 안 함)")
        else:
            print("[블로그] 메인에서도 콩배너 없음")

    return result
