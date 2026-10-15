"""
지식인 콩배너 모듈 (독립 사용)

메인 플로우에 포함되지 않음.
필요시 별도로 호출하여 사용.
"""
from playwright.sync_api import Page
from modules.bean_banner import scan_page_for_bean_banner

KIN_MAIN = "https://kin.naver.com/index.nhn"
KIN_QNA = "https://kin.naver.com/qna/list.nhn?d1id=1&dirId=101"


def click_bean_banner(page: Page) -> bool:
    """지식인 페이지에서 콩배너 확인 및 클릭."""
    print("[지식인 콩배너] 콩배너 확인 중...")

    result = scan_page_for_bean_banner(page, KIN_MAIN, "지식인_메인", actually_click=True)
    if result["clicked"]:
        return True

    result = scan_page_for_bean_banner(page, KIN_QNA, "지식인_QnA", actually_click=True)
    if result["clicked"]:
        return True

    print("[지식인 콩배너] 현재 콩배너가 보이지 않습니다.")
    return False
