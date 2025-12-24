# -*- coding: utf-8 -*-
"""
🎨 tab_chat パッケージ - v17.2.1対応版
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【ファイル情報】
作成日: 2025-11-03
作成者: Claude (Assistant)
バージョン: v17.2.1
親ファイル: main_v17_3.py

【目的】
tab_chatパッケージのエクスポート定義
- create_chat_tab: ファクトリ関数（推奨）
- ChatTab: クラスエイリアス（後方互換）
- ChatApp: クラスエイリアス（後方互換）

【依存関係】
- ./app.py: 実装本体
- shared.message_bus: MessageBus
- shared.unified_config_manager: UnifiedConfigManager

【ルールブック準拠】
✅ snake_case ファイル名
✅ 日本語コメント記載
✅ MessageBus経由のイベント通信
✅ v17.2.1命名規則準拠
"""

import logging

logger = logging.getLogger(__name__)

# ===== 実装のインポート =====
try:
    from .app import (
        create_chat_tab,
        create_integrated_ai_chat_tab,
        ChatAppCompleteFixed,
        ChatApp,
        ChatTabApp,
    )
    
    # エイリアス定義（後方互換性）
    ChatTab = ChatAppCompleteFixed
    
    logger.info("✅ tab_chat: 正常にインポート完了")
    
except ImportError as e:
    logger.warning(f"⚠️ tab_chat.app インポート失敗: {e}")
    
    # フォールバックの最小スタブ
    import tkinter as tk
    from tkinter import ttk
    
    class ChatTab(ttk.Frame):
        """最小フォールバックスタブ"""
        def __init__(self, master=None, message_bus=None, config_manager=None, app_instance=None, **kwargs):
            super().__init__(master)
            if not self.winfo_manager():
                self.pack(fill="both", expand=True)
            
            label = ttk.Label(
                self,
                text="💬 チャットタブ（フォールバック）\n\napp.pyの読み込みに失敗しました。",
                font=("Arial", 12)
            )
            label.pack(padx=20, pady=20, expand=True)
            
            logger.error("❌ ChatTabフォールバックモードで起動")
        
        def cleanup(self):
            """クリーンアップ（空実装）"""
            pass
    
    def create_chat_tab(parent, message_bus=None, config_manager=None, app_instance=None):
        """ファクトリ関数（フォールバック）"""
        logger.warning("⚠️ create_chat_tab: フォールバックモードで実行")
        return ChatTab(
            master=parent,
            message_bus=message_bus,
            config_manager=config_manager,
            app_instance=app_instance
        )
    
    # エイリアス
    ChatApp = ChatTab
    ChatTabApp = ChatTab
    create_integrated_ai_chat_tab = create_chat_tab

except Exception as e:
    logger.error(f"❌ tab_chat 予期しないエラー: {e}")
    raise


# ===== エクスポート定義 =====
__all__ = [
    "create_chat_tab",
    "create_integrated_ai_chat_tab",
    "ChatTab",
    "ChatApp",
    "ChatTabApp",
    "ChatAppCompleteFixed",
]

# ===== モジュール情報 =====
__version__ = "17.2.1"
__author__ = "Claude (Assistant)"
__description__ = "AIチャットタブパッケージ - MessageBus統合版"