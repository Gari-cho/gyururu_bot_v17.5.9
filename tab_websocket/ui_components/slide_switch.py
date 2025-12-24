# -*- coding: utf-8 -*-
"""
slide_switch.py - v17.2
- ttk.Checkbutton ベースのシンプルなスイッチ
- auto_off_seconds を指定すると、自動で OFF に戻すフェイルセーフ付き
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
from typing import Callable, Optional

class SlideSwitch(ttk.Frame):
    """
    on_toggle: Callable[[bool], None] で現在状態(True/False)が渡る
    auto_off_seconds: int | None (接続失敗時に自動OFFしたい時に使う)
    """
    def __init__(
        self,
        parent,
        text: str = "接続",
        initial: bool = False,
        on_toggle: Optional[Callable[[bool], None]] = None,
        auto_off_seconds: int | None = None,
    ):
        super().__init__(parent)
        self._on_toggle = on_toggle
        self._auto_off_seconds = auto_off_seconds
        self._auto_off_guard = None

        ttk.Label(self, text=text).pack(side=tk.LEFT)
        self.var = tk.BooleanVar(value=initial)
        self.btn = ttk.Checkbutton(
            self, text="", variable=self.var, command=self._toggle
        )
        self.btn.pack(side=tk.LEFT, padx=(6, 0))

    def _toggle(self):
        val = bool(self.var.get())
        if self._on_toggle:
            try:
                self._on_toggle(val)
            except Exception:
                pass

        # ON にした時だけ自動OFF監視
        if val and self._auto_off_seconds:
            self._schedule_auto_off(self._auto_off_seconds)

    def set(self, flag: bool):
        self.var.set(bool(flag))

    def _schedule_auto_off(self, seconds: int):
        # 既存があれば放置（最初のトグルのみ）
        if self._auto_off_guard:
            return

        def _guard():
            time.sleep(seconds)
            # まだONならOFFに戻す
            try:
                if bool(self.var.get()):
                    self.var.set(False)
                    if self._on_toggle:
                        self._on_toggle(False)
            finally:
                self._auto_off_guard = None

        self._auto_off_guard = threading.Thread(target=_guard, daemon=True)
        self._auto_off_guard.start()
