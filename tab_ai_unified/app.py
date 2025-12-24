#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIキャラ設定タブ - v17対応完全版（整形済み・スタンドアロン起動可）
✨ ハイブリッド版：Document 3 + 感情変数完全実装

タブ名: AIキャラ設定
構成: [基本設定] [応答パターン] [行動設定] [技術設定]
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any

print("=" * 60)
print("🚀 AIキャラ設定タブ - 起動開始")
print("=" * 60)

# === 共有モジュールのインポート + Events統合 ===
MESSAGE_BUS_AVAILABLE = False
try:
    from shared.message_bus import MessageBus
    from shared.unified_config_manager import get_config_manager, UnifiedConfigManager
    from shared.event_types import Events
    MESSAGE_BUS_AVAILABLE = True
    print("✅ 共有モジュール読み込み成功")
except ImportError as e:
    MESSAGE_BUS_AVAILABLE = False
    print(f"⚠️ 共有モジュール利用不可: {e}")
    class Events:  # フォールバック
        AI_PERSONALITY_CHANGED = "ai_personality_changed"
        CONFIG_UPDATE = "config_update"
        CONFIG_SAVED = "config_saved"
        TAB_READY = "tab_ready"
    print("✅ フォールバックモード起動")


class AICharacterTab:
    """AIキャラ設定タブ（v17対応・4タブ構成）"""

    # =========================
    # 1) 初期化
    # =========================
    def __init__(self, parent_frame, message_bus=None, config_manager=None, app_instance=None):
        """初期化"""
        print("🔧 AICharacterTab.__init__ 開始")
        
        self.parent_frame = parent_frame
        self.app_instance = app_instance
        self.message_bus = message_bus
        self.logger = None
        
        # ✅ Events初期化
        try:
            from shared.event_types import Events as SharedEvents
            self.Events = SharedEvents
        except Exception:
            self.Events = Events
        
        # ✅ AIとチャットタブと同じパターンに統一
        if config_manager:
            self.config_manager = config_manager
            print("✅ 注入されたConfigManagerを使用")
        else:
            print("⚠️ ConfigManager未注入 → 新規作成")
            try:
                from shared.unified_config_manager import UnifiedConfigManager
                self.config_manager = UnifiedConfigManager()
                print("✅ UnifiedConfigManager インスタンス化成功")
            except Exception as e:
                print(f"❌ UnifiedConfigManager インスタンス化失敗: {e}")
                import traceback
                traceback.print_exc()
                self.config_manager = None
        
        print(f"   MessageBus: {'有効' if self.message_bus else '無効'}")
        print(f"   ConfigManager: {'有効' if self.config_manager else '無効'}")

        # Phase 8: 複数AIキャラ管理
        self.ai_characters: Dict[str, Dict] = {}  # キャラ名 -> character_data
        self.selected_character_name = "ぎゅるる"  # 現在選択中のキャラ名

        # Phase 10: アーカイブ表示制御
        self.show_archived_var = tk.BooleanVar(value=False)  # アーカイブも表示するか

        self.__init_default_data()
        self.config_file = "configs/ai_character_config.json"
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        self.ui_elements: Dict[str, Any] = {}
        self.setup_ui()
        
        # ✅ 修正1: MessageBusセットアップを先に行う（イベント購読を先に設定）
        self.setup_message_bus()

        # ✅ 修正2: 初回読み込み（v17.3.1: 1回のみ実行）
        self.load_character_config()

        # ❌ v17.3.1: 遅延再読み込みは廃止（二重読み込み防止のため）
        # if hasattr(self.parent_frame, 'after'):
        #     self.parent_frame.after(200, self._delayed_load_config)

        try:
            if self.message_bus:
                self.message_bus.publish(Events.TAB_READY, {'tab': 'ai_character', 'status': 'ready'}, sender='tab_ai_unified')
        except Exception:
            pass

        # ❌ v17.3.1: REQUEST_SAVE_AI_CONFIG は廃止（購読者なしのデッドイベント）
        # if not getattr(self, "_requested_startup_save", False):
        #     if self._bus_publish("REQUEST_SAVE_AI_CONFIG", {"reason": "startup_sync"}):
        #         self._requested_startup_save = True
        #         print("🛰️ REQUEST_SAVE_AI_CONFIG を起動時に1回だけ発行（startup_sync）")
        #     else:
        #         print("⚠️ Bus未接続のため REQUEST_SAVE_AI_CONFIG を発行できませんでした")

        # AIステータス再取得用のクールダウン管理（AI_STATUS_REQUEST多重発行防止）
        self._last_status_request_ts = 0.0
        self._status_request_cooldown = 0.5  # 秒

        # AI_STATUS_UPDATE ログの重複抑制用（状態変化時のみログ出力）
        self._last_ai_status_for_log = None

        print("✅ AICharacterTab.__init__ 完了")

    def _delayed_load_config(self):
        """
        ❌ v17.3.1: このメソッドは廃止されました（二重読み込み防止のため）
        初期化時に load_character_config() を1回だけ実行します。
        """
        print("⚠️ _delayed_load_config は v17.3.1 で廃止されました（二重読み込み防止）")
        # try:
        #     print("=" * 60)
        #     print("🔄 遅延ConfigManager読み込み開始...")
        #     self.load_character_config()
        #     self._write_details("設定を再読み込みしました")
        #     print("✅ 遅延ConfigManager読み込み完了")
        #     print("=" * 60)
        # except Exception as e:
        #     print(f"⚠️ 遅延読み込みエラー: {e}")
        #     import traceback
        #     traceback.print_exc()

    def _create_scrollable(self, parent):
        """縦スクロール可能な領域を作る（幅自動フィット、初期表示ズレ対策、ホイール対応）"""
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        vbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        inner = ttk.Frame(canvas)
        # キャンバスに内部フレームを貼る
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        # 1) 内部フレームのサイズが変わったらスクロール領域を更新
        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_inner_configure)

        # 2) キャンバスの幅に合わせて内部フレームの幅をフィット
        def _on_canvas_configure(event):
            canvas.itemconfigure(window_id, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        # 3) 初期表示で“スクロールしないと見えない”問題を潰す
        #    レイアウト確定後にスクロール領域を計算＆先頭へ移動
        def _ensure_top_visible():
            try:
                canvas.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.yview_moveto(0.0)
            except Exception:
                pass
        # after_idle で呼ぶと初期化タイミング差でのチラつきを抑えられる
        canvas.after_idle(_ensure_top_visible)

        # 4) マウスホイール対応（Windows / macOS / Linux）
        def _bind_mousewheel(widget):
            # Windows / macOS
            widget.bind_all("<MouseWheel>", _on_mousewheel_windows_macos, add="+")
            # Linux (X11)
            widget.bind_all("<Button-4>", _on_mousewheel_linux_up, add="+")
            widget.bind_all("<Button-5>", _on_mousewheel_linux_down, add="+")
        def _unbind_mousewheel(widget):
            widget.unbind_all("<MouseWheel>")
            widget.unbind_all("<Button-4>")
            widget.unbind_all("<Button-5>")

        def _on_mousewheel_windows_macos(event):
            # Windows: event.delta は ±120 の倍数 / macOS: ±1や±120
            delta = event.delta
            if delta == 0:
                return
            step = -1 if delta > 0 else 1
            canvas.yview_scroll(step, "units")

        def _on_mousewheel_linux_up(event):
            canvas.yview_scroll(-1, "units")
        def _on_mousewheel_linux_down(event):
            canvas.yview_scroll(1, "units")

        # ホバー中だけホイールを奪う
        def _enter(_):
            _bind_mousewheel(canvas)
        def _leave(_):
            _unbind_mousewheel(canvas)

        inner.bind("<Enter>", _enter)
        inner.bind("<Leave>", _leave)

        # 呼び出し元は、この戻り値（inner）に対して子ウィジェットを配置する
        return inner

    # =========================
    # 2) UI構築
    # =========================
    def setup_ui(self):
        """UIの構築（アクションバーを常時表示・レイアウト安定化）"""
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # grid で行/列を管理： 0=ステータス, 1=ノートブック(伸縮), 2=アクションバー(固定)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # 接続ステータスバー（上部）
        status_holder = ttk.Frame(main_frame)
        status_holder.grid(row=0, column=0, sticky="ew")
        self._build_status_bar(status_holder)

        # ノートブック（中央, 伸縮）
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(8, 8))

        # 1. 基本設定
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="基本設定")
        self.setup_basic_settings_tab(basic_frame)

        # 2. 応答パターン
        patterns_frame = ttk.Frame(notebook)
        notebook.add(patterns_frame, text="応答パターン")
        self.setup_response_patterns_tab(patterns_frame)

        # 3. 行動設定
        behavior_frame = ttk.Frame(notebook)
        notebook.add(behavior_frame, text="行動設定")
        self.setup_behavior_settings_tab(behavior_frame)

        # 4. 技術設定
        technical_frame = ttk.Frame(notebook)
        notebook.add(technical_frame, text="技術設定")
        self.setup_technical_settings_tab(technical_frame)

        # アクションバー（下部・固定表示）
        action_holder = ttk.Frame(main_frame)
        action_holder.grid(row=2, column=0, sticky="ew")
        self._build_action_bar(action_holder)

    def _build_action_bar(self, parent):
        """下部の固定アクションバー（テストボタン廃止済み）"""
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(4, 2))

        # 左側: 操作用ボタン
        left = ttk.Frame(bar)
        left.pack(side=tk.LEFT)

        ttk.Button(
            left,
            text="設定保存",
            command=self.save_personality_config
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            left,
            text="設定読み込み",
            command=self.load_character_config
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            left,
            text="設定リセット",
            command=self.reset_character_config
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Phase 8: AIキャラ追加ボタン
        ttk.Button(
            left,
            text="AIキャラ追加",
            command=self._on_add_character
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Phase 10: アーカイブ・削除ボタン
        ttk.Button(
            left,
            text="AIキャラをアーカイブ",
            command=self._on_archive_character
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            left,
            text="AIキャラを完全削除",
            command=self._on_delete_character
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Phase 10: アーカイブも表示チェックボックス
        ttk.Checkbutton(
            left,
            text="アーカイブも表示",
            variable=self.show_archived_var,
            command=self._on_show_archived_changed
        ).pack(side=tk.LEFT, padx=(12, 0))

        # ★ テストボタンは削除済み（競合防止）
        # 右側ステータスラベル
        right = ttk.Frame(bar)
        right.pack(side=tk.RIGHT, fill="x", expand=True)

        self.status_label = ttk.Label(right, text="設定準備完了", anchor="e")
        self.status_label.pack(fill="x")


    # =========================
    # 3) ステータスバー
    # =========================
    def _build_status_bar(self, parent):
        """接続ステータスバーの構築"""
        grp = ttk.LabelFrame(parent, text="AI接続ステータス")
        grp.pack(fill="x", pady=(0, 10))

        grid = ttk.Frame(grp)
        grid.pack(fill="x", padx=8, pady=8)

        self.var_provider = tk.StringVar(value="-")
        self.var_model = tk.StringVar(value="-")
        self.var_key = tk.StringVar(value="-")
        self.var_connected = tk.StringVar(value="未接続")

        def row(r, lbl, var):
            ttk.Label(grid, text=lbl, width=16, anchor="e").grid(
                row=r, column=0, sticky="e", padx=4, pady=2
            )
            value_label = tk.Label(grid, textvariable=var, anchor="w")
            value_label.grid(row=r, column=1, sticky="w", padx=4, pady=2)
            return value_label

        row(0, "プロバイダ", self.var_provider)
        row(1, "モデル", self.var_model)
        row(2, "APIキー", self.var_key)
        self._connection_label = row(3, "接続状態", self.var_connected)

        ttk.Button(grp, text="ステータス再取得",
                   command=self.refresh_status).pack(side="left", padx=8, pady=(0, 8))

        # ステータスログ欄：最低8行表示、ウィンドウ拡大時に伸縮可能
        self.details_box = tk.Text(grp, height=8, wrap="word")
        self.details_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.details_box.insert("1.0", "接続情報はここに表示されます。\n")
        self.details_box.configure(state="disabled")
        
    def _set_ai_connected_label(self, connected: bool, provider: str = "-", model: str = "-"):
        """
        AIの接続状態を表示するラベルを更新する（色付き・プロバイダ/モデル表示）
        - connected が True なら「接続中（provider / model）」（緑色）
        - connected が False なら「未接続」（赤色）
        """
        try:
            if connected:
                label_text = f"接続中（{provider} / {model}）"
                self.var_connected.set(label_text)
                if hasattr(self, "_connection_label"):
                    self._connection_label.configure(foreground="#008800")
            else:
                label_text = "未接続"
                self.var_connected.set(label_text)
                if hasattr(self, "_connection_label"):
                    self._connection_label.configure(foreground="#aa0000")
        except Exception as e:
            self._write_details(f"⚠️ ラベル更新エラー: {e}")


    def _write_details(self, text: str):
        """詳細ログに書き込み"""
        self.details_box.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.details_box.insert("end", f"[{timestamp}] {text}\n")
        self.details_box.see("end")
        self.details_box.configure(state="disabled")

    def refresh_status(self):
        """ステータス情報の更新"""
        self._write_details("ステータス更新を開始しました。")
        try:
            prov = model = "-"
            masked = "(未設定)"

            # ① ConfigManager から読む（従来動作）
            if self.config_manager and hasattr(self.config_manager, "get"):
                p = self.config_manager.get('ai.provider', None)
                m = self.config_manager.get('ai.model', None)
                k = self.config_manager.get('ai.api_key', None)
                if p: prov = p
                if m: model = m
                if k and isinstance(k, str) and len(k) >= 8:
                    masked = k[:4] + "***" + k[-3:]
                elif k:
                    masked = "(設定あり)"
                
                self._write_details(f"ConfigManagerから取得: provider={prov}, model={model}")

            # ② まだ空なら AIコネクタから取得（新フォールバック）
            if (prov == "-" or model == "-") and hasattr(self, "app_instance") and self.app_instance:
                ai = getattr(self.app_instance, "ai_connector", None)
                if ai:
                    self._write_details("AIコネクタから情報取得を試行...")
                    try:
                        if hasattr(ai, "current_provider"):
                            cp = ai.current_provider
                            prov = cp() if callable(cp) else cp
                            self._write_details(f"current_provider: {prov}")
                        elif hasattr(ai, "current"):
                            curr = ai.current
                            prov = curr() if callable(curr) else curr
                            self._write_details(f"current: {prov}")
                        
                        if hasattr(ai, "config") and isinstance(ai.config, dict):
                            model = ai.config.get("model", model)
                            key = ai.config.get("api_key", None)
                            self._write_details(f"configから: model={model}")
                            
                            if key and isinstance(key, str) and len(key) >= 8:
                                masked = key[:4] + "***" + key[-3:]
                            elif key:
                                masked = "(設定あり)"
                    except Exception as e:
                        self._write_details(f"AIコネクタ情報取得エラー: {e}")

            self.var_provider.set(prov or "-")
            self.var_model.set(model or "-")
            self.var_key.set(masked)
            self._write_details(f"最終結果: {prov or '-'} / {model or '-'}")
        except Exception as e:
            self._write_details(f"設定取得エラー: {e}")

        # ステータス再取得ボタンで手動リフレッシュ時は AI_STATUS_REQUEST を発行
        self._request_ai_status()

    def _request_ai_status(self, source="ai_tab"):
        """AI_STATUS_REQUEST を発行してAIの接続状態を取得"""
        try:
            bus = self.message_bus
            evt = self.Events if hasattr(self, "Events") else None

            topic = getattr(evt, "AI_STATUS_REQUEST", None) if evt else None
            topic = topic or "AI_STATUS_REQUEST"

            if bus and hasattr(bus, "publish"):
                bus.publish(topic, {"source": source}, sender="tab_ai_unified")
                self._write_details(f"AI_STATUS_REQUEST を発行しました（source: {source}）")
        except Exception as e:
            print(f"⚠️ AIステータスリクエスト送信エラー: {e}")
            self._write_details(f"⚠️ AIステータスリクエスト送信エラー: {e}")

    # =========================
    # 4) 基本設定タブ
    # =========================
    def setup_basic_settings_tab(self, parent):
        """基本設定タブ（AI基本情報 + キーワード設定）"""
        # スクロール対応のコンテナ（中身をこの main_frame に追加する）
        main_frame = self._create_scrollable(parent)

        # === AI基本情報 ===
        info_frame = ttk.LabelFrame(main_frame, text="AI基本情報", padding=10)
        info_frame.pack(fill=tk.X, expand=True, padx=10, pady=10)

        # 名前（Phase 8: Comboboxに変更）
        row = ttk.Frame(info_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="名前", width=10, anchor="e").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['name_var'] = tk.StringVar(value=self.selected_character_name)
        self.ui_elements['name'] = ttk.Combobox(
            row,
            textvariable=self.ui_elements['name_var'],
            values=list(self.ai_characters.keys()) if self.ai_characters else ["ぎゅるる"],
            state="readonly",
            width=24
        )
        self.ui_elements['name'].pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ui_elements['name'].bind("<<ComboboxSelected>>", self._on_character_selected)

        # 年齢
        row = ttk.Frame(info_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="年齢", width=10, anchor="e").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['age'] = ttk.Entry(row)
        self.ui_elements['age'].pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 性格（複数行）
        row = ttk.Frame(info_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="性格", width=10, anchor="ne").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['personality'] = tk.Text(row, height=4, wrap="word")
        self.ui_elements['personality'].pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 背景（複数行）
        row = ttk.Frame(info_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="背景", width=10, anchor="ne").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['background'] = tk.Text(row, height=4, wrap="word")
        self.ui_elements['background'].pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 口調（複数行）
        row = ttk.Frame(info_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="話し方/口調", width=10, anchor="ne").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['speaking_style'] = tk.Text(row, height=3, wrap="word")
        self.ui_elements['speaking_style'].pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 語尾（Phase 9: 新規追加）
        row = ttk.Frame(info_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="語尾", width=10, anchor="e").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['ending'] = ttk.Entry(row)
        self.ui_elements['ending'].pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(row, text="（例: ～だよ、～なのだ）").pack(side=tk.LEFT, padx=8)

        # === キーワード設定 ===
        kw_frame = ttk.LabelFrame(main_frame, text="キーワード設定", padding=10)
        kw_frame.pack(fill=tk.X, expand=True, padx=10, pady=(0, 10))

        # 反応トリガー（カンマ区切り）
        row = ttk.Frame(kw_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="反応トリガー", width=12, anchor="e").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['kw_triggers'] = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.ui_elements['kw_triggers'])\
            .pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(row, text="（例: ぎゅるる, AI, ボット）").pack(side=tk.LEFT, padx=8)

        # 除外ワード（カンマ区切り）
        row = ttk.Frame(kw_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="除外ワード", width=12, anchor="e").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['kw_excludes'] = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.ui_elements['kw_excludes'])\
            .pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(row, text="（例: NGワードA, NGワードB）").pack(side=tk.LEFT, padx=8)

        # ブラックリストユーザー（改行区切り）
        row = ttk.Frame(kw_frame)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="ブラックリスト", width=12, anchor="ne").pack(side=tk.LEFT, padx=(0, 8))
        self.ui_elements['kw_blacklist'] = tk.Text(row, height=3, wrap="word")
        self.ui_elements['kw_blacklist'].pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(row, text="（1行1ユーザー名）").pack(side=tk.LEFT, padx=8)

        # ※ 応答制御設定（応答モード・応答確率）はチャットタブに配置
        # ※ 応答タイミング設定 / 応答動作設定 は行動設定タブへ移動済み

    # =========================
    # 5) 変数展開・プレビュー ✨ 感情変数完全実装版
    # =========================
    def _expand_variables(self, text: str, context: dict = None) -> str:
        """テンプレート変数を展開（拡張版・感情/ムード対応）"""
        if context is None:
            context = {}

        import re, random
        from datetime import datetime

        botname = self.character_data.get('basic_info', {}).get('name', 'AIアシスタント')
        username = context.get('username', 'ユーザー')

        hour = datetime.now().hour
        time_greeting = "おはよう" if 5 <= hour < 11 else ("こんにちは" if 11 <= hour < 17 else "こんばんは")

        now = datetime.now()
        date_str = now.strftime("%Y年%m月%d日")
        day_names = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        day_str = day_names[now.weekday()]

        emotions = ['嬉しい', '楽しい', '悲しい', '驚き', '普通']
        moods = ['元気', '落ち着いてる', '眠い', 'ハイテンション']

        replacements = {
            '{username}': username,
            '{botname}': botname,
            '{time}': time_greeting,
            '{date}': date_str,
            '{day}': day_str,
            '{emotion}': random.choice(emotions),
            '{mood}': random.choice(moods),
        }

        result = text
        for k, v in replacements.items():
            result = result.replace(k, v)

        def replace_random(m):
            options = m.group(1).split('|')
            return random.choice(options) if options else ''

        result = re.sub(r'\{random:(.*?)\}', replace_random, result)
        result = result.replace('{count:today}', '1回目').replace('{count:total}', '1回目')
        return result

    def preview_pattern(self, category_key):
        """パターンのプレビュー表示（改善版）"""
        entry = self.ui_elements.get(f'{category_key}_entry')
        if not entry:
            return

        pattern = entry.get().strip()
        if not pattern:
            messagebox.showwarning("プレビュー", "パターンを入力してください")
            return

        expanded = self._expand_variables(pattern, {'username': 'テストユーザー'})

        messagebox.showinfo(
            "パターンプレビュー",
            f"📝 入力:\n{pattern}\n\n⬇️ 展開後 ⬇️\n\n{expanded}\n\n💡 変数が正しく置き換わっているか確認してください！"
        )

    # =========================
    # 6) 応答パターン
    # =========================
    def setup_response_patterns_tab(self, parent):
        """応答パターンタブのセットアップ"""
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        categories = [
            ("greeting", "挨拶"),
            ("thanks", "感謝"),
            ("goodbye", "別れ"),
            ("reaction_positive", "ポジティブ反応"),
            ("reaction_negative", "ネガティブ反応"),
        ]
        for key, name in categories:
            frame = ttk.Frame(nb)
            nb.add(frame, text=name)
            self.setup_pattern_category(frame, key, name)

    def setup_pattern_category(self, parent, category_key, category_name):
        """応答パターンカテゴリのセットアップ（変数システム対応）"""
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        list_frame = ttk.LabelFrame(main_frame, text=f"{category_name}パターン", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        listbox = tk.Listbox(list_container, height=8)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        self.ui_elements[f'{category_key}_listbox'] = listbox

        edit_frame = ttk.LabelFrame(main_frame, text="パターン編集", padding=10)
        edit_frame.pack(fill=tk.X)

        entry_frame = ttk.Frame(edit_frame)
        entry_frame.pack(fill=tk.X, pady=(0, 5))

        entry = ttk.Entry(entry_frame)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.ui_elements[f'{category_key}_entry'] = entry

        button_frame = ttk.Frame(entry_frame)
        button_frame.pack(side=tk.RIGHT)

        var_button = ttk.Button(button_frame, text="変数▼", width=8,
                               command=lambda: self._show_variable_menu(category_key, var_button))
        var_button.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="追加",
                  command=lambda: self.add_pattern(category_key)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="削除",
                  command=lambda: self.remove_pattern(category_key)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="編集",
                  command=lambda: self.edit_pattern(category_key)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="👁️プレビュー",
                  command=lambda: self.preview_pattern(category_key)).pack(side=tk.LEFT)

    # =========================
    # 7) 行動設定タブ
    # =========================
    def setup_behavior_settings_tab(self, parent):
        """行動設定タブ（スクロール対応・左寄せ・重複除去・枠を右端まで伸ばす）"""
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # スクロール可能な内部フレームを作る
        main_frame = self._create_scrollable(container)

        # 既存データ（あれば反映）
        p_base = (self.character_data.get('base_settings', {}) if hasattr(self, 'character_data') else {})
        p_behv = (self.character_data.get('behavior_settings', {}) if hasattr(self, 'character_data') else {})

        # === 応答タイミング設定（左寄せ / 枠は右端まで / Entryはw揃え）===
        timing = ttk.LabelFrame(main_frame, text="⏱️ 応答タイミング設定", padding=10)
        timing.pack(fill=tk.X, expand=False, padx=0, pady=(0, 10))

        for i in (0, 1):
            timing.grid_columnconfigure(i, weight=0)
        timing.grid_columnconfigure(2, weight=1)  # 右側に余白を持たせて左寄せに見せる

        self.ui_elements['limit_len'] = tk.IntVar(value=int(p_base.get('limit_len', 200)))
        self.ui_elements['delay_sec'] = tk.IntVar(value=int(p_base.get('delay_sec', 2)))
        self.ui_elements['cooldown_sec'] = tk.IntVar(value=int(p_base.get('cooldown_sec', 5)))

        ttk.Label(timing, text="応答長さ上限（文字）").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Spinbox(timing, from_=50, to=1000, textvariable=self.ui_elements['limit_len'], width=10)\
            .grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(timing, text="返答遅延（秒）").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Spinbox(timing, from_=0, to=10, textvariable=self.ui_elements['delay_sec'], width=10)\
            .grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(timing, text="連続応答間隔（秒）").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Spinbox(timing, from_=0, to=60, textvariable=self.ui_elements['cooldown_sec'], width=10)\
            .grid(row=2, column=1, sticky="w", padx=6, pady=4)

        # === 基本機能（会話記憶のチェック＋直下に制限）===
        options_frame = ttk.LabelFrame(main_frame, text="基本機能", padding=10)
        options_frame.pack(fill=tk.X, padx=0, pady=(0, 10))
        options_frame.grid_columnconfigure(0, weight=0)
        options_frame.grid_columnconfigure(1, weight=1)

        self.ui_elements['memory_retention'] = tk.BooleanVar(value=bool(p_behv.get('memory_retention', True)))
        ttk.Checkbutton(options_frame, text="会話記憶を保持",
                        variable=self.ui_elements['memory_retention'])\
            .grid(row=0, column=0, sticky="w", padx=6, pady=4)

        ttk.Label(options_frame, text="会話記憶制限").grid(row=1, column=0, sticky="w", padx=6, pady=(2, 4))
        self.ui_elements['conversation_memory_limit'] = tk.IntVar(
            value=int(p_behv.get('conversation_memory_limit', 100))
        )
        mem_row = ttk.Frame(options_frame)
        mem_row.grid(row=1, column=1, sticky="w", padx=6, pady=(2, 4))
        ttk.Spinbox(mem_row, from_=10, to=1000,
                    textvariable=self.ui_elements['conversation_memory_limit'],
                    width=10).pack(side=tk.LEFT)
        ttk.Label(mem_row, text="メッセージ").pack(side=tk.LEFT, padx=(6, 0))

        self.ui_elements['learning_enabled'] = tk.BooleanVar(value=bool(p_behv.get('learning_enabled', False)))
        ttk.Checkbutton(options_frame, text="学習機能を有効化",
                        variable=self.ui_elements['learning_enabled'])\
            .grid(row=2, column=0, sticky="w", padx=6, pady=4)

        # === 高度な機能 ===
        advanced_frame = ttk.LabelFrame(main_frame, text="高度な機能", padding=10)
        advanced_frame.pack(fill=tk.X, padx=0, pady=(0, 10))

        self.ui_elements['context_awareness'] = tk.BooleanVar(value=bool(p_behv.get('context_awareness', True)))
        ttk.Checkbutton(advanced_frame, text="コンテキスト認識",
                        variable=self.ui_elements['context_awareness']).pack(anchor="w", pady=2)

        self.ui_elements['mood_simulation'] = tk.BooleanVar(value=bool(p_behv.get('mood_simulation', False)))
        ttk.Checkbutton(advanced_frame, text="ムードシミュレーション",
                        variable=self.ui_elements['mood_simulation']).pack(anchor="w", pady=2)

        # === パラメータ調整（感情設定をここに統合 / 応答遅延は重複のため置かない）===
        params_frame = ttk.LabelFrame(main_frame, text="パラメータ調整", padding=10)
        params_frame.pack(fill=tk.X, padx=0, pady=(0, 10))

        var_row = ttk.Frame(params_frame)
        var_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(var_row, text="感情変化度:").pack(side=tk.LEFT)
        self.ui_elements['emotional_variance'] = tk.DoubleVar(value=float(p_behv.get('emotional_variance', 0.5)))
        ttk.Scale(var_row, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
                  variable=self.ui_elements['emotional_variance'], length=220,
                  command=self.update_emotion_label).pack(side=tk.LEFT, padx=(10, 10))
        self.ui_elements['emotion_label'] = ttk.Label(var_row, text=f"{int(self.ui_elements['emotional_variance'].get()*100)}%")
        self.ui_elements['emotion_label'].pack(side=tk.LEFT)

        drift_row = ttk.Frame(params_frame)
        drift_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(drift_row, text="個性ドリフト:").pack(side=tk.LEFT)
        self.ui_elements['personality_drift'] = tk.DoubleVar(value=float(p_behv.get('personality_drift', 0.1)))
        ttk.Scale(drift_row, from_=0.0, to=0.5, orient=tk.HORIZONTAL,
                  variable=self.ui_elements['personality_drift'], length=220,
                  command=self.update_drift_label).pack(side=tk.LEFT, padx=(10, 10))
        self.ui_elements['drift_label'] = ttk.Label(drift_row, text=f"{int(self.ui_elements['personality_drift'].get()*100)}%")
        self.ui_elements['drift_label'].pack(side=tk.LEFT)

    # =========================
    # 8) 技術設定タブ
    # =========================
    def setup_technical_settings_tab(self, parent):
        """技術設定タブのセットアップ（プロバイダ設定のみ・文字数は基本設定に統合）"""
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        provider_frame = ttk.LabelFrame(frm, text="プロバイダ設定", padding=10)
        provider_frame.pack(fill=tk.X, pady=(0, 10))

        prov_row = ttk.Frame(provider_frame)
        prov_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(prov_row, text="プロバイダ:", width=16, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
        self.ui_elements['provider_tech'] = tk.StringVar(value="gemini")
        ttk.Combobox(prov_row, textvariable=self.ui_elements['provider_tech'],
                     values=["gemini"], state="readonly", width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)

        key_row = ttk.Frame(provider_frame)
        key_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(key_row, text="APIキー:", width=16, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
        self.ui_elements['api_key_tech'] = tk.StringVar(value="")
        ttk.Entry(key_row, textvariable=self.ui_elements['api_key_tech'], show="*", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        model_row = ttk.Frame(provider_frame)
        model_row.pack(fill=tk.X)
        ttk.Label(model_row, text="モデル:", width=16, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
        gemini_models = [
            "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest", "gemini-1.5-flash-8b", "gemini-1.5-pro-002",
            "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"
        ]
        self.ui_elements['model_tech'] = tk.StringVar(value="gemini-2.5-flash")
        ttk.Combobox(model_row, textvariable=self.ui_elements['model_tech'],
                     values=gemini_models, state="readonly", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        test_row = ttk.Frame(frm)
        test_row.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(test_row, text="接続テスト", command=self._test_connection).pack(side=tk.LEFT)

        # Phase 3: フォールバック順序設定
        fallback_frame = ttk.LabelFrame(frm, text="フォールバック順序設定（Phase 3）", padding=10)
        fallback_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # 説明ラベル
        desc_label = ttk.Label(fallback_frame,
            text="AI応答の試行順序を設定します。上から順に試行され、失敗した場合は次のプロバイダにフォールバックします。",
            wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor="w", pady=(0, 10))

        # コンテナフレーム（左右分割）
        container = ttk.Frame(fallback_frame)
        container.pack(fill=tk.BOTH, expand=True)

        # 左側: 順序リスト
        list_frame = ttk.Frame(container)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(list_frame, text="試行順序（上から順に試行）:").pack(anchor="w", pady=(0, 5))

        # Listbox + Scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.fallback_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=6)
        self.fallback_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.fallback_listbox.yview)

        # 右側: 操作ボタン
        btn_frame = ttk.Frame(container)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Button(btn_frame, text="↑ 上へ", command=self._move_provider_up, width=12).pack(pady=2)
        ttk.Button(btn_frame, text="↓ 下へ", command=self._move_provider_down, width=12).pack(pady=2)
        ttk.Frame(btn_frame, height=10).pack()  # スペーサー
        ttk.Button(btn_frame, text="順序を保存", command=self._save_fallback_order, width=12).pack(pady=2)
        ttk.Button(btn_frame, text="リセット", command=self._reset_fallback_order, width=12).pack(pady=2)

        # 利用可能なプロバイダの説明
        available_label = ttk.Label(fallback_frame,
            text="利用可能なプロバイダ: gemini, local-echo, gpt4all（将来実装）",
            font=("", 9), foreground="gray")
        available_label.pack(anchor="w", pady=(10, 0))

        # 初期データ読み込み
        self._load_fallback_order()

        # （※最大文字数UIはここから削除。基本設定タブに統合済み）

    # =========================
    # X) 接続テスト（クラス直下・UI名に合わせて取得）
    # =========================
    def _test_connection(self):
        """AIプロバイダへの接続テスト（Gemini/フォールバック両対応, v17.3 導線仕様）"""
        try:
            # --- 1) UIの実フィールド名に合わせて取得 ---
            prov_var = self.ui_elements.get('provider_tech')
            model_var = self.ui_elements.get('model_tech')
            key_var   = self.ui_elements.get('api_key_tech')

            provider = (prov_var.get().strip().lower() if prov_var else "")
            model    = (model_var.get().strip() if model_var else "")
            api_key  = (key_var.get().strip() if key_var else "")

            # --- 2) Config の値で補完（空欄なら） ---
            if self.config_manager and hasattr(self.config_manager, "get"):
                get = self.config_manager.get
                if not provider:
                    provider = (get("ai.provider", "") or "").strip().lower()
                if not model:
                    model = (get("ai.model", "") or "").strip()
                if not api_key:
                    api_key = (get("ai.api_key", "") or "").strip()

            self._write_details(f"[AI接続テスト] provider='{provider}', model='{model}'")
            if not provider:
                self._write_details("⚠️ プロバイダが未選択です。")
                return

            # --- 3) MessageBus経由でテスト要求を送信 ---
            bus = getattr(self, "message_bus", None)
            if not (bus and hasattr(bus, "publish")):
                self._write_details("⚠️ MessageBus未接続のためテスト不可（スタンドアロン）")
                return

            # v17.3 導線: AI_TEST_REQUEST のみを Bus に投げる
            # （AI_STATUS_UPDATE は AIIntegrationManager 側が _send_status_update() で返す）
            payload = {
                "provider": provider,
                "model": model,
                "api_key": api_key or None,
                "source": "tab_ai_unified",
                "ts": datetime.now().timestamp(),
            }

            try:
                # メイン側の AIIntegrationManager がこれを受けてテストを実行
                bus.publish("AI_TEST_REQUEST", payload, sender="tab_ai_unified")
                self._write_details("📡 AI接続テスト要求を送信しました（Busルート）")
            except Exception as e:
                self._write_details(f"❌ 接続テスト処理中に例外: {e}")

        except Exception as e:
            self._write_details(f"❌ 接続テスト中に例外: {e}")

    # =========================
    # Phase 3: フォールバック順序管理メソッド
    # =========================
    def _load_fallback_order(self):
        """
        UnifiedConfigManager からフォールバック順序を読み込んで Listbox に表示する。

        設定キー:
        - ai.primary_provider: str (最初のプロバイダ)
        - ai.fallback_providers: list[str] (2番目以降のプロバイダ)

        順序: [primary] + fallback_providers
        """
        try:
            if not hasattr(self, 'fallback_listbox'):
                return

            # Listbox をクリア
            self.fallback_listbox.delete(0, tk.END)

            # ConfigManager から設定を取得
            if not (self.config_manager and hasattr(self.config_manager, "get")):
                # デフォルト順序
                default_order = ["gemini", "local-echo"]
                for p in default_order:
                    self.fallback_listbox.insert(tk.END, p)
                self._write_details("⚠️ ConfigManager未接続。デフォルト順序を使用します。")
                return

            # Phase 3 新設定を取得
            primary = self.config_manager.get("ai.primary_provider", None)
            fallbacks = self.config_manager.get("ai.fallback_providers", None)

            # 旧設定へのフォールバック
            if not primary:
                primary = self.config_manager.get("ai.provider_primary", None) or self.config_manager.get("ai.provider", None)
            if not fallbacks or not isinstance(fallbacks, list):
                old_fallback = self.config_manager.get("ai.provider_fallback", None)
                fallbacks = [old_fallback] if old_fallback else []

            # デフォルト値
            if not primary:
                primary = "gemini"
            if not fallbacks:
                fallbacks = ["local-echo"]

            # 順序を構築: [primary] + fallbacks
            order = [primary] + fallbacks

            # Listbox に追加
            for p in order:
                self.fallback_listbox.insert(tk.END, p)

            self._write_details(f"フォールバック順序を読み込みました: {order}")

        except Exception as e:
            self._write_details(f"❌ フォールバック順序の読み込みエラー: {e}")
            import traceback
            traceback.print_exc()

    def _save_fallback_order(self):
        """
        Listbox の順序を UnifiedConfigManager に保存する。

        保存先:
        - ai.primary_provider: Listbox の最初の要素
        - ai.fallback_providers: Listbox の2番目以降をリストとして保存
        """
        try:
            if not hasattr(self, 'fallback_listbox'):
                return

            # Listbox から順序を取得
            order = list(self.fallback_listbox.get(0, tk.END))

            if not order:
                self._write_details("⚠️ フォールバック順序が空です。")
                messagebox.showwarning("警告", "フォールバック順序が空です。最低1つのプロバイダを設定してください。")
                return

            # ConfigManager に保存
            if not (self.config_manager and hasattr(self.config_manager, "set")):
                self._write_details("⚠️ ConfigManager未接続。保存できません。")
                return

            # 順序を分割
            primary = order[0]
            fallbacks = order[1:] if len(order) > 1 else []

            # Phase 3 新設定に保存
            self.config_manager.set("ai.primary_provider", primary)
            self.config_manager.set("ai.fallback_providers", fallbacks)

            # 互換性のため旧設定にも保存
            self.config_manager.set("ai.provider_primary", primary)
            if fallbacks:
                self.config_manager.set("ai.provider_fallback", fallbacks[0])

            # 設定を保存
            self.config_manager.save()

            self._write_details(f"✅ フォールバック順序を保存しました: primary={primary}, fallbacks={fallbacks}")
            messagebox.showinfo("保存完了", f"フォールバック順序を保存しました。\n\n順序: {' → '.join(order)}")

            # AI状態をリフレッシュ
            self._request_ai_status("ai_unified.save_fallback")

        except Exception as e:
            self._write_details(f"❌ フォールバック順序の保存エラー: {e}")
            messagebox.showerror("エラー", f"フォールバック順序の保存に失敗しました。\n\n{e}")
            import traceback
            traceback.print_exc()

    def _move_provider_up(self):
        """選択されたプロバイダを上に移動する"""
        try:
            if not hasattr(self, 'fallback_listbox'):
                return

            selection = self.fallback_listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            if idx == 0:
                # すでに一番上
                return

            # 項目を取得
            item = self.fallback_listbox.get(idx)

            # 削除して上に挿入
            self.fallback_listbox.delete(idx)
            self.fallback_listbox.insert(idx - 1, item)

            # 選択を維持
            self.fallback_listbox.selection_set(idx - 1)

        except Exception as e:
            self._write_details(f"❌ プロバイダの移動エラー: {e}")

    def _move_provider_down(self):
        """選択されたプロバイダを下に移動する"""
        try:
            if not hasattr(self, 'fallback_listbox'):
                return

            selection = self.fallback_listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            if idx >= self.fallback_listbox.size() - 1:
                # すでに一番下
                return

            # 項目を取得
            item = self.fallback_listbox.get(idx)

            # 削除して下に挿入
            self.fallback_listbox.delete(idx)
            self.fallback_listbox.insert(idx + 1, item)

            # 選択を維持
            self.fallback_listbox.selection_set(idx + 1)

        except Exception as e:
            self._write_details(f"❌ プロバイダの移動エラー: {e}")

    def _reset_fallback_order(self):
        """フォールバック順序をデフォルトにリセットする"""
        try:
            if not hasattr(self, 'fallback_listbox'):
                return

            # 確認ダイアログ
            result = messagebox.askyesno(
                "確認",
                "フォールバック順序をデフォルト（gemini → local-echo）にリセットしますか？"
            )

            if not result:
                return

            # デフォルト順序
            default_order = ["gemini", "local-echo"]

            # Listbox をクリアして再構築
            self.fallback_listbox.delete(0, tk.END)
            for p in default_order:
                self.fallback_listbox.insert(tk.END, p)

            self._write_details(f"フォールバック順序をリセットしました: {default_order}")

        except Exception as e:
            self._write_details(f"❌ リセットエラー: {e}")


    # =========================
    # 9) ラベル更新
    # =========================
    def update_emotion_label(self, value):
        percent = int(float(value) * 100)
        self.ui_elements['emotion_label'].config(text=f"{percent}%")

    def update_drift_label(self, value):
        percent = int(float(value) * 100)
        self.ui_elements['drift_label'].config(text=f"{percent}%")

    def update_response_prob_label(self, value):
        """応答確率スライダー更新時のラベル更新（Phase 2-1）"""
        percent = int(float(value) * 100)
        self.ui_elements['response_prob_label'].config(text=f"{percent}%")

    def update_delay_label(self, value):
        delay = float(value)
        self.ui_elements['delay_label'].config(text=f"{delay:.1f}秒")

    # =========================
    # 10) パターン編集
    # =========================
    def add_pattern(self, category_key):
        entry = self.ui_elements.get(f'{category_key}_entry')
        listbox = self.ui_elements.get(f'{category_key}_listbox')
        if entry and listbox:
            pattern = entry.get().strip()
            if pattern:
                listbox.insert(tk.END, pattern)
                entry.delete(0, tk.END)

    def remove_pattern(self, category_key):
        listbox = self.ui_elements.get(f'{category_key}_listbox')
        if listbox:
            sel = listbox.curselection()
            if sel:
                listbox.delete(sel[0])

    def edit_pattern(self, category_key):
        listbox = self.ui_elements.get(f'{category_key}_listbox')
        entry = self.ui_elements.get(f'{category_key}_entry')
        if listbox and entry:
            sel = listbox.curselection()
            if sel:
                pattern = listbox.get(sel[0])
                entry.delete(0, tk.END)
                entry.insert(0, pattern)

    # =========================
    # 11) 変数メニュー ✨ 完全版（感情変数対応）
    # =========================
    def _show_variable_menu(self, category_key, button):
        """変数選択ドロップダウンメニューを表示（拡張版）"""
        from datetime import datetime

        menu = tk.Menu(button, tearoff=0)

        botname = self.character_data.get('basic_info', {}).get('name', 'AIアシスタント')

        hour = datetime.now().hour
        time_greeting = "おはよう" if 5 <= hour < 11 else ("こんにちは" if 11 <= hour < 17 else "こんばんは")

        now = datetime.now()
        date_str = now.strftime("%Y年%m月%d日")
        day_names = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        day_str = day_names[now.weekday()]

        # 🔹 基本変数
        basic_vars = [
            ('{username}', 'ユーザー名', 'テストユーザー'),
            ('{botname}', 'AIキャラ名', botname),
            ('{time}', '時刻挨拶', time_greeting),
            ('{date}', '今日の日付', date_str),
            ('{day}', '曜日', day_str),
        ]

        for var_name, description, example in basic_vars:
            label = f"{var_name} : {description} : {example}"
            menu.add_command(
                label=label,
                command=lambda v=var_name: self._insert_variable(category_key, v)
            )

        # 🔹 感情/文脈変数
        menu.add_separator()
        context_vars = [
            ('{emotion}', '感情', 'ランダム(嬉しい/楽しい/悲しい/驚き/普通)'),
            ('{mood}', 'AIムード', 'ランダム(元気/落ち着いてる/眠い/ハイテンション)'),
        ]
        for var_name, description, example in context_vars:
            label = f"{var_name} : {description} : {example}"
            menu.add_command(
                label=label,
                command=lambda v=var_name: self._insert_variable(category_key, v)
            )
        
        # 🔹 動的変数
        menu.add_separator()
        menu.add_command(
            label="{random:A|B|C} : ランダム選択",
            command=lambda: self._insert_variable(category_key, '{random:A|B|C}')
        )
        menu.add_command(
            label="{count:today} : 今日の会話回数 : 1回目",
            command=lambda: self._insert_variable(category_key, '{count:today}')
        )
        menu.add_command(
            label="{count:total} : 累計会話回数 : 1回目",
            command=lambda: self._insert_variable(category_key, '{count:total}')
        )
        
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)

    def _insert_variable(self, category_key, variable):
        """変数を入力フィールドに挿入"""
        entry = self.ui_elements.get(f'{category_key}_entry')
        if entry:
            entry.insert(tk.INSERT, variable)
            entry.focus()

    # =========================
    # 12) Bus / 保存・読込
    # =========================
    def setup_message_bus(self):
        """MessageBus購読のセットアップ（Eventsが無くても動くフォールバック付き）"""
        self.Events = None
        try:
            from shared.event_types import Events as ET
            self.Events = ET
        except Exception:
            try:
                from event_types import Events as ET
                self.Events = ET
            except Exception:
                self.Events = None
        
        if not self.message_bus:
            self._write_details("MessageBus未接続のため購読をスキップ")
            return
        
        topic_cfg = getattr(self.Events, 'CONFIG_UPDATE', 'CONFIG_UPDATE') if self.Events else "CONFIG_UPDATE"
        topic_aiu = getattr(self.Events, 'AI_STATUS_UPDATE', 'AI_STATUS_UPDATE') if self.Events else "AI_STATUS_UPDATE"
        
        try:
            self.message_bus.subscribe(topic_cfg, self._on_config_update)
            self.message_bus.subscribe(topic_aiu, self._on_ai_status_update)
            self._write_details(f"MessageBus購読: {topic_cfg} / {topic_aiu}")
        except Exception as e:
            self._write_details(f"MessageBus購読エラー: {e}")

    def _on_config_update(self, payload=None, **kwargs):
        """設定更新イベント受信時にステータスを再取得"""
        try:
            self._write_details("CONFIG_UPDATE を受信→ステータス再取得")
            self.refresh_status()
        except Exception as e:
            self._write_details(f"CONFIG_UPDATE処理エラー: {e}")

    def _on_ai_status_update(self, payload=None, sender=None):
        """
        AIIntegrationManager からの AI_STATUS_UPDATE を受信して
        「接続状態」ラベルやプロバイダ/モデル表示を更新する。

        期待payload例:
          {"provider": "gemini",
           "model": "gemini-2.5-flash",
           "has_api_key": True,
           "connector_available": True,
           "is_fallback": False}

        v17.5.4 (Task C): 正式な接続判定ロジックを適用
        """
        try:
            data = payload or {}
            if not isinstance(data, dict):
                # 文字列だけ飛んできた場合はログだけ残す
                self._write_details(f"AI_STATUS_UPDATE: {data}")
                return

            provider = data.get("provider") or "-"
            model = data.get("model") or "-"

            # v17.5.4: 正式な接続判定ロジック（Chat / WebSocket タブと同じ）
            has_key = data.get("has_api_key", None)
            connector_ok = bool(data.get("connector_available", False))
            is_fallback = bool(data.get("is_fallback", False))
            standalone = bool(data.get("standalone_mode", False))
            fallback_only = bool(data.get("fallback_only", False))

            # フォールバックモード判定
            if is_fallback or provider in ['fallback', 'local-echo', 'echo']:
                connected = False
            # 正常接続判定
            elif connector_ok and (has_key is None or has_key is True) and not standalone and not fallback_only:
                connected = True
            # 旧形式 (status フィールド) にも対応
            elif "status" in data:
                connected = str(data.get("status")).lower() == "connected"
            else:
                connected = False

            # 状態変化チェック（ログ重複抑制）
            current_status = (provider, model, connected)
            last_status = getattr(self, "_last_ai_status_for_log", None)
            self._last_ai_status_for_log = current_status

            # 状態が変わったときだけログ出力
            if last_status != current_status:
                status_text = f"{provider} / {model} ({'接続' if connected else '未接続'})"
                self._write_details(f"AI状態変化: {status_text}")

            # ラベル更新
            if hasattr(self, "var_provider"):
                self.var_provider.set(provider or "-")
            if hasattr(self, "var_model"):
                self.var_model.set(model or "-")

            # 「接続 / 未接続」ラベル（色付き・プロバイダ/モデル表示）
            if hasattr(self, "_set_ai_connected_label"):
                self._set_ai_connected_label(connected, provider=provider, model=model)
            else:
                # 念のための保険（_set_ai_connected_label が無い場合）
                if connected and hasattr(self, "var_connected"):
                    self.var_connected.set(f"接続中（{provider} / {model}）")
                elif hasattr(self, "var_connected"):
                    self.var_connected.set("未接続")

        except Exception as e:
            self._write_details(f"AI_STATUS_UPDATE処理エラー: {e}")


    def load_personality_config(self):
        return self.load_character_config()

    def load_character_config(self):
        """設定の読み込み（ConfigManager優先、JSONは空ファイル安全化）"""
        try:
            # ✅ デバッグログ追加
            print("=" * 60)
            print("📖 load_character_config 開始")
            print(f"   ConfigManager: {type(self.config_manager).__name__ if self.config_manager else 'None'}")

            # Phase 8: 複数キャラデータの読み込み
            if self.config_manager and hasattr(self.config_manager, "get"):
                saved_characters = self.config_manager.get('ai_characters', {})
                if isinstance(saved_characters, dict) and saved_characters:
                    self.ai_characters = saved_characters
                    print(f"   複数キャラデータ読み込み: {len(self.ai_characters)}キャラ")

                selected = self.config_manager.get('ai_character.selected_name', 'ぎゅるる')
                if selected and selected in self.ai_characters:
                    self.selected_character_name = selected
                    print(f"   選択中キャラ: {selected}")
                elif self.ai_characters:
                    # 選択されたキャラが存在しない場合は最初のキャラを選択
                    self.selected_character_name = list(self.ai_characters.keys())[0]
                    print(f"   デフォルトキャラ選択: {self.selected_character_name}")
                else:
                    # キャラが一つもない場合はデフォルトを作成
                    self.selected_character_name = 'ぎゅるる'
                    self.ai_characters = {}
                    print("   デフォルトキャラ「ぎゅるる」を作成")

                # 選択中キャラのデータを current_character_data にセット
                if self.selected_character_name in self.ai_characters:
                    self.character_data = self.ai_characters[self.selected_character_name].copy()

                # ドロップダウン更新
                self._refresh_character_dropdown()
                if 'name_var' in self.ui_elements:
                    self.ui_elements['name_var'].set(self.selected_character_name)

            if self.config_manager and hasattr(self.config_manager, "get"):
                # ✅ デバッグ: キーの存在確認
                name = self.config_manager.get('ai_personality.basic_info.name', None)
                print(f"   読み込んだ name: {name}")
                
                if name is not None:
                    # ✅ デバッグ: 全キーの値を表示
                    print("   ConfigManagerから読み込み中:")
                    print(f"     - name: {name}")
                    age_val = self.config_manager.get('ai_personality.basic_info.age', '')
                    print(f"     - age: {age_val}")
                    personality_val = self.config_manager.get('ai_personality.basic_info.personality', '')
                    print(f"     - personality: {personality_val[:50] if personality_val else '(空)'}...")
                    
                    # base_settings.limit_len に ai.response_length_limit を反映
                    limit_cfg = self.config_manager.get('ai.response_length_limit', None)
                    base_defaults = {
                        'keywords_triggers': ['ぎゅるる', 'AI', 'ボット'],
                        'keywords_excludes': ['ニート', '無職', '無色'],
                        'blacklist_users': [],
                        'limit_len': 200, 'delay_sec': 2, 'cooldown_sec': 5,
                        'emotion_level': 0.5, 'learning_mode': False,
                    }
                    if isinstance(limit_cfg, (int, float)) and int(limit_cfg) > 0:
                        base_defaults['limit_len'] = int(limit_cfg)

                    self.character_data = {
                        'basic_info': {
                            'name': name,
                            'age': self.config_manager.get('ai_personality.basic_info.age', ''),
                            'personality': self.config_manager.get('ai_personality.basic_info.personality', ''),
                            'background': self.config_manager.get('ai_personality.basic_info.background', ''),
                            'speaking_style': self.config_manager.get('ai_personality.basic_info.speaking_style', ''),
                        },
                        'response_patterns': self.config_manager.get('ai_personality.response_patterns', {}),
                        'behavior_settings': self.config_manager.get('ai_personality.behavior_settings', {'response_probability': 1.0}),
                        'base_settings': self.config_manager.get('ai_personality.base_settings', base_defaults),
                    }
                    
                    # ✅ デバッグ: 読み込んだデータを表示
                    print(f"   ✅ ConfigManagerから読み込み成功: {len(self.character_data)} 項目")
                    
                    if hasattr(self, "populate_ui_data"):
                        self.populate_ui_data()
                        print("   ✅ UIにデータを反映完了")
                    
                    print("=" * 60)
                    return
                else:
                    # ✅ デバッグ: ConfigManagerにデータが無い場合
                    print("   ⚠️ ConfigManagerにai_personality.basic_info.nameが存在しません")
                    print("   → JSONファイルから読み込みます")

            if not hasattr(self, "config_file") or not self.config_file:
                self.config_file = os.path.join(os.path.expanduser("~"), ".gyururu", "config.json")

            data = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    txt = f.read().strip()
                if txt:
                    try:
                        data = json.loads(txt)
                    except Exception:
                        data = {}
                else:
                    data = {}

            ap = data.get("ai_personality", {})
            if ap:
                self.character_data = {
                    'basic_info': ap.get('basic_info', {}),
                    'response_patterns': ap.get('response_patterns', {}),
                    'behavior_settings': ap.get('behavior_settings', {'response_probability': 1.0}),
                    'base_settings': ap.get('base_settings', {
                        'keywords_triggers': ['ぎゅるる', 'AI', 'ボット'],
                        'keywords_excludes': ['ニート', '無職', '無色'],
                        'blacklist_users': [],
                        'limit_len': 200, 'delay_sec': 2, 'cooldown_sec': 5,
                        'emotion_level': 0.5, 'learning_mode': False,
                    }),
                }

            if hasattr(self, "populate_ui_data"):
                self.populate_ui_data()

        except Exception as e:
            print(f"⚠️ 設定読み込みエラー: {e}")
            if hasattr(self, "populate_ui_data"):
                self.populate_ui_data()

    def populate_ui_data(self):
        """設定データをUIに反映"""
        try:
            # --- 基本情報 ---
            basic_info = self.character_data.get('basic_info', {})

            # Phase 8: Combobox対応
            if 'name_var' in self.ui_elements:
                self.ui_elements['name_var'].set(basic_info.get('name', ''))
            else:
                name_entry = self.ui_elements.get('name')
                if name_entry:
                    name_entry.delete(0, tk.END)
                    name_entry.insert(0, basic_info.get('name', ''))

            age_entry = self.ui_elements.get('age')
            if age_entry:
                age_entry.delete(0, tk.END)
                age_entry.insert(0, basic_info.get('age', ''))

            personality_txt = self.ui_elements.get('personality')
            if personality_txt:
                personality_txt.delete("1.0", tk.END)
                personality_txt.insert("1.0", basic_info.get('personality', ''))

            background_txt = self.ui_elements.get('background')
            if background_txt:
                background_txt.delete("1.0", tk.END)
                background_txt.insert("1.0", basic_info.get('background', ''))

            speaking_style_txt = self.ui_elements.get('speaking_style')
            if speaking_style_txt:
                speaking_style_txt.delete("1.0", tk.END)
                speaking_style_txt.insert("1.0", basic_info.get('speaking_style', ''))

            # --- 応答パターン（各カテゴリのリストボックス） ---
            response_patterns = self.character_data.get('response_patterns', {})
            for category in ['greeting', 'thanks', 'goodbye', 'reaction_positive', 'reaction_negative']:
                listbox = self.ui_elements.get(f'{category}_listbox')
                if listbox:
                    listbox.delete(0, tk.END)
                    for pattern in response_patterns.get(category, []):
                        listbox.insert(tk.END, pattern)

            # --- 行動設定（スライダー / チェックなど） ---
            behavior = self.character_data.get('behavior_settings', {})
            if 'emotional_variance' in self.ui_elements:
                self.ui_elements['emotional_variance'].set(behavior.get('emotional_variance', 0.5))
            if 'memory_retention' in self.ui_elements:
                self.ui_elements['memory_retention'].set(behavior.get('memory_retention', True))
            if 'learning_enabled' in self.ui_elements:
                self.ui_elements['learning_enabled'].set(behavior.get('learning_enabled', False))
            if 'auto_responses' in self.ui_elements:
                self.ui_elements['auto_responses'].set(behavior.get('auto_responses', True))
            if 'context_awareness' in self.ui_elements:
                self.ui_elements['context_awareness'].set(behavior.get('context_awareness', True))
            if 'mood_simulation' in self.ui_elements:
                self.ui_elements['mood_simulation'].set(behavior.get('mood_simulation', False))
            if 'personality_drift' in self.ui_elements:
                self.ui_elements['personality_drift'].set(behavior.get('personality_drift', 0.1))
            if 'response_delay' in self.ui_elements:
                self.ui_elements['response_delay'].set(behavior.get('response_delay', 0.5))
            if 'conversation_memory_limit' in self.ui_elements:
                self.ui_elements['conversation_memory_limit'].set(behavior.get('conversation_memory_limit', 100))

            # ラベルの数値表示を同期
            if 'emotional_variance' in self.ui_elements:
                self.update_emotion_label(self.ui_elements['emotional_variance'].get())
            if 'personality_drift' in self.ui_elements:
                self.update_drift_label(self.ui_elements['personality_drift'].get())
            if 'response_delay' in self.ui_elements:
                self.update_delay_label(self.ui_elements['response_delay'].get())

            # --- ベース設定をUIに同期 ---
            base_settings = self.character_data.get('base_settings', {})
            if 'limit_len' in self.ui_elements and base_settings.get('limit_len') is not None:
                try:
                    self.ui_elements['limit_len'].set(int(base_settings.get('limit_len')))
                except Exception:
                    pass
            if 'delay_sec' in self.ui_elements and base_settings.get('delay_sec') is not None:
                try:
                    self.ui_elements['delay_sec'].set(int(base_settings.get('delay_sec')))
                except Exception:
                    pass
            if 'cooldown_sec' in self.ui_elements and base_settings.get('cooldown_sec') is not None:
                try:
                    self.ui_elements['cooldown_sec'].set(int(base_settings.get('cooldown_sec')))
                except Exception:
                    pass
            if 'learning_mode' in self.ui_elements and base_settings.get('learning_mode') is not None:
                try:
                    self.ui_elements['learning_mode'].set(bool(base_settings.get('learning_mode')))
                except Exception:
                    pass

            # キーワード欄
            # （Entry/Textなのでそのまま整形して入れる）
            kw_tr = self.ui_elements.get('kw_triggers')
            if kw_tr is not None:
                try:
                    val = ','.join(base_settings.get('keywords_triggers') or [])
                    if hasattr(kw_tr, 'set'):
                        kw_tr.set(val)
                    else:
                        kw_tr.delete(0, tk.END)
                        kw_tr.insert(0, val)
                except Exception:
                    pass

            kw_ex = self.ui_elements.get('kw_excludes')
            if kw_ex is not None:
                try:
                    val = ','.join(base_settings.get('keywords_excludes') or [])
                    if hasattr(kw_ex, 'set'):
                        kw_ex.set(val)
                    else:
                        kw_ex.delete(0, tk.END)
                        kw_ex.insert(0, val)
                except Exception:
                    pass

            kw_bl = self.ui_elements.get('kw_blacklist')
            if kw_bl is not None:
                try:
                    val = "\n".join(base_settings.get('blacklist_users') or [])
                    kw_bl.delete("1.0", tk.END)
                    kw_bl.insert("1.0", val)
                except Exception:
                    pass

            # Phase 9: 語尾欄の復元
            ending_entry = self.ui_elements.get('ending')
            if ending_entry is not None:
                try:
                    ending_val = base_settings.get('ending', '')
                    ending_entry.delete(0, tk.END)
                    ending_entry.insert(0, ending_val)
                except Exception:
                    pass

            # === 技術設定タブ（プロバイダ / モデル / APIキー） ===
            cm = self.config_manager if (self.config_manager and hasattr(self.config_manager, "get")) else None
            prov_cfg  = cm.get("ai.provider", None) if cm else None
            model_cfg = cm.get("ai.model", None) if cm else None
            api_cfg   = cm.get("ai.api_key", None) if cm else None

            if 'provider_tech' in self.ui_elements:
                v = self.ui_elements['provider_tech']
                try:
                    current = v.get()
                except Exception:
                    current = ""
                new_val = (prov_cfg.strip() if isinstance(prov_cfg, str) and prov_cfg.strip() else (current or "gemini"))
                if hasattr(v, "set"):
                    v.set(new_val)
                elif hasattr(v, "delete") and hasattr(v, "insert"):
                    v.delete(0, tk.END)
                    v.insert(0, new_val)

            if 'model_tech' in self.ui_elements:
                v = self.ui_elements['model_tech']
                try:
                    current = v.get()
                except Exception:
                    current = ""
                default_model = "gemini-2.5-flash"
                new_val = (model_cfg.strip() if isinstance(model_cfg, str) and model_cfg.strip() else (current or default_model))
                if hasattr(v, "set"):
                    v.set(new_val)
                elif hasattr(v, "delete") and hasattr(v, "insert"):
                    v.delete(0, tk.END)
                    v.insert(0, new_val)

            if 'api_key_tech' in self.ui_elements:
                v = self.ui_elements['api_key_tech']
                if isinstance(api_cfg, str) and api_cfg.strip():
                    if hasattr(v, "set"):
                        v.set(api_cfg)
                    elif hasattr(v, "delete") and hasattr(v, "insert"):
                        v.delete(0, tk.END)
                        v.insert(0, api_cfg)

            if hasattr(self, 'refresh_status'):
                try:
                    self.refresh_status()
                except Exception:
                    pass

        except Exception as e:
            print(f"⚠️ UI更新エラー: {e}")

    def save_personality_config(self):
        """設定保存（ConfigManager があればそこへ保存／無ければ従来JSON）"""
        try:
            # ✅ デバッグログ追加
            print("=" * 60)
            print("💾 save_personality_config 開始")

            # UI → 内部データへ反映
            if hasattr(self, "_collect_ui_to_data"):
                self._collect_ui_to_data()

            # Phase 8: 複数キャラ管理 - 現在のキャラを保存
            if self.selected_character_name:
                self.ai_characters[self.selected_character_name] = self.character_data.copy()
                print(f"   現在のキャラ「{self.selected_character_name}」を保存")

            # ---- 最大文字数（基本設定のlimit_len）を取得してクランプ ----
            try:
                resp_var = self.ui_elements.get('limit_len')
                resp_limit = int(resp_var.get()) if resp_var else 200
            except Exception:
                resp_limit = 200
            if resp_limit < 50:
                resp_limit = 50
            if resp_limit > 1000:
                resp_limit = 1000

            # ConfigManager へ保存する場合
            if self.config_manager and (isinstance(self.config_manager, dict) or hasattr(self.config_manager, "set")):
                p = self.character_data
                
                print("   ConfigManagerに保存中...")

                # --- ai_personality.* ---
                self._cm_set('ai_personality.basic_info.name',           p.get('basic_info', {}).get('name'))
                self._cm_set('ai_personality.basic_info.age',            p.get('basic_info', {}).get('age'))
                self._cm_set('ai_personality.basic_info.personality',    p.get('basic_info', {}).get('personality'))
                self._cm_set('ai_personality.basic_info.background',     p.get('basic_info', {}).get('background'))
                self._cm_set('ai_personality.basic_info.speaking_style', p.get('basic_info', {}).get('speaking_style'))
                self._cm_set('ai_personality.response_patterns',         p.get('response_patterns', {}))
                self._cm_set('ai_personality.behavior_settings',         p.get('behavior_settings', {}))

                # base_settings にも反映（UIの值を保持）
                base_now = dict(p.get('base_settings', {}))
                base_now['limit_len'] = resp_limit
                self._cm_set('ai_personality.base_settings', base_now)

                # --- 技術設定（存在時のみ）---
                if 'provider_tech' in self.ui_elements:
                    self._cm_set('ai.provider', self.ui_elements['provider_tech'].get())
                if 'model_tech' in self.ui_elements:
                    self._cm_set('ai.model', self.ui_elements['model_tech'].get())
                if 'api_key_tech' in self.ui_elements:
                    api_key_val = (self.ui_elements['api_key_tech'].get() or '').strip()
                    if api_key_val:
                        self._cm_set('ai.api_key', api_key_val)

                # --- 文字数上限の保存（基本設定に統合）---
                self._cm_set('ai.response_length_limit', resp_limit)
                self._cm_set('chat.max_response_length', resp_limit)

                # ※ 応答制御設定（応答モード・応答確率）はチャットタブで保存

                # Phase 8: 複数AIキャラデータ全体を保存
                self._cm_set('ai_characters', self.ai_characters)
                self._cm_set('ai_character.selected_name', self.selected_character_name)
                print(f"   複数キャラデータ保存完了（{len(self.ai_characters)}キャラ）")

                # ✅ 修正: system_prompt の即時反映を強化
                sp = self._compose_system_prompt() if hasattr(self, "_compose_system_prompt") else ""
                if sp:
                    print(f"   system_prompt: {sp[:100]}...")
                    self._cm_set('ai.system_prompt', sp)
                    
                    # ✅ 方法1: app_instanceのai_connectorに直接設定
                    try:
                        if self.app_instance:
                            ac = getattr(self.app_instance, 'ai_connector', None)
                            if ac:
                                print(f"   ai_connector検出: {type(ac).__name__}")
                                
                                # default_system_promptを設定
                                if hasattr(ac, 'default_system_prompt'):
                                    setattr(ac, 'default_system_prompt', sp)
                                    print("   ✅ ai_connector.default_system_prompt を更新")
                                
                                # system_promptも設定（プロバイダによって異なる）
                                if hasattr(ac, 'system_prompt'):
                                    setattr(ac, 'system_prompt', sp)
                                    print("   ✅ ai_connector.system_prompt を更新")
                            else:
                                print("   ⚠️ app_instance.ai_connector が存在しません")
                    except Exception as e:
                        print(f"   ⚠️ ai_connector設定エラー: {e}")
                    
                    # ✅ 方法2: MessageBusで通知（他のコンポーネントに反映）
                    try:
                        if self.message_bus:
                            ET = self.Events if hasattr(self, "Events") else Events
                            ai_changed_event = getattr(ET, "AI_PERSONALITY_CHANGED", "AI_PERSONALITY_CHANGED")
                            
                            self.message_bus.publish(
                                ai_changed_event,
                                {
                                    'system_prompt': sp,
                                    'personality': self.character_data,
                                    'source': 'tab_ai_unified'
                                },
                                sender='tab_ai_unified'
                            )
                            print("   ✅ AI_PERSONALITY_CHANGED イベント送出")
                    except Exception as e:
                        print(f"   ⚠️ イベント送出エラー: {e}")

                # --- Config 保存 ---
                try:
                    self.config_manager.save()
                    print("   ✅ ConfigManager.save() 完了")
                except Exception as e:
                    print(f"   ⚠️ ConfigManager.save() エラー: {e}")

                # --- プロバイダ設定の保存と通知 ---
                try:
                    self._save_provider_and_emit()
                except Exception as e:
                    print(f"   ⚠️ プロバイダ設定の保存・通知エラー: {e}")

                # --- Bus 通知（CONFIG_UPDATE）---
                try:
                    ET = self.Events if hasattr(self, "Events") else Events
                except Exception:
                    ET = None
                topic = getattr(ET, "CONFIG_UPDATE", "CONFIG_UPDATE")
                if getattr(self, "message_bus", None):
                    try:
                        self.message_bus.publish(topic, {'scope': 'ai'}, sender='tab_ai_unified')
                        print(f"   ✅ {topic} イベント送出")
                    except Exception as e:
                        print(f"   ⚠️ CONFIG_UPDATE送出エラー: {e}")

                # ✅ v17.4: AI_STATUS_REQUEST は _save_provider_and_emit で一本化
                # （プロバイダ/モデル変更時にのみAI状態を更新）

                # --- UI メッセージ ---
                if 'status_text' in self.ui_elements:
                    self._write_details("設定を保存しました（ConfigManager）\n")
                try:
                    messagebox.showinfo("保存", "設定を保存しました（ConfigManager）")
                except Exception:
                    pass
                
                print("=" * 60)
                return

            # --- JSON フォールバック ---
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            base = {}
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        txt = f.read().strip()
                    base = json.loads(txt) if txt else {}
                except Exception:
                    base = {}

            base.setdefault("ai_personality", {})
            # 保存時に UI の limit_len を反映
            self.character_data.setdefault('base_settings', {})
            self.character_data['base_settings']['limit_len'] = resp_limit
            base["ai_personality"] = self.character_data

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(base, f, ensure_ascii=False, indent=2)

            if 'status_text' in self.ui_elements:
                self._write_details("設定を保存しました（JSON）\n")
            try:
                messagebox.showinfo("保存", "設定を保存しました（JSON）")
            except Exception:
                pass

        except Exception as e:
            try:
                messagebox.showerror("保存エラー", str(e))
            except Exception:
                print(f"保存エラー: {e}")

    def _compose_system_prompt(self) -> str:
        """UI/内部データから system_prompt を生成。最大文字数も反映。"""
        try:
            bi = self.character_data.get('basic_info', {}) if hasattr(self, 'character_data') else {}
            name = (bi.get('name') or '').strip()
            age = (bi.get('age') or '').strip()
            personality = (bi.get('personality') or '').strip()
            background = (bi.get('background') or '').strip()
            speaking = (bi.get('speaking_style') or '').strip()

            rp = self.character_data.get('response_patterns', {}) if hasattr(self, 'character_data') else {}

            def _lines(key):
                items = rp.get(key, []) or []
                return "\n".join(f"- {s}" for s in items if isinstance(s, str) and s.strip())

            # 文字数上限の決定（UIのlimit_len 優先 → Config → 既定200）
            limit = 200
            try:
                if 'limit_len' in getattr(self, 'ui_elements', {}) and hasattr(self.ui_elements['limit_len'], 'get'):
                    limit = int(self.ui_elements['limit_len'].get() or 200)
                elif self.config_manager and hasattr(self.config_manager, 'get'):
                    v = self.config_manager.get('ai.response_length_limit', 200)
                    if isinstance(v, (int, float)):
                        limit = int(v)
                if limit < 50:
                    limit = 50
                if limit > 1000:
                    limit = 1000
            except Exception:
                limit = 200

            prompt = (
                "あなたは配信アシスタントAI『{name}』です。\n"
                "## 基本設定\n"
                f"- 名前: {name}\n"
                f"- 性格: {personality}\n"
                f"- 口調: {speaking}\n"
                "\n"
                "## 応答ルール\n"
                "- ユーザーとの自然な対話を優先してください。\n"
                "- **重要**: プロフィール、自己紹介、キャラクター説明などは絶対に出力しないでください。\n"
                "  会話の内容だけを返してください（「## プロフィール」「## 性格」「## 口調」などの見出しは不要です）。\n"
                "- ユーザーが「自己紹介して」と明示的に尋ねた場合のみ、簡潔に答えてください。\n"
                "- 配信を盛り上げるため、短く歯切れよく、明るく返答してください。\n"
                f"- 応答は{limit}文字以内に収めてください。\n"
                "- 過度に丁寧すぎず、フレンドリーなトーンで応答してください。\n"
                "- 応答の最初に「---」などの区切り記号を入れないでください。\n"
            ).format(name=name or "ぎゅるる")
            return prompt
        except Exception:
            return ""

    # =========================
    # 13) 内部ヘルパー
    # =========================
    def reset_character_config(self):
        """設定リセット"""
        try:
            self.__init_default_data()
            self.populate_ui_data()
            messagebox.showinfo("リセット", "設定を初期化しました")
        except Exception as e:
            messagebox.showerror("リセットエラー", str(e))

    def __init_default_data(self):
        """デフォルトデータで初期化"""
        self.character_data = {
            "archived": False,  # Phase 10: アーカイブフラグ
            "basic_info": {
                "name": "ぎゅるる",
                "age": "不明",
                "personality": "元気いっぱいで、ちょっぴりおっちょこちょいな頑張り屋さん",
                "background": "配信サポートAI",
                "speaking_style": "語尾に「～ぎゅる！」「～なぎゅる？」をつける明るい話し方"
            },
            "response_patterns": {
                "greeting": ["こんにちは!", "おはようございます!", "こんばんは!"],
                "thanks": ["ありがとうございます!", "感謝します!", "嬉しいです!"],
                "goodbye": ["またお会いしましょう!", "お疲れ様でした!", "さようなら!"],
                "reaction_positive": ["すごいですね!", "素晴らしい!", "いいですね!"],
                "reaction_negative": ["大丈夫ですか?", "心配です", "気をつけてくださいね"]
            },
            "behavior_settings": {
                "emotional_variance": 0.5,
                "memory_retention": True,
                "learning_enabled": False,
                "auto_responses": True,
                "context_awareness": True,
                "mood_simulation": False,
                "personality_drift": 0.1,
                "response_delay": 0.5,
                "conversation_memory_limit": 100
            },
            "base_settings": {
                "keywords_triggers": ["ぎゅるる", "AI", "ボット"],
                "keywords_excludes": ["ニート", "無職", "無色"],
                "blacklist_users": [],
                "limit_len": 100,  # Phase 9: デフォルトを100に変更
                "delay_sec": 2,
                "cooldown_sec": 5,
                "emotion_level": 0.5,
                "learning_mode": False,
                "ending": ""  # Phase 9: 語尾欄追加
            }
        }

    def _collect_ui_to_data(self):
        """UI の値を character_data に反映（現行UIに完全対応）"""
        try:
            # --- basic_info ---
            b = self.character_data.setdefault('basic_info', {})
            if 'name_var' in self.ui_elements:
                # Phase 8: Combobox対応
                b['name'] = (self.ui_elements['name_var'].get() or '').strip()
            elif 'name' in self.ui_elements:
                b['name'] = (self.ui_elements['name'].get() or '').strip()
            if 'age' in self.ui_elements:
                b['age'] = (self.ui_elements['age'].get() or '').strip()
            if 'personality' in self.ui_elements:
                b['personality'] = self.ui_elements['personality'].get("1.0", "end").strip()
            if 'background' in self.ui_elements:
                b['background'] = self.ui_elements['background'].get("1.0", "end").strip()
            if 'speaking_style' in self.ui_elements:
                b['speaking_style'] = self.ui_elements['speaking_style'].get("1.0", "end").strip()

            # --- base_settings（キーワード & 応答タイミング & 語尾）---
            base = self.character_data.setdefault('base_settings', {})
            # Phase 9: 語尾欄の取得
            if 'ending' in self.ui_elements:
                base['ending'] = (self.ui_elements['ending'].get() or '').strip()
            if 'kw_triggers' in self.ui_elements:
                base['keywords_triggers'] = [
                    s.strip() for s in self.ui_elements['kw_triggers'].get().split(",") if s.strip()
                ]
            if 'kw_excludes' in self.ui_elements:
                base['keywords_excludes'] = [
                    s.strip() for s in self.ui_elements['kw_excludes'].get().split(",") if s.strip()
                ]
            if 'kw_blacklist' in self.ui_elements:
                base['blacklist_users'] = [
                    s.strip() for s in self.ui_elements['kw_blacklist'].get("1.0", "end").splitlines() if s.strip()
                ]

            # 応答タイミング（行動設定タブから）
            if 'limit_len' in self.ui_elements:
                try:
                    base['limit_len'] = int(self.ui_elements['limit_len'].get())
                except Exception:
                    pass
            if 'delay_sec' in self.ui_elements:
                try:
                    base['delay_sec'] = int(self.ui_elements['delay_sec'].get())
                except Exception:
                    pass
            if 'cooldown_sec' in self.ui_elements:
                try:
                    base['cooldown_sec'] = int(self.ui_elements['cooldown_sec'].get())
                except Exception:
                    pass

            # --- behavior_settings（行動設定タブ）---
            beh = self.character_data.setdefault('behavior_settings', {})

            if 'emotional_variance' in self.ui_elements:
                try:
                    beh['emotional_variance'] = float(self.ui_elements['emotional_variance'].get())
                except Exception:
                    pass
            if 'personality_drift' in self.ui_elements:
                try:
                    beh['personality_drift'] = float(self.ui_elements['personality_drift'].get())
                except Exception:
                    pass
            if 'memory_retention' in self.ui_elements:
                try:
                    beh['memory_retention'] = bool(self.ui_elements['memory_retention'].get())
                except Exception:
                    pass
            if 'conversation_memory_limit' in self.ui_elements:
                try:
                    beh['conversation_memory_limit'] = int(self.ui_elements['conversation_memory_limit'].get())
                except Exception:
                    pass
            if 'learning_enabled' in self.ui_elements:
                try:
                    beh['learning_enabled'] = bool(self.ui_elements['learning_enabled'].get())
                except Exception:
                    pass
            if 'context_awareness' in self.ui_elements:
                try:
                    beh['context_awareness'] = bool(self.ui_elements['context_awareness'].get())
                except Exception:
                    pass
            if 'mood_simulation' in self.ui_elements:
                try:
                    beh['mood_simulation'] = bool(self.ui_elements['mood_simulation'].get())
                except Exception:
                    pass

            # （UIに戻したら再利用）
            if 'auto_responses' in self.ui_elements:
                try:
                    beh['auto_responses'] = bool(self.ui_elements['auto_responses'].get())
                except Exception:
                    pass

            # --- 応答制御設定（Phase 2-1）---
            if 'response_mode' in self.ui_elements:
                try:
                    beh['response_mode'] = self.ui_elements['response_mode'].get()
                except Exception:
                    pass

            if 'response_probability' in self.ui_elements:
                try:
                    beh['response_probability'] = float(self.ui_elements['response_probability'].get())
                except Exception:
                    pass

        except Exception as e:
            print(f"_collect_ui_to_data error: {e}")

    def _cm_set(self, dotted_key, value):
        """ConfigManager へドットキーで保存"""
        try:
            if hasattr(self.config_manager, "set"):
                self.config_manager.set(dotted_key, value)
            elif isinstance(self.config_manager, dict):
                cur = self.config_manager
                parts = dotted_key.split(".")
                for k in parts[:-1]:
                    cur = cur.setdefault(k, {})
                cur[parts[-1]] = value
        except Exception:
            pass

    def _bus_publish(self, event, payload, sender="ai_unified") -> bool:
        """Bus発行ヘルパ（統一版）"""
        bus = getattr(self, "message_bus", None)
        if not bus:
            return False
        try:
            # Eventsに無い場合でも素の文字列で投げられるようにする
            try:
                ET = self.Events if hasattr(self, "Events") else Events
                evt = getattr(ET, event, event)
            except Exception:
                evt = event
            bus.publish(evt, payload, sender=sender)
            return True
        except Exception as e:
            print(f"⚠️ Bus発行エラー: {event} ({e})")
            return False

    def _request_ai_status(self, source: str = "") -> None:
        """AI_STATUS_REQUEST をクールダウン付きで Bus に発行するヘルパー。"""
        # クールダウン判定（連打や多重呼び出しを抑制）
        try:
            now = datetime.now().timestamp()
            last = getattr(self, "_last_status_request_ts", 0.0)
            cooldown = getattr(self, "_status_request_cooldown", 0.5)
            if now - last < cooldown:
                self._write_details(f"⏳ AI_STATUS_REQUEST スキップ（クールダウン中）: {source}")
                return
            self._last_status_request_ts = now
        except Exception:
            # タイムスタンプ系のエラーは致命的ではないので無視して続行
            pass

        payload = {"source": source or "ai_unified"}
        if not self._bus_publish("AI_STATUS_REQUEST", payload, sender="tab_ai_unified"):
            self._write_details(f"⚠️ AI_STATUS_REQUEST 送信失敗: {payload}")
        else:
            self._write_details(f"📡 AI_STATUS_REQUEST を送信しました: {payload}")

    def _ev(self, name: str):
        """Enum優先でイベント名を取得、未定義の場合は元の文字列を返す"""
        try:
            ET = self.Events if hasattr(self, "Events") else Events
            return getattr(ET, name.upper(), name.lower())
        except Exception:
            return name.lower()

    def _get_selected_provider_tuple(self):
        """
        UI上の選択肢から (primary, fallback, model) を取り出す。
        v17.2では provider_tech / model_tech を使用。
        UI変数が無い場合は UnifiedConfigManager の値を参照。
        """
        # primary (provider_tech から取得)
        primary = None
        if 'provider_tech' in self.ui_elements:
            try:
                primary = (self.ui_elements['provider_tech'].get() or "").strip()
            except Exception:
                pass
        if (not primary) and hasattr(self, "config_manager") and self.config_manager:
            try:
                primary = self.config_manager.get("ai.provider", None)
                if not primary:
                    primary = self.config_manager.get("ai.provider_primary", None)
            except Exception:
                primary = None
        if not primary:
            primary = "gemini"

        # fallback (固定またはConfigから)
        fallback = None
        if hasattr(self, "config_manager") and self.config_manager:
            try:
                fallback = self.config_manager.get("ai.provider_fallback", None)
            except Exception:
                fallback = None
        if not fallback:
            fallback = "local-echo"

        # model (model_tech から取得)
        model = None
        if 'model_tech' in self.ui_elements:
            try:
                model = (self.ui_elements['model_tech'].get() or "").strip()
            except Exception:
                pass
        if (not model) and hasattr(self, "config_manager") and self.config_manager:
            try:
                model = self.config_manager.get("ai.model", None)
            except Exception:
                model = None
        if not model:
            model = "gemini-2.5-flash"

        return primary, fallback, model

    def _save_provider_and_emit(self):
        """
        プロバイダ設定を UnifiedConfig に保存し、AI状態を更新。

        v17.4 設定保存フロー統一:
        1) 保存（ai.provider_primary / ai.provider_fallback / ai.model）
        2) AI_STATUS_REQUEST を publish（プロバイダ変更時のみAI状態を更新）
        """
        try:
            primary, fallback, model = self._get_selected_provider_tuple()
            print(f"   📡 プロバイダ設定取得: primary={primary}, fallback={fallback}, model={model}")

            # 1) 保存
            if hasattr(self, "config_manager") and self.config_manager and hasattr(self.config_manager, "set"):
                try:
                    self.config_manager.set("ai.provider_primary", primary)
                    self.config_manager.set("ai.provider_fallback", fallback)
                    self.config_manager.set("ai.model", model)
                    self.config_manager.save()
                    print(f"   ✅ プロバイダ設定をConfigに保存完了")
                except Exception as ce:
                    print(f"   ⚠️ プロバイダ設定の保存で例外: {ce}")
                    self._write_details(f"⚠️ プロバイダ設定の保存で例外: {ce}")

            # 2) 状態リフレッシュ要求（プロバイダ変更時）
            print(f"   📤 AI_STATUS_REQUEST 発行")
            # プロバイダ変更時もクールダウン付きで状態再取得を依頼
            self._request_ai_status("ai_unified.save_provider")

            # UIログ
            self._write_details("✅ プロバイダ設定を保存しました。AIの状態を更新しています…")
            print(f"   ✅ プロバイダ設定保存完了")

        except Exception as e:
            print(f"   ❌ プロバイダ設定の反映に失敗: {e}")
            import traceback
            traceback.print_exc()
            self._write_details(f"❌ プロバイダ設定の反映に失敗: {e}")

    def _on_provider_apply(self):
        """
        「保存」や「接続テスト」ボタンから呼ぶだけの薄いハンドラ。
        見た目は変えずに、保存→通知→状態問い合わせを1アクションで実施。
        """
        self._save_provider_and_emit()

    def start_auto_save(self):
        """自動保存（未使用）"""
        pass

    # =========================
    # Phase 8: 複数AIキャラ管理
    # =========================
    def _on_character_selected(self, event=None):
        """キャラ選択時の処理"""
        try:
            selected_name = self.ui_elements['name_var'].get()
            if selected_name and selected_name != self.selected_character_name:
                # 現在のデータを保存
                self._collect_ui_to_data()
                if self.selected_character_name:
                    self.ai_characters[self.selected_character_name] = self.character_data.copy()

                # 新しいキャラに切り替え
                self.selected_character_name = selected_name
                if selected_name in self.ai_characters:
                    self.character_data = self.ai_characters[selected_name].copy()
                else:
                    self.character_data = self._default_character_template()
                    self.ai_characters[selected_name] = self.character_data.copy()

                # UIに反映
                self.populate_ui_data()

                # ConfigManagerに保存
                if self.config_manager and hasattr(self.config_manager, "set"):
                    self.config_manager.set("ai_character.selected_name", selected_name)

                print(f"✅ AIキャラ切り替え: {selected_name}")
        except Exception as e:
            print(f"❌ キャラ選択エラー: {e}")
            import traceback
            traceback.print_exc()

    def _on_add_character(self):
        """AIキャラ追加ボタン"""
        from tkinter import simpledialog, messagebox

        name = simpledialog.askstring("AIキャラ追加", "追加するAIキャラ名を入力してください：")
        if not name:
            return
        name = name.strip()

        if not name:
            messagebox.showwarning("入力エラー", "キャラ名を入力してください。")
            return

        if name in self.ai_characters:
            messagebox.showwarning("重複エラー", f"「{name}」は既に存在します。")
            return

        # 現在のデータを保存
        self._collect_ui_to_data()
        if self.selected_character_name:
            self.ai_characters[self.selected_character_name] = self.character_data.copy()

        # 新しいキャラを作成
        self.selected_character_name = name
        self.character_data = self._default_character_template()
        self.character_data['basic_info']['name'] = name
        self.ai_characters[name] = self.character_data.copy()

        # ドロップダウンを更新
        self._refresh_character_dropdown()
        self.ui_elements['name_var'].set(name)

        # UIに反映
        self.populate_ui_data()

        # 追加直後に保存
        self.save_personality_config()

        messagebox.showinfo("成功", f"「{name}」を追加しました！")
        print(f"✅ AIキャラ追加: {name}")

    def _default_character_template(self) -> dict:
        """デフォルトキャラテンプレート"""
        return {
            "archived": False,  # Phase 10: アーカイブフラグ
            "basic_info": {
                "name": "",
                "age": "不明",
                "personality": "",
                "background": "",
                "speaking_style": ""
            },
            "response_patterns": {
                "greeting": [],
                "thanks": [],
                "goodbye": [],
                "reaction_positive": [],
                "reaction_negative": []
            },
            "behavior_settings": {
                "emotional_variance": 0.5,
                "memory_retention": True,
                "learning_enabled": False,
                "auto_responses": True,
                "context_awareness": True,
                "mood_simulation": False,
                "personality_drift": 0.1,
                "response_delay": 0.5,
                "conversation_memory_limit": 100
            },
            "base_settings": {
                "keywords_triggers": [],
                "keywords_excludes": [],
                "blacklist_users": [],
                "limit_len": 100,  # Phase 9: デフォルト100
                "delay_sec": 2,
                "cooldown_sec": 5,
                "emotion_level": 0.5,
                "learning_mode": False,
                "ending": ""  # Phase 9: 語尾
            }
        }

    def _refresh_character_dropdown(self):
        """キャラドロップダウン更新（Phase 10: アーカイブ表示制御対応）"""
        try:
            show_archived = self.show_archived_var.get()

            # Phase 10: アーカイブフラグがないキャラには False を補完
            for name, data in self.ai_characters.items():
                if 'archived' not in data:
                    data['archived'] = False

            # Phase 10: アーカイブ表示制御
            if show_archived:
                # すべて表示
                names = sorted(self.ai_characters.keys())
            else:
                # archived == False のみ表示
                names = sorted([
                    name for name, data in self.ai_characters.items()
                    if not data.get('archived', False)
                ])

            if 'name' in self.ui_elements:
                self.ui_elements['name']['values'] = names

            print(f"✅ ドロップダウン更新: {len(names)}キャラ表示（アーカイブ表示: {show_archived}）")
        except Exception as e:
            print(f"⚠️ ドロップダウン更新エラー: {e}")

    def _on_show_archived_changed(self):
        """「アーカイブも表示」チェックボックス変更時"""
        try:
            self._refresh_character_dropdown()

            # 現在選択中のキャラがアーカイブ済みで、かつ表示OFFの場合は「ぎゅるる」に退避
            if not self.show_archived_var.get():
                current = self.selected_character_name
                if current in self.ai_characters:
                    if self.ai_characters[current].get('archived', False):
                        # アーカイブ済みキャラが選択されているので「ぎゅるる」に退避
                        self.selected_character_name = 'ぎゅるる'
                        if 'ぎゅるる' in self.ai_characters:
                            self.character_data = self.ai_characters['ぎゅるる'].copy()
                        self.ui_elements['name_var'].set('ぎゅるる')
                        self.populate_ui_data()
                        print("⚠️ アーカイブ済みキャラは非表示のため、ぎゅるるに切り替えました")
        except Exception as e:
            print(f"❌ アーカイブ表示切替エラー: {e}")
            import traceback
            traceback.print_exc()

    def _on_archive_character(self):
        """AIキャラをアーカイブ（Phase 10: トグル式）"""
        from tkinter import messagebox

        try:
            current_name = self.selected_character_name

            # 「ぎゅるる」は不可
            if current_name == "ぎゅるる":
                messagebox.showwarning("保護されたキャラ", "「ぎゅるる」はアーカイブできません。")
                return

            if current_name not in self.ai_characters:
                messagebox.showwarning("エラー", "選択中のキャラが見つかりません。")
                return

            # 現在のアーカイブ状態を取得
            current_archived = self.ai_characters[current_name].get('archived', False)
            new_archived = not current_archived

            # トグル
            self.ai_characters[current_name]['archived'] = new_archived

            # 保存
            self.save_personality_config()

            # ドロップダウン更新
            self._refresh_character_dropdown()

            # アーカイブ表示OFFかつアーカイブした場合は「ぎゅるる」に退避
            if new_archived and not self.show_archived_var.get():
                self.selected_character_name = 'ぎゅるる'
                if 'ぎゅるる' in self.ai_characters:
                    self.character_data = self.ai_characters['ぎゅるる'].copy()
                self.ui_elements['name_var'].set('ぎゅるる')
                self.populate_ui_data()
                messagebox.showinfo("アーカイブ完了", f"「{current_name}」をアーカイブしました。\n\n「ぎゅるる」に切り替えました。")
            else:
                status = "アーカイブしました" if new_archived else "アーカイブ解除しました"
                messagebox.showinfo("成功", f"「{current_name}」を{status}。")

            print(f"✅ AIキャラアーカイブ切替: {current_name} → archived={new_archived}")
        except Exception as e:
            print(f"❌ アーカイブエラー: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("エラー", f"アーカイブ処理に失敗しました: {e}")

    def _on_delete_character(self):
        """AIキャラを完全削除（Phase 10: アーカイブ済みのみ）"""
        from tkinter import messagebox

        try:
            current_name = self.selected_character_name

            # 「ぎゅるる」は不可
            if current_name == "ぎゅるる":
                messagebox.showwarning("保護されたキャラ", "「ぎゅるる」は削除できません。")
                return

            if current_name not in self.ai_characters:
                messagebox.showwarning("エラー", "選択中のキャラが見つかりません。")
                return

            # アーカイブ済みチェック
            if not self.ai_characters[current_name].get('archived', False):
                messagebox.showwarning(
                    "削除不可",
                    f"「{current_name}」は削除できません。\n\n先に「アーカイブ」してください。"
                )
                return

            # 最終確認（依頼書⑩の必須文言）
            confirm = messagebox.askyesno(
                "完全削除の確認",
                f"AIキャラ「{current_name}」をアーカイブからも削除しますか？\n\nこの操作は取り消せません。",
                icon='warning'
            )

            if not confirm:
                return

            # 完全削除実行
            del self.ai_characters[current_name]
            print(f"🗑️ AIキャラ完全削除: {current_name}")

            # 保存
            self.save_personality_config()

            # 「ぎゅるる」に退避
            self.selected_character_name = 'ぎゅるる'
            if 'ぎゅるる' in self.ai_characters:
                self.character_data = self.ai_characters['ぎゅるる'].copy()
            self.ui_elements['name_var'].set('ぎゅるる')

            # UI更新
            self._refresh_character_dropdown()
            self.populate_ui_data()

            messagebox.showinfo("削除完了", f"「{current_name}」を完全に削除しました。")
            print(f"✅ AIキャラ完全削除完了: {current_name}")

        except Exception as e:
            print(f"❌ 削除エラー: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("エラー", f"削除処理に失敗しました: {e}")

    def cleanup(self):
        """クリーンアップ"""
        print("🔚 クリーンアップ実行")

    # --- Compatibility shims (legacy method names) ---
    def save_character_config(self, *args, **kwargs):
        """旧呼び出し名→新実装へフォワード"""
        return self.save_personality_config()

    def reset_personality_config(self, *args, **kwargs):
        """旧呼び出し名→新実装へフォワード"""
        return self.reset_character_config()

    def test_personality(self, *args, **kwargs):
        """旧呼び出し名→新実装へフォワード"""
        return self.test_character()


# =========================
# タブ作成関数（v17 形式）
# =========================
def create_tab(parent, message_bus=None, config_manager=None, app_instance=None):
    """Notebook から呼ばれるファクトリ"""
    return AICharacterTab(parent, message_bus, config_manager, app_instance)

def create_ai_tab(parent, message_bus=None, config_manager=None, app_instance=None):
    """v17.2生き残り用: メインの規約に合わせた薄いエイリアス。
    既存の create_tab をそのまま呼び出します。"""
    return create_tab(parent, message_bus=message_bus, config_manager=config_manager, app_instance=app_instance)

# 後方互換（旧名）
create_ai_personality_tab = create_tab
create_ai_character_tab = create_tab


# =========================
# スタンドアロン実行
# =========================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 スタンドアロンモード起動")
    print("=" * 60)

    root = tk.Tk()
    root.title("AIキャラ設定タブ - スタンドアロンテスト（ハイブリッド完全版）")
    root.geometry("900x700")
    print("🔧 Tkウィンドウ作成完了")

    class MockMessageBus:
        def subscribe(self, event, callback, owner=None): 
            print(f"📡 MockMessageBus.subscribe: {event}")
        def publish(self, event, data, sender=None): 
            print(f"📤 MockMessageBus.publish: {event}")
        def unsubscribe(self, event, callback): 
            print(f"📡 MockMessageBus.unsubscribe: {event}")

    class MockConfigManager:
        def __init__(self): 
            self.data = {}
        def get(self, key, default=None):
            keys = key.split('.') if isinstance(key, str) else [key]
            value = self.data
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k, default)
                else:
                    return default
            return value if value is not None else default
        def set(self, key, value): 
            print(f"💾 MockConfigManager.set: {key}")
        def save(self): 
            print("💾 MockConfigManager.save")

    try:
        print("🔧 Mock初期化中...")
        mock_bus = MockMessageBus()
        print("✅ MockMessageBus 作成完了")
        mock_config = MockConfigManager()
        print("✅ MockConfigManager 作成完了")

        print("🔧 AICharacterTab 作成中...")
        tab = AICharacterTab(root, mock_bus, mock_config)
        print("✅ AICharacterTab 作成完了")

        print("\n" + "=" * 60)
        print("✅✅✅ スタンドアロン起動成功! ✅✅✅")
        print("=" * 60)
        print("📋 実装済み機能:")
        print("  ✅ 接続ステータス表示")
        print("  ✅ 基本設定タブ（統合版）")
        print("     - AI基本情報")
        print("     - キーワード管理")
        print("     - 応答タイミング設定")
        print("     - 応答動作設定")
        print("  ✅ 応答パターンタブ（5カテゴリ）")
        print("     - ✨ 変数システム完全実装")
        print("     - ✨ 感情変数対応 {emotion}")
        print("     - ✨ ムード変数対応 {mood}")
        print("     - ✨ ドロップダウンメニュー")
        print("     - ✨ プレビュー機能（改善版）")
        print("  ✅ 行動設定タブ（統合版）")
        print("  ✅ 技術設定タブ（プロバイダ設定+接続テスト）")
        print("  ✅ 設定保存/読込機能（ConfigManager対応）")
        print("=" * 60)
        print("🔧 v17形式対応:")
        print("  ✅ create_tab() 関数エクスポート")
        print("  ✅ ドットキー形式の設定取得")
        print("  ✅ Events.TAB_READY 通知")
        print("  ✅ ConfigManager双方向連携")
        print("=" * 60)
        print("✨ ハイブリッド版追加機能:")
        print("  ✅ 感情変数 {emotion} 完全実装")
        print("  ✅ ムード変数 {mood} 完全実装")
        print("  ✅ AI連携機能（双方向通信）")
        print("  ✅ MessageBus堅牢化")
        print("  ✅ 技術設定の保存機能")
        print("  ✅ AI側からのステータス更新受信")
        print("=" * 60)
        print("📊 タブ構成: [基本設定] [応答パターン] [行動設定] [技術設定]")
        print("=" * 60)
        print("\n🎉 GUIを表示します...")

        # 初回ステータス更新
        root.after(500, tab.refresh_status)

        def on_closing():
            print("\n🔚 ウィンドウを閉じています...")
            try:
                tab.cleanup()
            except:
                pass
            root.destroy()
            print("✅ 正常終了")

        root.protocol("WM_DELETE_WINDOW", on_closing)
        print("⏳ メインループ開始...")
        root.mainloop()

    except Exception as e:
        print(f"\n❌❌❌ エラー発生 ❌❌❌")
        print(f"エラー内容: {e}\n\n詳細:")
        traceback.print_exc()
        print("\n" + "=" * 60)
        input("\nEnterキーを押して終了...")

print("\n✅ スクリプト終了")


# =========================
# メイン互換用の空フック
# =========================
def install_ai_tab(notebook=None, message_bus=None, config_manager=None, **kwargs):
    """互換用の空フック。v17.2生き残りでは何もしない。"""
    try:
        # ここで何かする必要があれば将来追記
        return True
    except Exception:
        return False