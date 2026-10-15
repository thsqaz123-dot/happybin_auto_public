"""
사용자 설정 관리 모듈

각 사용자별 데이터 디렉토리를 관리합니다.
설정 없이 Windows 사용자 이름으로 자동 생성됩니다.
"""
import os
import json
import getpass
import shutil

from modules.paths import get_app_data_dir

USER_DATA_ROOT = get_app_data_dir()


def get_user_dir(username: str = None) -> str:
    """사용자 데이터 디렉토리 경로 반환"""
    if username is None:
        username = getpass.getuser()
    return os.path.join(USER_DATA_ROOT, username)


def get_config_path(username: str = None) -> str:
    """사용자 설정 파일 경로 반환"""
    return os.path.join(get_user_dir(username), "user_config.json")


def get_browser_dir(username: str = None) -> str:
    """브라우저 프로필 디렉토리 경로 반환"""
    return os.path.join(get_user_dir(username), "browser")


def clear_browser_data(username: str = None) -> None:
    """명시적인 로그인 초기화 시 사용자 브라우저 프로필도 제거한다."""
    browser_dir = get_browser_dir(username)
    if os.path.exists(browser_dir):
        shutil.rmtree(browser_dir)
        print(f"[세션] 브라우저 프로필 삭제: {browser_dir}")


def get_session_path(username: str = None) -> str:
    """세션 파일 경로 반환"""
    return os.path.join(get_user_dir(username), "session.json")


def load_config(username: str = None) -> dict:
    """사용자 설정 로드. 없으면 None 반환"""
    config_path = get_config_path(username)
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_config(config: dict, username: str = None) -> None:
    """사용자 설정 저장"""
    user_dir = get_user_dir(username)
    os.makedirs(user_dir, exist_ok=True)
    config_path = get_config_path(username)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_or_create_config(username: str = None) -> dict:
    """설정 로드 또는 자동 생성"""
    config = load_config(username)
    if config is None:
        if username is None:
            username = getpass.getuser()
        config = {"user_name": username}
        save_config(config, username)
        print(f"[설정] 사용자 디렉토리 생성: {get_user_dir(username)}")
    return config


def list_users() -> list:
    """등록된 사용자 목록 반환"""
    if not os.path.exists(USER_DATA_ROOT):
        return []
    users = []
    for name in os.listdir(USER_DATA_ROOT):
        config_path = os.path.join(USER_DATA_ROOT, name, "user_config.json")
        if os.path.exists(config_path):
            users.append(name)
    return users
