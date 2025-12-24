# -*- coding: utf-8 -*-
"""
base_ui.py - v17.2
- WebSocketタブで使い回す基本フレーム作成ヘルパ
- 依存最小・安全フォールバック
"""

import tkinter as tk
from tkinter import ttk

def create_base_frame(parent, title: str = "📡 WebSocket", subtitle: str | None = None):
    """
    共通のタブ骨格を作成して返す（header, body, statusバー の3構成）
    return: (root_frame, header_frame, body_frame, status_var)
    """
    root = ttk.Frame(parent)
    root.pack(fill=tk.BOTH, expand=True)

    # Header
    header = ttk.Frame(root)
    header.pack(fill=tk.X, padx=10, pady=(10, 6))
    ttk.Label(header, text=title, font=("Yu Gothic UI", 12, "bold")).pack(side=tk.LEFT)
    if subtitle:
        ttk.Label(header, text=subtitle).pack(side=tk.LEFT, padx=(8, 0))

    # Body
    body = ttk.Frame(root)
    body.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

    # Status
    status_frame = ttk.Frame(root)
    status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
    status_var = tk.StringVar(value="⏳ 準備中…")
    ttk.Label(status_frame, textvariable=status_var).pack(side=tk.LEFT)

    return root, header, body, status_var
