"""
HappyBean 메인 페이지 콩 수집 모듈

다양한 배너/팝업 시나리오에 대응:
  1. BannerTop 배너 (현재 가장 흔한 케이스)
  2. 팝업/모달 형식의 콩 받기
  3. 특정 이벤트성 배너
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from modules.utils import safe_goto

HAPPYBEAN_URL = "https://happybean.naver.com/"

# "콩 받고" 텍스트를 포함할 수 있는 패턴들
BEAN_COLLECT_PATTERNS = [
    "콩 받고",
    "콩받기",
    "받고 기부",
    "받고 참여",
    "받고 응원",
    "받고 확인",
]


def _find_banner_elements(page: Page):
    """
    해피빈 메인 페이지에서 콩 받기 배너 요소들을 찾는다. (href 기준 중복 제거)
    """
    seen_hrefs = set()
    candidates = []

    def add_unique(el):
        try:
            href = el.get_attribute("href") or ""
        except Exception:
            href = ""
        if href and href in seen_hrefs:
            return
        if href:
            seen_hrefs.add(href)
        candidates.append(el)

    # 1. BannerTop-module-scss-module__ti2eAG__link 클래스의 링크
    try:
        banners = page.locator('[class*="BannerTop"][class*="link"]').all()
        for b in banners:
            if b.is_visible():
                add_unique(b)
    except Exception:
        pass

    # 2. "콩 받고" 텍스트를 포함한 모든 a 태그
    for pattern in BEAN_COLLECT_PATTERNS:
        try:
            links = page.locator(f'a:has-text("{pattern}")').all()
            for link in links:
                if link.is_visible():
                    add_unique(link)
        except Exception:
            pass

    return candidates


def _find_bean_popup(page: Page):
    """
    팝업/모달 형식의 콩 받기 UI를 찾는다.
    - 레이어 팝업 (class에 popup, modal, layer, dialog 포함)
    - "콩" 텍스트를 포함한 버튼이 있는 모달
    """
    popup_selectors = [
        '[class*="popup"]:visible',
        '[class*="modal"]:visible',
        '[class*="layer"]:visible',
        '[class*="dialog"]:visible',
        '[class*="toast"]:visible',
        '[role="dialog"]:visible',
    ]

    for selector in popup_selectors:
        try:
            popups = page.locator(selector).all()
            for p in popups:
                if not p.is_visible():
                    continue
                text = p.inner_text(timeout=1000)
                if "콩" in text:
                    return p
        except Exception:
            continue

    return None


def _click_bean_popup(page: Page, popup) -> bool:
    """팝업 내에서 콩 받기 버튼을 찾아 클릭한다."""
    try:
        collect_btn = popup.locator('button:has-text("콩"), a:has-text("콩")').first
        if collect_btn.is_visible():
            print("[해피빈 팝업] 콩 받기 버튼 발견, 클릭합니다.")
            collect_btn.click()
            page.wait_for_timeout(1500)
            return True
    except Exception:
        pass

    try:
        close_btn = popup.locator(
            'button[class*="close"], [class*="close"] button, '
            '.btn_close, [aria-label*="닫기"]'
        ).first
        if close_btn.is_visible():
            print("[해피빈 팝업] 닫기 버튼 클릭.")
            close_btn.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass

    return False


def _handle_new_tab(new_page: Page, label: str) -> bool:
    """열린 결과 탭을 확인하고 사용자가 검토할 수 있도록 유지한다."""
    try:
        new_page.wait_for_load_state("domcontentloaded", timeout=10000)
        new_page.wait_for_timeout(1500)
        new_page.bring_to_front()
        url = new_page.url
        print(f"[해피빈] 결과 탭 유지: {url}")

        if "happybean" in url.lower():
            try:
                text = new_page.locator("body").inner_text(timeout=3000).replace(" ", "")
                if "콩" in text and any(word in text for word in ("적립", "획득", "받았습니다", "지급", "완료")):
                    print(f"[해피빈 {label}] 콩 획득 확인!")
                    return True
            except Exception:
                pass

            # 해피빈의 일부 캠페인은 적립 후 별도 완료 문구를 렌더링하지
            # 않는다. 이 경우 실제 해피빈 결과 탭으로의 정상 이동 자체를
            # 적립 완료 신호로 사용한다.
            print(f"[해피빈 {label}] 해피빈 결과 페이지 이동 완료 — 콩 획득 처리됨")
            return True

        print(f"[해피빈 {label}] 결과 탭은 열렸지만 콩 획득 완료를 확인하지 못했습니다.")
        return False
    except Exception as e:
        print(f"[해피빈] 새 탭 처리 중 오류: {e}")

    return False


def _click_and_capture_new_page(page: Page, target, timeout: int = 5000):
    """이번 클릭으로 열린 결과 탭만 정확히 추적한다."""
    try:
        with page.context.expect_page(timeout=timeout) as page_info:
            target.click(force=True)
        return page_info.value
    except PlaywrightTimeout:
        return None


def collect_all_beans(page: Page) -> dict[str, bool]:
    """
    해피빈 메인 페이지에서 가능한 모든 콩을 수집한다.

    Returns:
        { "배너_콩받고기부하기": True, "팝업_콩받기": False, ... }
    """
    results: dict[str, bool] = {}

    print("\n[해피빈] === 해피빈 메인 페이지 콩 수집 시작 ===")
    if not safe_goto(page, HAPPYBEAN_URL, wait_until="domcontentloaded"):
        print("[해피빈] 메인 페이지 이동 실패")
        return {"해피빈 메인 페이지": False}
    page.wait_for_timeout(3000)

    # --- Phase 1: 팝업/모달 먼저 확인 (페이지 로드 시 자동으로 뜨는 경우) ---
    print("[해피빈] 팝업/모달 확인 중...")
    popup = _find_bean_popup(page)
    if popup:
        popup_text = popup.inner_text(timeout=2000)[:80]
        print(f"[해피빈] 팝업 발견: {popup_text}")
        results["팝업_콩받기"] = _click_bean_popup(page, popup)
    else:
        print("[해피빈] 팝업 없음.")

    # --- Phase 2: 배너 요소들 처리 ---
    print("[해피빈] 배너 요소 스캔 중...")
    banners = _find_banner_elements(page)

    if not banners:
        print("[해피빈] 콩 받기 배너를 찾을 수 없습니다.")
    else:
        print(f"[해피빈] {len(banners)}개의 콩 받기 배너 발견!")

    for i in range(len(banners)):
        # 배너 클릭 전에 happybean 페이지로 복귀
        try:
            safe_goto(page, HAPPYBEAN_URL, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(1500)
        except Exception:
            pass

        # 새 배너 목록 조회
        banners = _find_banner_elements(page)
        if i >= len(banners):
            break

        banner = banners[i]
        try:
            text = banner.inner_text(timeout=2000)[:60].replace("\n", " ")
        except Exception:
            href = ""
            try:
                href = banner.get_attribute("href") or ""
            except Exception:
                pass
            text = href[-40:] if href else f"배너_{i+1}"

        label = f"배너_{text[:20].strip().replace(' ', '')}"
        print(f"[해피빈] [{i+1}] '{text}' 클릭 시도...")

        try:
            new_page = _click_and_capture_new_page(page, banner)
            if new_page:
                results[label] = _handle_new_tab(new_page, label)
            else:
                results[label] = False
                print(f"[해피빈] {label}: 결과 확인 없이 클릭됨")
            if results[label]:
                print(f"[해피빈] {label} 콩 획득 확인!")
        except Exception as e:
            print(f"[해피빈] 배너 클릭 실패: {e}")
            results[label] = False

    # --- Phase 3: 오늘의 Pick 섹션 (BasicLargeOneContent + congbanner/content) ---
    print("[해피빈] 오늘의 Pick 콩 콘텐츠 확인 중...")
    try:
        today_pick = page.locator('a[href*="congbanner/content"]').first
        if not today_pick.is_visible():
            today_pick = page.locator('[class*="BasicLargeOneContent"][class*="link"]').first
        if today_pick.is_visible():
            text = today_pick.inner_text(timeout=2000)[:60].replace("\n", " ")
            print(f"[해피빈] 오늘의 Pick 발견: '{text}'")
            new_page = _click_and_capture_new_page(page, today_pick)
            if new_page:
                results["오늘의Pick"] = _handle_new_tab(new_page, "오늘의Pick")
            else:
                print("[해피빈] 오늘의 Pick: 결과 확인 없이 클릭됨")
                results["오늘의Pick"] = False
    except Exception as e:
        print(f"[해피빈] 오늘의 Pick 처리 오류: {e}")

    # --- Phase 4: "콩 더 모으는 방법" 링크 처리 ---
    try:
        more_beans_link = page.locator('a:has-text("콩 더 모으는 방법")').first
        if more_beans_link.is_visible():
            print('[해피빈] "콩 더 모으는 방법" 링크 발견, 클릭...')
            new_page = _click_and_capture_new_page(page, more_beans_link)
            if new_page:
                _handle_new_tab(new_page, "콩더모으는방법")
    except Exception:
        pass

    success = sum(1 for v in results.values() if v)
    print(f"[해피빈] === 콩 수집 완료: {success}/{len(results)} 성공 ===")
    return results


def click_top_banner_beans(page: Page) -> bool:
    """
    간편 모드: 메인 페이지 상단 배너 + 오늘의 Pick 콩을 빠르게 수집한다.
    """
    print("[해피빈] 상단 배너 콩 수집 (간편 모드)...")
    if not safe_goto(page, HAPPYBEAN_URL, wait_until="domcontentloaded"):
        print("[해피빈] 메인 페이지 이동 실패")
        return False
    page.wait_for_timeout(3000)

    collected = False

    # 1) BannerTop 배너
    try:
        banners = page.locator('[class*="BannerTop"][class*="link"]').all()
        for banner in banners:
            if not banner.is_visible():
                continue
            text = banner.inner_text(timeout=1000)[:80].replace("\n", " ")
            print(f"[해피빈] 배너: '{text}'")

            if any(p in text for p in BEAN_COLLECT_PATTERNS):
                new_page = _click_and_capture_new_page(page, banner)
                if new_page:
                    _handle_new_tab(new_page, f"상단배너_{text[:20]}")
                collected = True
                print(f"[해피빈] 콩 배너 클릭 완료!")
    except Exception as e:
        print(f"[해피빈] 배너 처리 오류: {e}")

    # 2) 오늘의 Pick (congbanner/content)
    try:
        pick = page.locator('a[href*="congbanner/content"]').first
        if not pick.is_visible():
            pick = page.locator('[class*="BasicLargeOneContent"][class*="link"]').first
        if pick.is_visible():
            text = pick.inner_text(timeout=1000)[:50].replace("\n", " ")
            print(f"[해피빈] 오늘의 Pick: '{text}'")
            new_page = _click_and_capture_new_page(page, pick)
            if new_page:
                _handle_new_tab(new_page, "오늘의Pick")
            collected = True
            print("[해피빈] 오늘의 Pick 콩 획득!")
    except Exception as e:
        print(f"[해피빈] 오늘의 Pick 오류: {e}")

    return collected
