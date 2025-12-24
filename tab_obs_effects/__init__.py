# -*- coding: utf-8 -*-
"""
tab_obs_effects package (v17.3統合版)
========================================
OBS演出効果タブのパッケージエクスポート

v17.3対応:
- メインファイル (main_v_17_3.py) から読み込み可能
- 統合モジュール対応 (config_handler, effects_handler, file_backend)
- スタンドアロン実行対応
- フォールバック機能内蔵

エクスポート:
- create_obs_tab(parent, message_bus=None, config_manager=None)
- OBSEffectsTab (= OBSEffectsTabUI)
"""

try:
    from .app import (
        create_obs_tab,
        create_obs_effects_tab,
        create_tab,
        OBSEffectsTabUI,
        OBSEffectsTab,
        OBSEffectsApp
    )
    
    # 正常にインポートできた場合
    __all__ = [
        "create_obs_tab",
        "create_obs_effects_tab", 
        "create_tab",
        "OBSEffectsTab",
        "OBSEffectsTabUI",
        "OBSEffectsApp"
    ]
    
except Exception as e:
    # フォールバック: tkinterが無い環境でもインポートエラーを回避
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ tab_obs_effects.app のインポート失敗（フォールバック起動）: {e}")
    
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        tk = None
        ttk = None

    class OBSEffectsTab(ttk.Frame if ttk else object):
        """フォールバッククラス"""
        def __init__(self, master=None, **kwargs):
            if ttk:
                super().__init__(master)
                if not self.winfo_manager():
                    self.pack(fill="both", expand=True)
                ttk.Label(self, text="📺 OBS Effects tab (fallback mode)").pack(padx=16, pady=16)
                ttk.Label(self, text="統合モジュールの読み込みに失敗しました", 
                         foreground="red").pack(padx=16, pady=8)

        def cleanup(self):
            pass

    OBSEffectsTabUI = OBSEffectsTab
    OBSEffectsApp = OBSEffectsTab

    def create_obs_tab(parent, **kwargs):
        return OBSEffectsTab(master=parent, **kwargs)
    
    def create_obs_effects_tab(parent, **kwargs):
        return OBSEffectsTab(master=parent, **kwargs)
    
    def create_tab(parent, **kwargs):
        return OBSEffectsTab(master=parent, **kwargs)

    __all__ = ["create_obs_tab", "create_obs_effects_tab", "create_tab", "OBSEffectsTab"]