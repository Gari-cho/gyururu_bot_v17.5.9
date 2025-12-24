#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧩 tab_ai_unified.__init__.py — AI統合タブ（個性設定＋技術設定）初期化モジュール  v17.2

このモジュールは「AIキャラ設定（個性）」と「AI技術設定（技術）」の
両タブを統合的に扱うためのエントリポイントを提供します。

主な役割：
- 各サブモジュール(app, config_handler, ui_core, view_model) の安全読み込み
- MessageBus, UnifiedConfigManager, Logger の依存注入
- `create_tab(parent, message_bus, config_manager)` で統合タブを生成

📁 配置: C:/gyururu_bot_claude/gyururu_bot_v17/tab_ai_unified/__init__.py
"""

from __future__ import annotations
import importlib
import logging
from typing import Any, Optional

# =============================
#  ロガー設定
# =============================
try:
    from shared.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except Exception:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.warning("⚠️ GUIロガーが見つからないため、標準ロガーを使用中")

# =============================
#  共通依存 (MessageBus / ConfigManager)
# =============================
BUS = None
CFG = None

try:
    from shared.message_bus import get_message_bus
    BUS = get_message_bus()
    logger.info("📨 MessageBus 利用可能")
except Exception as e:
    logger.warning(f"⚠️ MessageBus 未使用: {e}")

try:
    from shared.unified_config_manager import get_config_manager
    CFG = get_config_manager()
    logger.info("⚙️ UnifiedConfigManager 利用可能")
except Exception as e:
    logger.warning(f"⚠️ UnifiedConfigManager 未使用: {e}")


# =============================
#  公開関数
# =============================
def create_tab(parent, message_bus: Optional[Any] = None, config_manager: Optional[Any] = None):
    """
    統合AIタブの作成。
    - parent: Tkinter Frame (Notebook のタブなど)
    - message_bus: 任意指定。なければ共有BUSを使用。
    - config_manager: 任意指定。なければ共有CFGを使用。
    """
    try:
        module = importlib.import_module("tab_ai_unified.app")
        if hasattr(module, "create_ai_tab"):
            logger.info("🧠 create_ai_tab() を使用して統合AIタブを生成")
            return module.create_ai_tab(
                parent,
                message_bus=message_bus or BUS,
                config_manager=config_manager or CFG
            )
        elif hasattr(module, "AIUnifiedTab"):
            logger.info("🧠 AIUnifiedTab クラスを使用して統合AIタブを生成")
            cls = getattr(module, "AIUnifiedTab")
            return cls(parent, message_bus or BUS, config_manager or CFG)
        else:
            raise ImportError("app.py に create_ai_tab() または AIUnifiedTab が定義されていません。")

    except Exception as e:
        logger.error(f"❌ AI統合タブの生成に失敗: {e}")
        import tkinter as tk
        import tkinter.ttk as ttk
        frame = ttk.Frame(parent)
        lbl = ttk.Label(frame, text=f"AI統合タブの初期化に失敗しました。\n{e}", foreground="red")
        lbl.pack(padx=10, pady=10)
        return frame


# =============================
#  互換ユーティリティ
# =============================
def get_bus() -> Optional[Any]:
    """MessageBus を取得（存在しない場合は None）"""
    return BUS

def get_config() -> Optional[Any]:
    """UnifiedConfigManager を取得（存在しない場合は None）"""
    return CFG


# =============================
#  モジュール情報
# =============================
__all__ = [
    "create_tab",
    "get_bus",
    "get_config",
]

logger.info("✅ tab_ai_unified 初期化モジュール読み込み完了")
