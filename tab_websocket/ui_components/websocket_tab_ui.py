# -*- coding: utf-8 -*-
"""
websocket_tab_ui.py - v17.2
- 見た目だけ組む「UI合成」層
- MessageBus が無くても落ちない
- app.py（タブ本体）から流用可能
"""

import tkinter as tk
from tkinter import ttk
from .base_ui import create_base_frame
from .log_panel import LogPanel
from .slide_switch import SlideSwitch
from .analysis_panel import create_analysis_panel

def create_websocket_tab_ui(parent, message_bus=None):
    """
    親フレーム(parent)の中に、
    - ヘッダ
    - 接続スイッチ + 簡易ステータス
    - ログパネル
    - ステータスバー
    で構成した UI を組み立てて返す。
    return: (root_frame, api_dict)
      api_dict = {
        "append_log": callable(str),
        "set_status": callable(str),
        "set_connected": callable(bool),
      }
    """
    root, header, body, status_var = create_base_frame(parent, title="📡 WebSocket（UI Components）")

    # 行レイアウト：上段（スイッチ＋分析） / 下段（ログ）
    top = ttk.Frame(body); top.pack(fill=tk.X, padx=0, pady=(0,6))
    bottom = ttk.Frame(body); bottom.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0,0))

    # 接続トグル
    def _on_switch(flag: bool):
        # Bus があれば旧イベント名で発火（互換）
        if not message_bus:
            return
        if flag:
            message_bus.publish("WEBSOCKET_CONNECT", {"url": "ws://127.0.0.1:11180/sub"}, sender="ui_components")
        else:
            message_bus.publish("WEBSOCKET_DISCONNECT", {}, sender="ui_components")

    switch = SlideSwitch(top, text="🛰 OneComme 接続", initial=False, on_toggle=_on_switch, auto_off_seconds=5)
    switch.pack(side=tk.LEFT)

    # 簡易ステータス
    analysis_frame, _apply_analysis = create_analysis_panel(top, message_bus=message_bus)
    analysis_frame.pack(side=tk.LEFT, padx=(12,0))

    # ログ
    log = LogPanel(bottom, height=12)
    log.pack(fill=tk.BOTH, expand=True)

    # Bus購読でUI反映
    if message_bus:
        try:
            def _on_status(data, sender=None):
                if isinstance(data, dict) and "connected" in data:
                    connected = bool(data["connected"])
                    switch.set(connected)
                    _apply_analysis({"connected": connected})
            message_bus.subscribe("WS_STATUS", _on_status)
        except Exception:
            pass

   
