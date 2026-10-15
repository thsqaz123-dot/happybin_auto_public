"""실행 파일과 사용자 데이터의 경로를 분리한다."""
import sys
import os
import shutil


def get_base_dir() -> str:
    """
    실행 환경에 따른 기준 디렉토리 반환.

    - PyInstaller frozen exe: exe가 있는 폴더
    - 개발 환경: 이 파일의 상위 폴더 (happybean_auto/)
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_data_dir() -> str:
    """Windows 사용자별 영구 데이터 위치를 반환한다.

    실행 파일 위치와 무관하게 로그인 프로필을 보존한다. 기존 버전이
    실행 폴더에 만든 ``user_data``는 최초 한 번만 자동 이전한다.
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")

    target = os.path.join(local_app_data, "HappyBeanAuto")
    legacy = os.path.join(get_base_dir(), "user_data")

    if not os.path.exists(target) and os.path.isdir(legacy):
        try:
            shutil.copytree(legacy, target)
            print(f"[데이터] 기존 로그인 캐시를 이전했습니다: {target}")
        except OSError as exc:
            # 이전 실패는 첫 실행을 막지 않는다. 이후 새 캐시를 만든다.
            print(f"[데이터] 기존 캐시 이전 실패: {exc}")

    os.makedirs(target, exist_ok=True)
    return target
