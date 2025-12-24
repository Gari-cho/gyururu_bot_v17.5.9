# -*- coding: utf-8 -*-
"""
log_panel.py - v17.2
黒背景テキストログ。append() で追記、auto_scroll on。
"""

import tkinter as tk
from tkinter import ttk

class LogPanel(ttk.Frame):
    def __init__(self, parent, height: int = 10):
        super().__init__(parent)
        self._build(height)

    def _build(self, height: int):
        # スクロールバー
        yscroll = ttk.Scrollbar(self, orient="vertical")
        xscroll = ttk.Scrollbar(self, orient="horizontal")

        self.text = tk.Text(
            self,
            height=height,
            bg="black",
            fg="white",
            insertbackground="white",
            wrap="none",
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        self.text.config(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.config(command=self.text.yview)
        xscroll.config(command=self.text.xview)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.append("=== WebSocket Log ===")

    def append(self, line: str):
        try:
            self.text.insert("end", line + "\n")
            self.text.see("end")
        except Exception:
            pass

    def clear(self):
        try:
            self.text.delete("1.0", "end")
        except Exception:
            pass
