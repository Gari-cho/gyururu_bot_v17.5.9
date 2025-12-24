# -*- coding: utf-8 -*-
"""
analysis_panel.py - v17.2
最低限の統計・状態表示（接続状態 / 受信件数）
MessageBus を渡されれば自動購読して数値更新する。
"""

import tkinter as tk
from tkinter import ttk

class _Counter:
    def __init__(self):
        self.comments = 0
        self.connected = False

def create_analysis_panel(parent, message_bus=None):
    """
    return: (frame, update_fn)
      - update_fn(dict) を呼ぶと手動更新も可能
    """
    counter = _Counter()
    frm = ttk.LabelFrame(parent, text="簡易ステータス")
    frm.pack(fill=tk.X, padx=0, pady=6)

    v_conn = tk.StringVar(value="未接続")
    v_cnt = tk.StringVar(value="0")

    row = ttk.Frame(frm); row.pack(fill=tk.X, padx=8, pady=4)
    ttk.Label(row, text="接続状態:").pack(side=tk.LEFT)
    ttk.Label(row, textvariable=v_conn).pack(side=tk.LEFT, padx=(6,0))

    row2 = ttk.Frame(frm); row2.pack(fill=tk.X, padx=8, pady=4)
    ttk.Label(row2, text="受信コメント数:").pack(side=tk.LEFT)
    ttk.Label(row2, textvariable=v_cnt).pack(side=tk.LEFT, padx=(6,0))

    def _apply():
        v_conn.set("✅ 接続中" if counter.connected else "⛔ 未接続")
        v_cnt.set(str(counter.comments))

    def _update(payload: dict):
        if "connected" in payload:
            counter.connected = bool(payload["connected"])
        if "comments" in payload:
            counter.comments = int(payload["comments"])
        _apply()

    # Bus購読（任意）
    if message_bus:
        try:
            def _on_status(data, sender=None):
                if isinstance(data, dict) and "connected" in data:
                    counter.connected = bool(data["connected"])
                    _apply()
            def _on_comment(data, sender=None):
                counter.comments += 1
                _apply()
            message_bus.subscribe("WS_STATUS", _on_status)
            message_bus.subscribe("ONECOMME_COMMENT", _on_comment)
        except Exception:
            pass

    _apply()
    return frm, _update
