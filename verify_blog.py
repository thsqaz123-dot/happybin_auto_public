"""EXE 빌드 전 블로그 제목 입력·발행 전환만 점검하는 수동 검증 도구."""
import getpass

from modules.blog import do_blog_write
from modules.login import create_browser_context, do_login
from modules.user_manager import get_or_create_config


def main() -> None:
    username = getpass.getuser()
    get_or_create_config(username)
    print("=" * 56)
    print("블로그 검증: 제목 입력 → 비공개 발행 → URL 전환")
    print("브라우저에서 제목이 실제로 입력되는지 확인하세요.")
    print("=" * 56)

    pw = None
    context = None
    try:
        pw, context = create_browser_context(username)
        if not do_login(context, username):
            print("[검증 실패] 로그인에 실패했습니다.")
            return
        page = context.pages[0] if context.pages else context.new_page()
        result = do_blog_write(page, actually_click_banner=False)
        print("\n검증 결과")
        for name, success in result.items():
            print(f"- {name}: {'성공' if success else '실패'}")
        if result["write_success"]:
            print("[검증 성공] 제목 입력과 게시글 URL 전환을 확인했습니다.")
        else:
            print("[검증 실패] 로그의 제목 입력/URL 미전환 메시지를 확인하세요.")
        input("\n브라우저와 로그를 확인한 뒤 Enter를 누르면 종료합니다...")
    except KeyboardInterrupt:
        print("\n사용자가 검증을 중지했습니다.")
    except Exception as exc:
        print(f"\n[검증 실패] 예기치 않은 오류: {exc}")
    finally:
        if context:
            context.close()
        if pw:
            pw.stop()


if __name__ == "__main__":
    main()
