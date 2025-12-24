# -*- coding: utf-8 -*-
"""
ui_components - v17.2
小さくて安全なUIユーティリティ群。最低依存で単独動作可能。
公開API:
- create_websocket_tab_ui (websocket_tab_ui.create_websocket_tab_ui)
- LogPanel, SlideSwitch, create_base_frame, create_analysis_panel
"""

from .base_ui import create_base_frame
from .log_panel import LogPanel
from .slide_switch import SlideSwitch
from .analysis_panel import create_analysis_panel
from .websocket_tab_ui import create_websocket_tab_ui

__all__ = [
    "create_base_frame",
    "LogPanel",
    "SlideSwitch",
    "create_analysis_panel",
    "create_websocket_tab_ui",
]
