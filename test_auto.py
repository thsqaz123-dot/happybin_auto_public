"""논인터랙티브 전체 자동화 테스트 (input() 없이 실행)"""
import sys
import os
import getpass
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from modules.login import create_browser_context, do_login, check_and_relogin
from modules.user_manager import get_or_create_config
from modules.session_manager import check_login_cookies
from modules.blog import do_blog_write
from modules.cafe import do_cafe_write
from modules.happybean import collect_all_beans


def _ensure_page(page):
    """페이지가 닫혔으면 복구"""
    try:
        page.url
        return page
    except Exception:
        pass
    ctx = page.context
    for pg in ctx.pages:
        try:
            pg.url
            return pg
        except Exception:
            continue
    return ctx.new_page()


def check_login(page) -> bool:
    """쿠키 기반으로 로그인 상태 확인."""
    print("[로그인] 네이버 로그인 상태 확인 중...")
    return check_login_cookies(page)


def main():
    print("=" * 50)
    print("  [테스트] 해피빈 콩 자동 수집기 (논인터랙티브)")
    print(f"  시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    username = getpass.getuser()

    user_config = get_or_create_config(username)

    print(f"\n사용자: {user_config['user_name']}")

    # 브라우저 실행
    print("\n[1/7] 브라우저 실행 중...")
    pw, context = create_browser_context(username)

    try:
        # 로그인 확인
        print("\n[2/7] 로그인 상태 확인 중...")
        if not do_login(context, username):
            print("[FAIL] 로그인에 실패했습니다.")
            return
        print("[로그인] 로그인 확인 완료!")

        page = context.pages[0] if context.pages else context.new_page()

        results = {}

        # 각 단계 전에 세션 확인
        def ensure_login():
            return check_and_relogin(context, username)

        print("\n[3/7] 블로그 글쓰기...")
        if not ensure_login():
            results["블로그 글쓰기"] = False
        else:
            blog_result = do_blog_write(page)
            results["블로그 글쓰기"] = blog_result["write_success"]
            results["블로그 콩배너"] = blog_result["banner_clicked"]

        page = _ensure_page(page)
        print("\n[4/5] 카페 글쓰기...")
        if not ensure_login():
            results["카페 글쓰기"] = False
        else:
            cafe_result = do_cafe_write(page)
            results["카페 글쓰기"] = cafe_result["write_success"]
            results["카페 콩배너"] = cafe_result["banner_clicked"]

        page = _ensure_page(page)
        print("\n[5/5] 해피빈 메인 페이지 콩 수집...")
        if not ensure_login():
            results["해피빈 콩 수집"] = False
        else:
            happybean_results = collect_all_beans(page)
            results.update(happybean_results)

        print("\n" + "=" * 50)
        print("  실행 결과 요약")
        print("=" * 50)
        for name, success in results.items():
            status = "성공" if success else "실패"
            print(f"  [{status}] {name}")

        success_count = sum(1 for v in results.values() if v)
        total = len(results)
        print(f"\n  총 {total}개 중 {success_count}개 성공")
        print(f"  예상 획득 콩: 약 {success_count}콩")

    finally:
        context.close()
        pw.stop()
        print("\n[완료] 브라우저 연결 종료.")


if __name__ == "__main__":
    main()
