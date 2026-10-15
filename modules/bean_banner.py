"""
콩배너(floatingda_home / floatingda_content) 통합 모듈

네이버 전 페이지에 떠다니는 콩배너를 감지하고 상호작용한다.

배너 종류:
  1. floatingda_home  — 메인페이지용 (축소 상태, 호버 시 확장)
     <div id="floatingda_home">
       <button data-role="bannerWrapper"><img alt="상품명"></button>
       <button data-role="bannerClose">

  2. floatingda_content — 글 작성 후용 (이미 확장된 상태, 바로 클릭 가능)
     <div id="floatingda_content">
       <a data-role="bannerWrapper" href="..." target="_blank">
         ... "클릭하고 기부콩 1개 받기" ...
       </a>
       <button data-role="bannerClose">

동작 방식:
  1. 페이지에서 floatingda_home 또는 floatingda_content 탐색
  2. floatingda_home이면 호버 → 확장 → 클릭
  3. floatingda_content이면 바로 클릭 (이미 확장됨)

광고 차단 확장프로그램(uBlock, AdGuard 등)이 floatingda를 숨기므로
 headless가 아닌 실제 브라우저 + 확장프로그램 비활성화 필요.
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from modules.utils import safe_goto
import config


# ──────────────────────────────────────────────
# 콩배너가 나타나는 알려진 페이지 목록
# ──────────────────────────────────────────────
BEAN_BANNER_PAGES = {
    "블로그_메인": "https://section.blog.naver.com/BlogHome.naver?directoryNo=0&currentPage=1&groupId=0",
}
if config.CAFE_WRITE_URL:
    BEAN_BANNER_PAGES["카페_메인"] = config.CAFE_URL


def check_bean_banner_exists(page: Page) -> dict:
    """
    현재 페이지에서 floatingda 콩배너 존재 여부를 확인한다.
    메인 프레임 + 모든 iframe을 순회한다.

    Returns:
        {
            "exists": bool,
            "visible": bool,
            "container_id": str,
            "img_src": str,
            "alt_text": str,
            "page_url": str,
        }
    """
    result = {
        "exists": False,
        "visible": False,
        "container_id": "",
        "img_src": "",
        "alt_text": "",
        "page_url": page.url,
    }

    # 모든 프레임 순회 (iframe 내부에도 floatingda가 로드될 수 있음)
    for frame in page.frames:
        try:
            container = None
            banner_type = None
            for bid in ["floatingda_home", "floatingda_content", "floatingda"]:
                c = frame.locator(f"#{bid}").first
                if c.count() > 0:
                    container = c
                    banner_type = bid
                    break
            if not container:
                for selector, detected_type in [
                    ("[id*='floatingda']", "floatingda_dynamic_id"),
                    ("[class*='floatingda']", "floatingda_dynamic_class"),
                ]:
                    c = frame.locator(selector).first
                    if c.count() > 0:
                        container = c
                        banner_type = detected_type
                        break
            if not container:
                c = frame.locator('[data-container-id*="happybean"]').first
                if c.count() > 0:
                    container = c
                    banner_type = "happybean_data_attr"

            if container and container.count() > 0:
                result["exists"] = True
                result["visible"] = container.is_visible()
                result["container_id"] = banner_type or ""

                try:
                    cid = container.get_attribute("data-container-id") or ""
                    if not cid:
                        inner = container.locator("[data-container-id]").first
                        if inner.count() > 0:
                            cid = inner.get_attribute("data-container-id") or ""
                    if cid:
                        result["container_id"] = cid
                except Exception:
                    pass

                # 이미지/텍스트 추출
                for sel in ["#floatingda_content", "#floatingda_home"]:
                    try:
                        img = frame.locator(f"{sel} img").first
                        if img.count() > 0:
                            result["img_src"] = img.get_attribute("src") or ""
                            alt = img.get_attribute("alt") or ""
                            if alt:
                                result["alt_text"] = alt
                    except Exception:
                        pass

                try:
                    a_tag = frame.locator('#floatingda_content a[data-role="bannerWrapper"]').first
                    if a_tag.count() > 0 and a_tag.is_visible():
                        text = a_tag.inner_text(timeout=1000)
                        if not result["alt_text"]:
                            result["alt_text"] = text[:50].replace("\n", " ")
                except Exception:
                    pass

                break  # 찾았으면 중단
        except Exception:
            continue

    return result


def _click_and_capture_new_page(page: Page, target, timeout: int = 5000):
    """일반 사용자 클릭으로 열린 결과 탭만 추적한다."""
    try:
        with page.context.expect_page(timeout=timeout) as page_info:
            target.click(timeout=timeout)
        return page_info.value
    except PlaywrightTimeout:
        print("[콩배너] 클릭 후 새 결과 탭이 열리지 않았습니다.")
        return None


def _verify_bean_reward(new_page: Page) -> tuple[bool, str]:
    """추적 링크의 실제 이동과 화면의 적립 완료 신호를 확인한다.

    단순 click 호출은 성공으로 취급하지 않는다. 새 탭이 추적 URL에서
    벗어나고 '적립/획득/완료'와 같은 완료 문구를 보여야 True다.
    """
    try:
        new_page.bring_to_front()
        for _ in range(8):
            current_url = new_page.url
            if "tivan.naver.com" not in current_url.lower():
                break
            new_page.wait_for_timeout(1000)

        new_page.wait_for_load_state("domcontentloaded", timeout=10000)
        new_page.wait_for_timeout(1500)
        current_url = new_page.url
        print(f"[콩배너] 결과 탭 유지: {current_url}")

        if "tivan.naver.com" in current_url.lower():
            print("[콩배너] 추적 링크에서 이동하지 않았습니다. 적립을 성공으로 처리하지 않습니다.")
            return False, current_url

        try:
            text = new_page.locator("body").inner_text(timeout=5000).replace(" ", "")
        except Exception:
            text = ""
        verified_words = ("적립", "획득", "받았습니다", "지급", "완료")
        if "콩" in text and any(word in text for word in verified_words):
            print("[콩배너] 기부콩 적립 완료 신호를 확인했습니다.")
            return True, current_url

        print("[콩배너] 결과 탭은 열렸지만 적립 완료 신호를 확인하지 못했습니다.")
        return False, current_url
    except Exception as exc:
        print(f"[콩배너] 결과 탭 검증 실패: {exc}")
        return False, ""


def hover_and_click_bean_banner(page: Page, actually_click: bool = False) -> dict:
    """
    콩배너에 마우스오버하여 확장한 뒤, 클릭 가능한 요소를 찾는다.

    Args:
        page: Playwright Page 객체
        actually_click: True면 실제로 클릭 (콩 획득), False면 존재만 확인

    Returns:
        {
            "found": bool,
            "expanded": bool,
            "clickable": bool,
            "clicked": bool,
            "banner_text": str,
            "banner_href": str,
            "product_name": str,
        }
    """
    result = {
        "found": False,
        "expanded": False,
        "clickable": False,
        "clicked": False,
        "banner_text": "",
        "banner_href": "",
        "product_name": "",
        "result_url": "",
    }

    # 컨테이너 찾기 — 모든 프레임 순회 (content 우선 — 이미 확장된 상태)
    container = None
    is_expanded_type = False
    try:
        for frame in page.frames:
            for bid in ["floatingda_content", "floatingda_home", "floatingda"]:
                c = frame.locator(f"#{bid}").first
                if c.count() > 0:
                    container = c
                    is_expanded_type = (bid == "floatingda_content")
                    break
            if not container:
                for selector, detected_type in [
                    ("[id*='floatingda']", "id"),
                    ("[class*='floatingda']", "class"),
                ]:
                    c = frame.locator(selector).first
                    if c.count() > 0:
                        container = c
                        try:
                            value = (c.get_attribute("id") or c.get_attribute("class") or "").lower()
                            is_expanded_type = "content" in value
                        except Exception:
                            is_expanded_type = False
                        break
            if container:
                break
            c = frame.locator('[data-container-id*="happybean"]').first
            if c.count() > 0:
                container = c
                break
        if not container:
            return result
    except Exception:
        return result

    result["found"] = True

    # ── floatingda_content: 이미 확장됨, 바로 a[href] 클릭 ──
    if is_expanded_type:
        try:
            wrapper = container.locator('a[data-role="bannerWrapper"]').first
            if wrapper.count() == 0:
                wrapper = container.locator("a[href]").first
            if wrapper.count() == 0:
                wrapper = container.locator('[role="button"], button, [onclick]').first
            if wrapper.count() == 0:
                # 일부 카페 배너는 링크가 아니라 컨테이너 자체에 클릭 핸들러를 둔다.
                wrapper = container
            if wrapper.count() > 0:
                result["expanded"] = True
                result["clickable"] = True
                try:
                    result["banner_text"] = wrapper.inner_text(timeout=1000)[:100]
                except Exception:
                    pass
                try:
                    result["banner_href"] = wrapper.get_attribute("href") or ""
                except Exception:
                    pass

                if actually_click:
                    try:
                        new_page = _click_and_capture_new_page(page, wrapper)
                        if new_page:
                            result["clicked"], result["result_url"] = _verify_bean_reward(new_page)
                        else:
                            print("[콩배너] 적립 확인 없이 클릭을 성공으로 처리하지 않습니다.")
                    except Exception as e:
                        print(f"[콩배너] floatingda_content 클릭 실패: {e}")
        except Exception as e:
            print(f"[콩배너] floatingda_content 처리 실패: {e}")
        return result

    # ── floatingda_home: 축소 상태 → 호버 후 확장 → 클릭 ──
    try:
        wrapper = container.locator('button[data-role="bannerWrapper"]').first
        if wrapper.count() == 0:
            wrapper = container.locator("button").first
        if wrapper.count() == 0:
            return result
    except Exception:
        return result

    try:
        img = wrapper.locator("img").first
        if img.count() > 0:
            result["product_name"] = img.get_attribute("alt") or ""
    except Exception:
        pass

    # 숨겨져 있으면 대기 + 스크롤 + 강제 표시
    try:
        if not wrapper.is_visible():
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(2000)
            if not wrapper.is_visible():
                page.evaluate("""(el) => {
                    let p = el;
                    while (p && p !== document.body) {
                        const s = getComputedStyle(p);
                        if (s.display === 'none') p.style.display = 'block';
                        if (s.visibility === 'hidden') p.style.visibility = 'visible';
                        if (s.opacity === '0') p.style.opacity = '1';
                        p = p.parentElement;
                    }
                }""", wrapper.element_handle())
                page.wait_for_timeout(1000)
    except Exception:
        pass

    # 마우스오버 → 배너 확장
    try:
        wrapper.hover(force=True)
        page.wait_for_timeout(1500)
        result["expanded"] = True
    except Exception:
        try:
            box = wrapper.bounding_box()
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.wait_for_timeout(1500)
                result["expanded"] = True
        except Exception:
            pass

    # 확장된 배너 내부에서 클릭 가능한 요소 탐색
    clickable_selectors = [
        'a[href]',
        'button[data-role="bannerWrapper"]',
        'button:not([data-role="bannerClose"])',
        '[role="button"]',
        '[onclick]',
    ]

    click_target = None
    # locator(selector)는 자식만 찾으므로, 컨테이너 자신이 링크/버튼인
    # 경우를 먼저 별도로 검사한다.
    try:
        is_clickable_container = container.evaluate("""el =>
            el.matches('a[href], button, [role="button"], [onclick]')
        """)
        if is_clickable_container:
            click_target = container
    except Exception:
        pass

    for sel in clickable_selectors:
        if click_target:
            break
        try:
            candidates = container.locator(sel).all()
            for c in candidates:
                if not c.is_visible():
                    continue
                role = c.get_attribute("data-role") or ""
                if role == "bannerClose":
                    continue
                click_target = c
                break
            if click_target:
                break
        except Exception:
            continue

    if not click_target:
        # 동적 카페 배너는 별도 링크 없이 floatingda 컨테이너 클릭으로
        # 이동하는 경우가 있다. 마지막 수단으로 본체를 클릭한다.
        click_target = container
        print("[콩배너] 표준 클릭 요소 없음 — 배너 본체 클릭을 시도합니다.")

    if click_target:
        result["clickable"] = True
        try:
            result["banner_text"] = click_target.inner_text(timeout=1000)[:100]
        except Exception:
            pass
        try:
            result["banner_href"] = click_target.get_attribute("href") or ""
        except Exception:
            pass

        if actually_click:
            try:
                new_page = _click_and_capture_new_page(page, click_target)
                if new_page:
                    result["clicked"], result["result_url"] = _verify_bean_reward(new_page)
                else:
                    print("[콩배너] 적립 확인 없이 클릭을 성공으로 처리하지 않습니다.")
            except Exception:
                pass

    return result


def scan_page_for_bean_banner(page: Page, url: str, page_name: str,
                               actually_click: bool = False) -> dict:
    """
    특정 페이지로 이동하여 콩배너를 스캔한다.
    """
    print(f"\n[콩배너] === {page_name} 스캔 ===")
    print(f"[콩배너] URL: {url}")

    if not safe_goto(page, url, wait_until="domcontentloaded", timeout=15000):
        print(f"[콩배너] {page_name}: 페이지 이동 실패")
        return {
            "page_name": page_name,
            "url": url,
            "exists": False,
            "expanded": False,
            "clickable": False,
            "clicked": False,
            "product_name": "",
            "banner_text": "",
        }
    page.wait_for_timeout(3000)

    check = check_bean_banner_exists(page)
    if not check["exists"]:
        print(f"[콩배너] {page_name}: 배너 없음")
        return {
            "page_name": page_name,
            "url": url,
            "exists": False,
            "expanded": False,
            "clickable": False,
            "clicked": False,
            "product_name": "",
            "banner_text": "",
        }

    print(f"[콩배너] {page_name}: 배너 발견! (visible={check['visible']}, "
          f"alt='{check['alt_text']}')")

    hover_result = hover_and_click_bean_banner(page, actually_click=actually_click)

    status = "클릭됨" if hover_result["clicked"] else (
        "클릭가능" if hover_result["clickable"] else "확장됨" if hover_result["expanded"] else "감지됨"
    )
    prod = hover_result["product_name"]
    btxt = hover_result["banner_text"][:30]
    print(f"[콩배너] {page_name}: {status} (상품='{prod}', text='{btxt}')")

    return {
        "page_name": page_name,
        "url": url,
        "exists": True,
        "expanded": hover_result["expanded"],
        "clickable": hover_result["clickable"],
        "clicked": hover_result["clicked"],
        "product_name": hover_result["product_name"],
        "banner_text": hover_result["banner_text"],
    }


def scan_all_bean_banners(page: Page, actually_click: bool = False) -> list[dict]:
    """
    모든 알려진 페이지에서 콩배너를 스캔한다.
    """
    print("\n[콩배너] ========== 전체 콩배너 스캔 시작 ==========")
    results = []

    for page_name, url in BEAN_BANNER_PAGES.items():
        result = scan_page_for_bean_banner(page, url, page_name, actually_click)
        results.append(result)

    found = sum(1 for r in results if r["exists"])
    clickable = sum(1 for r in results if r["clickable"])
    clicked = sum(1 for r in results if r["clicked"])

    print(f"\n[콩배너] ========== 스캔 완료 ==========")
    print(f"[콩배너] 총 {len(results)}개 페이지 스캔")
    print(f"[콩배너] 배너 발견: {found}개")
    print(f"[콩배너] 클릭 가능: {clickable}개")
    if actually_click:
        print(f"[콩배너] 클릭 완료: {clicked}개")

    for r in results:
        icon = "O" if r["exists"] else "X"
        extra = ""
        if r["exists"]:
            if r["clicked"]:
                extra = " [클릭됨]"
            elif r["clickable"]:
                extra = " [클릭가능]"
            else:
                extra = " [확장됨]"
        print(f"  [{icon}] {r['page_name']}{extra}")

    return results


def collect_bean_banners_on_current_page(page: Page, actually_click: bool = False) -> dict:
    """
    현재 페이지(이동 없이)에서 콩배너를 확인한다.
    """
    page_name = f"현재페이지 ({page.url[:50]})"
    check = check_bean_banner_exists(page)

    if not check["exists"]:
        print(f"[콩배너] 현재 페이지: 배너 없음")
        return {
            "page_name": page_name,
            "url": page.url,
            "exists": False,
            "expanded": False,
            "clickable": False,
            "clicked": False,
            "product_name": "",
            "banner_text": "",
        }

    print(f"[콩배너] 현재 페이지에서 배너 발견! (alt='{check['alt_text']}')")
    hover_result = hover_and_click_bean_banner(page, actually_click=actually_click)

    return {
        "page_name": page_name,
        "url": page.url,
        "exists": True,
        "expanded": hover_result["expanded"],
        "clickable": hover_result["clickable"],
        "clicked": hover_result["clicked"],
        "product_name": hover_result["product_name"],
        "banner_text": hover_result["banner_text"],
    }
