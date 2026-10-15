"""UI와 CLI가 공통으로 사용하는 자동화 실행 흐름."""
from __future__ import annotations

import getpass
import traceback
from collections.abc import Callable
from threading import Event

from modules.login import check_and_relogin, create_browser_context, do_login
from modules.user_manager import get_or_create_config
from modules.blog import do_blog_write
from modules.cafe import do_cafe_write
from modules.happybean import collect_all_beans
from modules.bean_banner import scan_all_bean_banners
from modules.utils import safe_goto

ProgressCallback = Callable[[str, str], None]


class AutomationCancelled(Exception):
    """사용자가 UI에서 취소를 요청했을 때 사용한다."""


def _notify(callback: ProgressCallback | None, state: str, message: str) -> None:
    print(message)
    if callback:
        callback(state, message)


def run_automation(username: str | None = None, on_progress: ProgressCallback | None = None,
                   cancel_event: Event | None = None) -> dict:
    """전체 수집을 실행하고 UI에 표시할 결과 사전을 반환한다."""
    username = username or getpass.getuser()
    user_config = get_or_create_config(username)
    _notify(on_progress, "starting", f"사용자: {user_config['user_name']}")

    def ensure_not_cancelled() -> None:
        if cancel_event and cancel_event.is_set():
            raise AutomationCancelled()

    pw = None
    context = None
    results: dict[str, bool] = {}
    try:
        ensure_not_cancelled()
        _notify(on_progress, "login", "[1/5] 브라우저 실행 및 로그인 상태 확인...")
        pw, context = create_browser_context(username)
        if not do_login(context, username, cancel_check=lambda: bool(cancel_event and cancel_event.is_set())):
            ensure_not_cancelled()
            _notify(on_progress, "failed", "로그인에 실패했습니다.")
            return {"로그인": False}

        page = context.pages[0] if context.pages else context.new_page()

        def run_phase(name: str, action: Callable[[], object], fallback: object) -> object:
            ensure_not_cancelled()
            try:
                # 결과 탭이 열려 있어도 다음 자동화 단계의 실제 작업 탭을
                # 사용자가 바로 볼 수 있도록 전면으로 가져온다.
                page.bring_to_front()
                value = action()
                ensure_not_cancelled()
                return value
            except AutomationCancelled:
                raise
            except Exception as exc:
                print(f"[{name}] 실행 실패: {exc}")
                results[name] = False
                return fallback

        def reset_page() -> None:
            nonlocal page
            ensure_not_cancelled()
            try:
                if page.is_closed():
                    page = context.new_page()
                if not safe_goto(page, "https://www.naver.com", wait_until="commit", timeout=10000):
                    print("[브라우저] 다음 단계 전 페이지 초기화 실패")
                else:
                    page.wait_for_timeout(1000)
            except Exception as exc:
                print(f"[브라우저] 다음 단계 전 페이지 초기화 실패: {exc}")

        def ensure_login() -> bool:
            try:
                logged_in = check_and_relogin(
                    context, username, cancel_check=lambda: bool(cancel_event and cancel_event.is_set())
                )
                ensure_not_cancelled()
                return logged_in
            except AutomationCancelled:
                raise
            except Exception as exc:
                print(f"[로그인] 확인 실패 (브라우저 상태 이상): {exc}")
                return False

        _notify(on_progress, "blog", "[2/5] 블로그 글쓰기...")
        if not ensure_login():
            results["블로그 글쓰기"] = False
        else:
            blog_result = run_phase("블로그 글쓰기", lambda: do_blog_write(page), {
                "write_success": False, "banner_found": False, "banner_clicked": False,
            })
            results["블로그 글쓰기"] = blog_result["write_success"]
            if blog_result["banner_found"]:
                results["블로그 콩배너"] = blog_result["banner_clicked"]

        reset_page()
        _notify(on_progress, "cafe", "[3/5] 카페 글쓰기...")
        if not ensure_login():
            results["카페 글쓰기"] = False
        else:
            cafe_result = run_phase("카페 글쓰기", lambda: do_cafe_write(page), {
                "write_success": False, "banner_found": False, "banner_clicked": False,
            })
            results["카페 글쓰기"] = cafe_result["write_success"]
            if cafe_result["banner_found"]:
                results["카페 콩배너"] = cafe_result["banner_clicked"]

        reset_page()
        _notify(on_progress, "banners", "[4/5] 메인 페이지 콩배너 스캔...")
        if not ensure_login():
            results["메인 배너 스캔"] = False
        else:
            banner_results = run_phase(
                "메인 배너 스캔", lambda: scan_all_bean_banners(page, actually_click=True), []
            )
            for item in banner_results:
                results[f"콩배너_{item['page_name']}"] = item["clicked"] if item["exists"] else False

        ensure_not_cancelled()
        _notify(on_progress, "happybean", "[5/5] 해피빈 메인 페이지 콩 수집...")
        if not ensure_login():
            results["해피빈 콩 수집"] = False
        else:
            happybean_results = run_phase("해피빈 콩 수집", lambda: collect_all_beans(page), {})
            results.update(happybean_results)

        _notify(on_progress, "complete", _format_summary(results))
        return results
    except AutomationCancelled:
        _notify(on_progress, "cancelled", "실행이 취소되었습니다.")
        return results
    except Exception as exc:
        _notify(on_progress, "failed", f"오류 발생: {exc}")
        print(traceback.format_exc())
        return results
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass


def _format_summary(results: dict[str, bool]) -> str:
    total = len(results)
    successful = sum(1 for value in results.values() if value)
    lines = ["", "=" * 50, "실행 결과 요약", "=" * 50]
    lines.extend(f"  [{'성공' if ok else '실패'}] {name}" for name, ok in results.items())
    lines.append(f"총 {total}개 중 {successful}개 성공")
    return "\n".join(lines)
