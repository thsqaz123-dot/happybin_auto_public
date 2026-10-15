import ctypes


def safe_goto(page, url, **kwargs):
    try:
        page.bring_to_front()
    except Exception:
        pass
    try:
        return page.goto(url, **kwargs)
    except Exception:
        page.wait_for_timeout(2000)
        try:
            return page.goto(url, **kwargs)
        except Exception:
            return None


def get_screen_size() -> tuple:
    """논리적 화면 크기 반환 (DPI 스케일링 반영)"""
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w, h


def position_cmd_left():
    """CMD/터미널 창을 화면 왼쪽에 배치 (화면 45%)"""
    user32 = ctypes.windll.user32
    w, h = get_screen_size()
    cmd_w = int(w * 0.45)
    cmd_h = int(h * 0.9)
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        user32.SetWindowPos(hwnd, 0, 0, 0, cmd_w, cmd_h, 0x0004 | 0x0040)
