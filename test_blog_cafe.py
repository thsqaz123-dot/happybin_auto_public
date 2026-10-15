import sys
import os
import getpass
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from modules.login import create_browser_context, do_login, check_and_relogin
from modules.user_manager import get_or_create_config
from modules.blog import do_blog_write
from modules.cafe import do_cafe_write
from modules.happybean import collect_all_beans


def print_header():
    print("=" * 50)
    print("  블로그/카페 글쓰기 + 콩 획득 테스트")
    print(f"  실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def print_result(name: str, success: bool):
    status = "성공" if success else "실패"
    print(f"  [{status}] {name}")


def main():
    print_header()

    username = getpass.getuser()

    user_config = get_or_create_config(username)

    print(f"\n사용자: {user_config['user_name']}")

    # 브라우저 실행
    print("\n[1/6] 브라우저 실행 및 로그인 확인...")
    pw, context = create_browser_context(username)

    try:
        if not do_login(context, username):
            print("로그인에 실패했습니다. 프로그램을 종료합니다.")
            return

        page = context.pages[0] if context.pages else context.new_page()

        def ensure_login():
            return check_and_relogin(context, username)

        results = {}

        print("\n[2/6] 블로그 글쓰기 (비공개)...")
        if not ensure_login():
            results["블로그 글쓰기"] = False
        else:
            blog_result = do_blog_write(page)
            results["블로그 글쓰기"] = blog_result["write_success"]
            results["블로그 콩 획득"] = blog_result["banner_clicked"]

        print("\n[3/6] 카페 글쓰기 (공개)...")
        if not ensure_login():
            results["카페 글쓰기"] = False
        else:
            cafe_result = do_cafe_write(page)
            results["카페 글쓰기"] = cafe_result["write_success"]
            results["카페 콩 획득"] = cafe_result["banner_clicked"]

        print("\n[4/4] 해피빈 메인 페이지 콩 수집...")
        if not ensure_login():
            results["해피빈 콩 수집"] = False
        else:
            happybean_results = collect_all_beans(page)
            results.update(happybean_results)

        print("\n" + "=" * 50)
        print("  테스트 결과 요약")
        print("=" * 50)
        for name, success in results.items():
            print_result(name, success)

        success_count = sum(1 for v in results.values() if v)
        total = len(results)
        print(f"\n  총 {total}개 중 {success_count}개 성공")
        print(f"  예상 획득 콩: 약 {success_count}콩 ({success_count * 100}원 상당)")

    finally:
        print("\n브라우저를 닫으려면 Enter 키를 눌러주세요...")
        try:
            input()
        except EOFError:
            pass
        context.close()
        pw.stop()


if __name__ == "__main__":
    main()
