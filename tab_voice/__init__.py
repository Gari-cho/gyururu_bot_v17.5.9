# -*- coding: utf-8 -*-
"""
🎤 tab_voice パッケージ - v17.3統合版
========================================
📦 メタデータ:
  - パッケージ名: tab_voice
  - バージョン: v17.3.0
  - 作成日: 2025-11-03
  - 更新日: 2025-11-03
  - 作成者: BillyTrunks & Claude
  - ライセンス: MIT

🎯 目的:
  音声制御タブの統一エクスポートポイント
  main_v_17_3.py からの読み込みを保証

🔗 エクスポート:
  - create_voice_tab: タブ作成関数（推奨）
  - VoiceControlTab: タブクラス
  - VoiceTab: 後方互換性エイリアス
  - create_tab: 後方互換性エイリアス

📋 使用方法:
  ```python
  from tab_voice import create_voice_tab, VoiceControlTab
  
  # 推奨方法
  tab = create_voice_tab(parent, message_bus, config_manager)
  
  # クラス直接使用
  tab = VoiceControlTab(parent, message_bus=bus, config_manager=cfg)
  ```

🔧 フォールバック:
  app.py の読み込みに失敗した場合、最小限のフォールバック実装を提供
"""

__version__ = "17.3.0"
__author__ = "BillyTrunks & Claude"

# ===== メインインポート（app.pyから） =====
try:
    from .app import (
        create_voice_tab,
        VoiceControlTab,
        VoiceTab,
        create_tab,
    )
    
    # 読み込み成功ログ
    import logging
    logger = logging.getLogger(__name__)
    logger.info("✅ tab_voice: 正常にロードされました（v17.3統合版）")
    
    # エクスポート成功フラグ
    _EXPORT_SUCCESS = True

except ImportError as e:
    # ===== フォールバック実装 =====
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ tab_voice.app読み込み失敗 - フォールバック使用: {e}")
    
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        tk = None
        ttk = None
        logger.error("❌ tkinterが利用できません")

    class VoiceControlTab(ttk.Frame if ttk else object):
        """
        音声制御タブ フォールバック実装
        
        最小限の表示のみを行い、機能は提供しない
        """
        def __init__(self, master=None, message_bus=None, config_manager=None, app_instance=None, **_):
            if ttk:
                super().__init__(master)
                if not self.winfo_manager():
                    self.pack(fill="both", expand=True)
                
                # フォールバック警告表示
                warning_frame = ttk.Frame(self, padding=20)
                warning_frame.pack(fill="both", expand=True)
                
                ttk.Label(
                    warning_frame,
                    text="⚠️ 音声制御タブ (フォールバック)",
                    font=("Yu Gothic UI", 16, "bold"),
                    foreground="orange"
                ).pack(pady=10)
                
                ttk.Label(
                    warning_frame,
                    text="app.pyの読み込みに失敗しました。\n音声制御機能は利用できません。",
                    font=("Yu Gothic UI", 12),
                    justify=tk.CENTER
                ).pack(pady=10)
                
                ttk.Label(
                    warning_frame,
                    text="🔧 トラブルシューティング:\n"
                         "1. tab_voice/app.py が存在するか確認\n"
                         "2. shared/ モジュールが正しく配置されているか確認\n"
                         "3. 依存関係がインストールされているか確認",
                    font=("Yu Gothic UI", 10),
                    justify=tk.LEFT,
                    foreground="gray"
                ).pack(pady=10)
            
            logger.warning("⚠️ VoiceControlTab: フォールバック実装を使用")

        def cleanup(self):
            """クリーンアップ（フォールバック）"""
            pass

    def create_voice_tab(parent, message_bus=None, config_manager=None, app_instance=None, **kwargs):
        """
        音声制御タブ作成関数（フォールバック）
        
        Args:
            parent: 親ウィジェット
            message_bus: MessageBusインスタンス（無視される）
            config_manager: ConfigManagerインスタンス（無視される）
            app_instance: アプリインスタンス（無視される）
            **kwargs: その他のキーワード引数（無視される）
        
        Returns:
            VoiceControlTab: フォールバック実装のタブ
        """
        logger.warning("⚠️ create_voice_tab: フォールバック実装を使用")
        return VoiceControlTab(master=parent, message_bus=message_bus, 
                              config_manager=config_manager, app_instance=app_instance, **kwargs)

    # 後方互換性エイリアス
    VoiceTab = VoiceControlTab
    create_tab = create_voice_tab
    
    # フォールバック使用フラグ
    _EXPORT_SUCCESS = False

except Exception as e:
    # 予期しないエラー
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"❌ tab_voice: 予期しないエラー: {e}")
    
    # 最小限のダミー実装
    class VoiceControlTab:
        def __init__(self, *args, **kwargs):
            raise ImportError(f"tab_voice: 読み込みに失敗しました: {e}")
        def cleanup(self):
            pass
    
    def create_voice_tab(*args, **kwargs):
        raise ImportError(f"tab_voice: 読み込みに失敗しました: {e}")
    
    VoiceTab = VoiceControlTab
    create_tab = create_voice_tab
    
    _EXPORT_SUCCESS = False


# ===== パッケージ情報 =====
PACKAGE_INFO = {
    "name": "tab_voice",
    "version": __version__,
    "description": "ぎゅるるボット音声制御タブ（v17.3統合版）",
    "author": __author__,
    "license": "MIT",
    "export_success": _EXPORT_SUCCESS,
    "features": [
        "音声テスト実行",
        "エンジン切替（VOICEVOX / 棒読みちゃん）",
        "話者選択",
        "音量制御",
        "キュー管理",
        "ステータス監視",
    ] if _EXPORT_SUCCESS else ["フォールバック表示のみ"],
    "dependencies": {
        "shared.voice_manager_singleton": "推奨",
        "shared.message_bus": "推奨",
        "shared.unified_config_manager": "推奨",
        "shared.event_types": "推奨",
    }
}


# ===== エクスポート一覧 =====
__all__ = [
    # 主要エクスポート
    "create_voice_tab",
    "VoiceControlTab",
    
    # 後方互換性
    "VoiceTab",
    "create_tab",
    
    # メタデータ
    "__version__",
    "__author__",
    "PACKAGE_INFO",
]


# ===== 起動時チェック =====
if __name__ == "__main__":
    print("=" * 70)
    print("🎤 tab_voice パッケージ情報")
    print("=" * 70)
    
    import json
    print("\n📦 パッケージ詳細:")
    print(json.dumps(PACKAGE_INFO, ensure_ascii=False, indent=2))
    
    print("\n✅ エクスポート一覧:")
    for name in __all__:
        status = "✅" if name in globals() else "❌"
        print(f"  {status} {name}")
    
    print("\n🔧 統合状態:")
    if _EXPORT_SUCCESS:
        print("  ✅ 正常にロードされました（完全機能版）")
    else:
        print("  ⚠️ フォールバック実装を使用しています")
    
    print("\n💡 使用方法:")
    print("  from tab_voice import create_voice_tab")
    print("  tab = create_voice_tab(parent, message_bus, config_manager)")
    
    print("\n" + "=" * 70)