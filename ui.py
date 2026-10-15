"""콩콩줍줍 Windows UI."""
from __future__ import annotations

import getpass
import queue
import threading
import tkinter as tk
from contextlib import redirect_stderr, redirect_stdout
from tkinter import messagebox, ttk

from automation import run_automation
from modules.session_manager import clear_session
from modules.user_manager import clear_browser_data


BG = "#f5f8f6"
SURFACE = "#ffffff"
TEXT = "#17201b"
MUTED = "#748078"
GREEN = "#08a557"
GREEN_DARK = "#08743d"
GREEN_SOFT = "#eaf8f0"
AMBER_SOFT = "#fff6e4"
AMBER_TEXT = "#805c13"
BORDER = "#dce7e0"
RED = "#b83b31"


class _QueueStream:
    def __init__(self, events: queue.Queue) -> None:
        self.events = events

    def write(self, text: str) -> int:
        if text and not text.isspace():
            self.events.put(("log", text.rstrip()))
        return len(text)

    def flush(self) -> None:
        pass


class HappyBeanApp(tk.Tk):
    STEP_ORDER = ("로그인", "블로그", "카페", "배너", "해피빈")
    STEP_TITLES = {
        "로그인": "로그인 상태 확인",
        "블로그": "블로그 글쓰기 및 콩배너",
        "카페": "카페 글쓰기 및 콩배너",
        "배너": "메인 페이지 배너 스캔",
        "해피빈": "해피빈 콩 수집",
    }
    PROGRESS = {"login": ("로그인", 8), "blog": ("블로그", 25), "cafe": ("카페", 45),
                "banners": ("배너", 68), "happybean": ("해피빈", 84), "complete": ("", 100)}

    def __init__(self) -> None:
        super().__init__()
        self.title("콩콩줍줍")
        # The side-by-side cards need this width; keeping it fixed prevents
        # Windows DPI/resolution changes from squeezing the status text.
        width = min(560, max(553, int(self.winfo_screenwidth() * 0.40)))
        height = min(760, max(680, self.winfo_screenheight() - 80))
        self.geometry(f"{width}x{height}+24+24")
        self.minsize(553, 680)
        self.resizable(False, False)
        self.configure(bg=BG)
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.username = getpass.getuser()
        self.status = tk.StringVar(value="준비됨 — 실행하면 로그인 상태를 확인합니다.")
        self.bean_detail = tk.StringVar(value="아직 확인된 콩 획득 내역이 없습니다")
        self.bean_total = tk.StringVar(value="+0콩")
        self.step_states: dict[str, tk.StringVar] = {}
        self.step_icons: dict[str, tk.Label] = {}
        self._configure_style()
        self._build()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("HB.Horizontal.TProgressbar", troughcolor="#cbe9d6", background=GREEN,
                        bordercolor="#cbe9d6", lightcolor=GREEN, darkcolor=GREEN, thickness=7)

    @staticmethod
    def _label(parent, text: str | tk.StringVar, **kwargs) -> tk.Label:
        defaults = {"bg": parent.cget("bg"), "fg": TEXT, "font": ("맑은 고딕", 10)}
        defaults.update(kwargs)
        if isinstance(text, tk.Variable):
            return tk.Label(parent, textvariable=text, **defaults)
        return tk.Label(parent, text=text, **defaults)

    def _build(self) -> None:
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=SURFACE, padx=20, pady=10)
        header.pack(fill="x")
        mark = tk.Label(header, text="✦", bg=GREEN, fg="white", font=("맑은 고딕", 18, "bold"),
                        width=2, height=1)
        mark.pack(side="left")
        brand = tk.Frame(header, bg=SURFACE)
        brand.pack(side="left", padx=12)
        self._label(brand, "콩콩줍줍", bg=SURFACE, font=("맑은 고딕", 18, "bold")).pack(anchor="w")
        self._label(brand, f"해피빈 자동 수집기 · {self.username} · 로그인 유지됨", bg=SURFACE,
                    fg=MUTED, font=("맑은 고딕", 8)).pack(anchor="w", pady=(2, 0))
        live = tk.Frame(header, bg=SURFACE)
        live.pack(side="right")
        self.live_dot = tk.Label(live, text="●", bg=SURFACE, fg=MUTED, font=("맑은 고딕", 10))
        self.live_dot.pack(side="left")
        self.live_text = self._label(live, "준비", bg=SURFACE, fg=MUTED, font=("맑은 고딕", 9, "bold"))
        self.live_text.pack(side="left", padx=(3, 0))

        body = tk.Frame(outer, bg=BG, padx=16, pady=8)
        body.pack(fill="both", expand=True)

        self._label(body, "현재 작업", fg=MUTED, font=("맑은 고딕", 8, "bold")).pack(anchor="w", padx=4)
        self.stage = tk.Frame(body, bg=GREEN_SOFT, highlightbackground="#cdecd9", highlightthickness=1,
                              padx=13, pady=8)
        self.stage.pack(fill="x", pady=(6, 8))
        icon = tk.Label(self.stage, text="●", bg=GREEN, fg="white", font=("맑은 고딕", 15), width=2)
        icon.grid(row=0, column=0, rowspan=2, padx=(0, 11))
        self.stage_title = self._label(self.stage, "실행을 시작할 준비가 되었습니다", bg=GREEN_SOFT,
                                       font=("맑은 고딕", 11, "bold"))
        self.stage_title.grid(row=0, column=1, sticky="w")
        self.stage_detail = self._label(self.stage, self.status, bg=GREEN_SOFT, fg=GREEN_DARK,
                                        font=("맑은 고딕", 8))
        self.stage_detail.grid(row=1, column=1, sticky="w", pady=(3, 0))
        self.stage.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(self.stage, style="HB.Horizontal.TProgressbar", mode="determinate",
                                        maximum=100, value=0)
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x")
        actions.columnconfigure(0, weight=7)
        actions.columnconfigure(1, weight=3)
        self.run_button = tk.Button(actions, text="자동 수집 시작", command=self._start, bg=GREEN, fg="white",
                                    activebackground=GREEN_DARK, activeforeground="white", relief="flat",
                                    font=("맑은 고딕", 10, "bold"), pady=10, cursor="hand2")
        self.run_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.cancel_button = tk.Button(actions, text="■  중지", command=self._cancel, state="disabled", bg=BG,
                                       fg=RED, activebackground="#fae9e7", activeforeground=RED,
                                       highlightbackground="#edc6c1", highlightthickness=1, relief="flat",
                                       font=("맑은 고딕", 9, "bold"), pady=10, cursor="hand2")
        self.cancel_button.grid(row=0, column=1, sticky="ew")

        info_row = tk.Frame(body, bg=BG)
        info_row.pack(fill="x", pady=(8, 8))
        info_row.columnconfigure(0, weight=1)
        info_row.columnconfigure(1, weight=1)

        bean = tk.Frame(info_row, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=11, pady=7)
        bean.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tk.Label(bean, text="♥", bg="#fff4dc", fg="#d7890b", font=("맑은 고딕", 13, "bold"), width=2).pack(anchor="w")
        self._label(bean, "이번 실행 콩 획득", bg=SURFACE, font=("맑은 고딕", 9, "bold")).pack(anchor="w", pady=(6, 0))
        self._label(bean, self.bean_total, bg=SURFACE, fg=GREEN_DARK, font=("맑은 고딕", 16, "bold")).pack(anchor="w", pady=(1, 0))
        self._label(bean, self.bean_detail, bg=SURFACE, fg=MUTED, font=("맑은 고딕", 7), wraplength=175,
                    justify="left").pack(anchor="w", pady=(2, 0))

        notice = tk.Frame(info_row, bg=AMBER_SOFT, highlightbackground="#f0dba5", highlightthickness=1,
                          padx=11, pady=7)
        notice.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._label(notice, "!", bg=AMBER_SOFT, fg=AMBER_TEXT, font=("맑은 고딕", 13, "bold")).pack(anchor="w")
        copy = tk.Frame(notice, bg=AMBER_SOFT)
        copy.pack(fill="both", expand=True, pady=(5, 0))
        self._label(copy, "작업 중에는 브라우저를 건드리지 마세요", bg=AMBER_SOFT, fg=AMBER_TEXT,
                    font=("맑은 고딕", 9, "bold")).pack(anchor="w")
        self._label(copy, "탭·로그인 창·콩배너를 직접 클릭하거나 닫지 마세요.", bg=AMBER_SOFT,
                    fg=AMBER_TEXT, font=("맑은 고딕", 7), justify="left", wraplength=175).pack(anchor="w", pady=(3, 0))

        self._label(body, "진행 단계", fg=MUTED, font=("맑은 고딕", 8, "bold")).pack(anchor="w", padx=4, pady=(8, 5))
        steps = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        steps.pack(fill="x")
        for index, key in enumerate(self.STEP_ORDER):
            if index:
                tk.Frame(steps, bg="#edf1ee", height=1).pack(fill="x")
            row = tk.Frame(steps, bg=SURFACE, padx=13, pady=4)
            row.pack(fill="x")
            icon = self._label(row, "○", bg=SURFACE, fg=MUTED, font=("맑은 고딕", 11))
            icon.pack(side="left", padx=(0, 10))
            self.step_icons[key] = icon
            self._label(row, self.STEP_TITLES[key], bg=SURFACE, font=("맑은 고딕", 9, "bold")).pack(side="left")
            state = tk.StringVar(value="대기")
            self.step_states[key] = state
            self._label(row, state, bg=SURFACE, fg=MUTED, font=("맑은 고딕", 8)).pack(side="right")

        self._label(body, "진행 로그", fg=MUTED, font=("맑은 고딕", 8, "bold")).pack(anchor="w", padx=4, pady=(8, 4))
        log_box = tk.Frame(body, bg="#1d2822", padx=2, pady=2)
        log_box.pack(fill="both", expand=True)
        self.log = tk.Text(log_box, height=3, state="disabled", wrap="word", bg="#1d2822", fg="#d9ebe1",
                           insertbackground="white", relief="flat", font=("Consolas", 8), padx=10, pady=8)
        scroll = ttk.Scrollbar(log_box, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        footer = tk.Frame(body, bg=BG)
        footer.pack(fill="x", pady=(5, 0))
        self._label(footer, "로그인 정보는 이 PC에만 안전하게 저장됩니다", fg=MUTED,
                    font=("맑은 고딕", 8)).pack(side="left")
        self.reset_button = tk.Button(footer, text="로그인 초기화", command=self._reset_login, bg=BG, fg=MUTED,
                                      activebackground=BG, activeforeground=TEXT, relief="flat", borderwidth=0,
                                      font=("맑은 고딕", 8, "underline"), cursor="hand2")
        self.reset_button.pack(side="right")

    def _start(self) -> None:
        self.cancel_event.clear()
        self.run_button.configure(state="disabled", text="자동 수집 진행 중")
        self.reset_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.live_dot.configure(fg="#16b364")
        self.live_text.configure(text="실행 중", fg=GREEN_DARK)
        self.progress.configure(value=3)
        self.bean_detail.set("작업 결과를 확인하는 중입니다")
        self.bean_total.set("+0콩")
        self._set_step_state("로그인", "진행 중")
        for key in self.STEP_ORDER[1:]:
            self._set_step_state(key, "대기")
        self._append_log("\n실행 시작")
        self.worker = threading.Thread(target=self._run_worker, args=(self.username,), daemon=True)
        self.worker.start()

    def _run_worker(self, username: str) -> None:
        stream = _QueueStream(self.events)

        def progress(state: str, message: str) -> None:
            self.events.put(("progress", state, message))

        with redirect_stdout(stream), redirect_stderr(stream):
            results = run_automation(username, progress, self.cancel_event)
        self.events.put(("finished", results))

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status.set("중지 요청됨 — 현재 작업을 정리한 뒤 안전하게 종료합니다.")
        self.stage_title.configure(text="중지 요청됨")
        self.cancel_button.configure(state="disabled", text="중지 요청됨")

    def _reset_login(self) -> None:
        if not messagebox.askyesno("로그인 초기화", "저장된 로그인 캐시를 삭제하고 다음 실행에서 다시 로그인할까요?"):
            return
        try:
            clear_session(self.username)
            clear_browser_data(self.username)
            self.status.set("로그인 캐시를 초기화했습니다.")
            self._append_log("로그인 캐시를 초기화했습니다.")
        except OSError as exc:
            messagebox.showerror("초기화 실패", str(exc))

    def _set_step_state(self, key: str, value: str) -> None:
        self.step_states[key].set(value)
        icon = self.step_icons[key]
        if value == "진행 중":
            icon.configure(text="●", fg="#d7890b")
        elif value == "대기":
            icon.configure(text="○", fg=MUTED)
        else:
            icon.configure(text="✓", fg=GREEN)

    def _show_progress(self, state: str, message: str) -> None:
        self.status.set(message.replace("\n", " "))
        if state not in self.PROGRESS:
            return
        current, amount = self.PROGRESS[state]
        self.progress.configure(value=amount)
        if current:
            self.stage_title.configure(text=self.STEP_TITLES[current])
            current_index = self.STEP_ORDER.index(current)
            for index, key in enumerate(self.STEP_ORDER):
                if index < current_index:
                    self._set_step_state(key, "완료")
                elif index == current_index:
                    self._set_step_state(key, "진행 중")
                    break

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "log":
                    self._append_log(event[1])
                elif event[0] == "progress":
                    self._show_progress(event[1], event[2])
                elif event[0] == "finished":
                    self._finish(event[1])
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + ("" if text.endswith("\n") else "\n"))
        self.log.see("end")
        self.log.configure(state="disabled")

    def _finish(self, results: dict) -> None:
        self.run_button.configure(state="normal", text="자동 수집 다시 시작")
        self.reset_button.configure(state="normal")
        self.cancel_button.configure(state="disabled", text="■  중지")
        self.live_dot.configure(fg=MUTED)
        self.live_text.configure(text="완료", fg=MUTED)
        bean_items = [
            name for name, ok in results.items()
            if ok and (
                "콩" in name
                or name.startswith("배너_")
                or name in {"오늘의Pick", "팝업_콩받기"}
            )
        ]
        self.bean_total.set(f"+{len(bean_items)}콩")
        if bean_items:
            self.bean_detail.set(" · ".join(bean_items[:2]) + " 적립 확인")
        elif self.cancel_event.is_set():
            self.bean_detail.set("사용자 요청으로 작업을 중지했습니다")
        else:
            self.bean_detail.set("확인된 콩 획득 내역이 없습니다")
        if self.cancel_event.is_set():
            self.stage_title.configure(text="실행이 중지되었습니다")
            self.status.set("중지됨")
        else:
            success = sum(1 for value in results.values() if value)
            self.stage_title.configure(text="자동 수집이 완료되었습니다")
            self.status.set(f"완료 — {len(results)}개 중 {success}개 성공")
            self.progress.configure(value=100)
            if results.get("블로그 콩배너"):
                self._set_step_state("블로그", "+1콩 획득")
            elif self.step_states["블로그"].get() != "대기":
                self._set_step_state("블로그", "완료")
            if results.get("카페 콩배너"):
                self._set_step_state("카페", "+1콩 획득")
            elif self.step_states["카페"].get() != "대기":
                self._set_step_state("카페", "완료")
            banner_count = sum(1 for name, ok in results.items() if ok and name.startswith("콩배너_"))
            if banner_count:
                self._set_step_state("배너", f"+{banner_count}콩 획득")
            happybean_count = sum(
                1 for name, ok in results.items()
                if ok and (name.startswith("배너_") or name in {"오늘의Pick", "팝업_콩받기"})
            )
            if happybean_count:
                self._set_step_state("해피빈", f"+{happybean_count}콩 획득")
            for key in self.STEP_ORDER:
                if self.step_states[key].get() == "진행 중":
                    self._set_step_state(key, "완료")

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("실행 중", "실행을 중지하고 창을 닫을까요?"):
                return
            self.cancel_event.set()
        self.destroy()


def launch_ui() -> None:
    HappyBeanApp().mainloop()
