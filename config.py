"""
공통 설정

카페 목적지는 실행 환경의 환경변수로 설정합니다.
"""
import os
from modules.user_manager import get_or_create_config

# ──────────────────────────────────────────────
# 카페 설정 (미설정 시 카페 작업 건너뜀)
# ──────────────────────────────────────────────
CAFE_ID = int(os.environ.get("HAPPYBIN_CAFE_ID", "0"))
CAFE_URL = os.environ.get("HAPPYBIN_CAFE_URL", "").strip().rstrip("/")
CAFE_WRITE_URL = (
    f"https://cafe.naver.com/ca-fe/cafes/{CAFE_ID}/articles/write?boardType=L"
    if CAFE_ID > 0 and CAFE_URL else ""
)

# ──────────────────────────────────────────────
# 타이밍 설정
# ──────────────────────────────────────────────
TIMEOUT = 30000
WAIT_AFTER_PUBLISH = 2000

# ──────────────────────────────────────────────
# 사용자 설정
# ──────────────────────────────────────────────
_user_config = None


def get_user_config(username: str = None) -> dict:
    """사용자 설정 가져오기 (캐시)"""
    global _user_config
    if _user_config is None:
        _user_config = get_or_create_config(username)
    return _user_config
