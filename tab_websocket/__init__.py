# -*- coding: utf-8 -*-
"""
tab_websocket パッケージ初期化
v17 系最新形式：create_websocket_tab を公開し、互換性を確保
"""

from __future__ import annotations

__all__ = [
    "create_websocket_tab",
    "__version__",
]

__version__ = "v17.2-websocket-tab-compat"

# create_websocket_tab をエクスポート
try:
    # 通常ルート（パッケージ内）
    from .app import create_websocket_tab
except Exception:
    # 直下配置フォールバック
    from app import create_websocket_tab  # type: ignore
