"""
콩배너 확인 전용 모드 (실제 획득 없음)

동선:
  로그인 → 블로그 글쓰기+배너확인 → 카페 글쓰기+배너확인 → 메인페이지 스캔

실행: python check_banners.py
"""
import getpass
from modules.login import create_browser_context, do_login
from modules.bean_banner import scan_all_bean_banners
from modules.blog import do_blog_write
from modules.cafe import do_cafe_write


def main():
    username = getpass.getuser()
    print(f"사용자: {username}")
    print("콩배너 확인 모드 (획득 없음)\n")

    pw = None
    context = None
    try:
        pw, context = create_browser_context(username)

        if not do_login(context, username):
            print("로그인 실패. 종료합니다.")
            return

        page = context.pages[0] if context.pages else context.new_page()

        # ─────────────────────────────────────────
        # Phase 1: 블로그 글쓰기 + 발행 후 콩배너 확인
        # ─────────────────────────────────────────
        print("\n" + "=" * 50)
        print("  [Phase 1] 블로그 글쓰기 + 콩배너 확인")
        print("=" * 50)
        blog_result = do_blog_write(page, actually_click_banner=False)
        print(f"\n  블로그 결과: write={blog_result['write_success']}, "
              f"banner_found={blog_result['banner_found']}, "
              f"banner_clicked={blog_result['banner_clicked']}")

        # ─────────────────────────────────────────
        # Phase 2: 카페 글쓰기 + 등록 후 콩배너 확인
        # ─────────────────────────────────────────
        print("\n" + "=" * 50)
        print("  [Phase 2] 카페 글쓰기 + 콩배너 확인")
        print("=" * 50)
        cafe_result = do_cafe_write(page, actually_click_banner=False)
        print(f"\n  카페 결과: write={cafe_result['write_success']}, "
              f"banner_found={cafe_result['banner_found']}, "
              f"banner_clicked={cafe_result['banner_clicked']}")

        # ─────────────────────────────────────────
        # Phase 3: 메인 페이지 배너 스캔
        # ─────────────────────────────────────────
        print("\n" + "=" * 50)
        print("  [Phase 3] 메인 페이지 콩배너 스캔")
        print("=" * 50)
        banner_results = scan_all_bean_banners(page, actually_click=False)

        # ─────────────────────────────────────────
        # 결과 요약
        # ─────────────────────────────────────────
        print("\n" + "=" * 50)
        print("  최종 결과 요약")
        print("=" * 50)
        print(f"  블로그 글쓰기: {'성공' if blog_result['write_success'] else '실패'}")
        print(f"  블로그 콩배너: {'발견됨' if blog_result['banner_found'] else '없음'}"
              f" {'(클릭됨)' if blog_result['banner_clicked'] else ''}")
        print(f"  카페 글쓰기: {'성공' if cafe_result['write_success'] else '실패'}")
        print(f"  카페 콩배너: {'발견됨' if cafe_result['banner_found'] else '없음'}"
              f" {'(클릭됨)' if cafe_result['banner_clicked'] else ''}")
        print()
        for r in banner_results:
            icon = "O" if r["exists"] else "X"
            extra = ""
            if r["exists"]:
                extra = f" (상품='{r['product_name']}', 확장={'Y' if r['expanded'] else 'N'})"
            print(f"  [{icon}] {r['page_name']}{extra}")

    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()
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
        print("\n완료")


if __name__ == "__main__":
    main()
