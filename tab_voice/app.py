#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 音声制御タブ - v17.3 基準版（統合パッチ適用済）
===============================================================
本版のポイント
- 右ペインは「リアルタイムログ」のみ
- 左上枠を「統合・稼働状態」に変更し、〔完全統合/部分統合/不可〕と〔接続中/未接続〕を
  個別カラーで表示。さらに「☑ VoiceManager」を“統合×接続”の複合判定で 緑/橙/赤 に色分け
- ステータス更新は常時自動ポーリング（トグルなし）
- 左側の順序: 統合・稼働状態 → 音量 → エンジン → キャラ選択 → テスト → 高度 → 基本
- テスト再生は現在のエンジン/キャラ/音量を確実に反映。全操作は右ログに出力
- 「キャラ選択」は VOICEVOX /speakers を読み込んでアプリ内ポップアップで選択（失敗時はブラウザへフォールバック）
- 起動時にチェンジログ（前版→現版の変更点）を右ログへ自動出力
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional
import tkinter as tk
from tkinter import ttk, scrolledtext


# ========== Versioning ==========
VERSION = "v17.3-rev2"

# バージョンの並び順（上が古い）
VERSIONS_ORDER = [
    "v17.2",
    "v17.3",
    "v17.3-rev1",
    "v17.3-rev2",   # ← 現在
]

# 各版の主な更新点（右ログへ出す要約）
CHANGELOG = {
    "v17.3": [
        "UI順序を最適化（音量→エンジン→キャラ→テスト→高度→基本）。",
        "右ペインをログ中心に整理、操作ログを統一出力。",
        "テスト再生でエンジン/キャラ/音量を確実に反映。",
    ],
    "v17.3-rev1": [
        "右ペインを完全にログのみへ。",
        "左上を「統合・稼働状態」に変更し、〔完全統合/接続中〕を個別カラー表示。",
        "自動ステータス更新を常時ONに（トグル削除）。",
        "キャラボタン表記を「キャラ選択」に変更、テストメッセージのレイアウト統一。",
    ],
    "v17.3-rev2": [
        "☑ VoiceManager の複合カラー（統合×接続: 緑/橙/赤）。",
        "「キャラ選択」をアプリ内ポップアップ化（JSON取得→一覧→選択）。",
        "状態変化や操作ログの文言を微調整。",
    ],
}

# ===== パス設定（path bootstrap） =====
# tab_voice/app.py から 1 つ上がプロジェクトルート（…/gyururu_bot_v17）
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== ログ設定 =====
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ===== 可用性フラグ =====
EVENTS_AVAILABLE = False
BUS_AVAILABLE = False
VOICE_SINGLETON_AVAILABLE = False
CONFIG_AVAILABLE = False

# ===== Events定義 =====
try:
    from shared.event_types import Events
    EVENTS_AVAILABLE = True
    logger.info("✅ Events利用可能")
except Exception:
    logger.warning("⚠️ Events未利用 - フォールバック使用")
    class Events:
        TAB_READY = "tab_ready"

# ===== MessageBus =====
try:
    from shared.message_bus import get_message_bus
    BUS_AVAILABLE = True
    logger.info("✅ MessageBus利用可能")
except Exception:
    logger.warning("⚠️ MessageBus未利用（簡易Bus）")
    class _MiniBus:
        def __init__(self):
            self._subs: Dict[str, list] = {}
        def _key(self, ev): return ev.name if hasattr(ev, "name") else str(ev)
        def publish(self, ev, data=None, sender=None):
            k = self._key(ev)
            for cb in self._subs.get(k, []):
                try: cb(ev, data, sender=sender)
                except Exception: pass
            return True
        def subscribe(self, ev, cb):
            k = self._key(ev); self._subs.setdefault(k, []).append(cb)
        def unsubscribe(self, ev, cb):
            k = self._key(ev)
            if k in self._subs and cb in self._subs[k]:
                self._subs[k].remove(cb)
    def get_message_bus(): return _MiniBus()

# ===== VoiceManager Singleton =====
get_voice_manager = speak_text = get_voice_status = None
stop_voice_manager = clear_voice_queue = None
try:
    import shared.voice_manager_singleton as vms
    get_voice_manager = getattr(vms, "get_voice_manager", None)
    speak_text = getattr(vms, "speak_text", None)
    get_voice_status = getattr(vms, "get_voice_status", None)
    stop_voice_manager = getattr(vms, "stop_voice_manager", None)
    clear_voice_queue = getattr(vms, "clear_voice_queue", None)
    VOICE_SINGLETON_AVAILABLE = (get_voice_manager is not None and speak_text is not None)
    logger.info("✅ VoiceManager Singleton統合完了" if VOICE_SINGLETON_AVAILABLE else "⚠️ VoiceManager Singleton必須機能不足")
except Exception as e:
    logger.warning(f"⚠️ VoiceManager Singleton利用不可: {e}")

# ===== UI共通ヘルパー =====
try:
    from shared.ui_helpers import apply_statusbar_style
except Exception:
    # フォールバック：共通関数が見つからない場合は何もしない
    def apply_statusbar_style(widget):
        return "#66DD66", "#000000"

# ===== Config =====
try:
    from shared.unified_config_manager import UnifiedConfigManager
    CONFIG_AVAILABLE = True
    logger.info("✅ UnifiedConfigManager利用可能")
except Exception:
    logger.warning("⚠️ Config未利用（簡易Config）")
    class UnifiedConfigManager:
        def __init__(self): self._store: Dict[str, Any] = {}
        def get(self, k, d=None): return self._store.get(k, d)
        def set(self, k, v): self._store[k] = v

# ===== 設定デフォルト =====
DEFAULTS = {
    "auto_status_update": True,  # UIトグルは出さないが常時ON扱い
    "auto_voice_chat": False,    # 本タブではUI提供しない
    "volume_level": 1.0,
    "voice_engine": "voicevox",
    "speaker_id": 46,
    "max_log_lines": 500,
    "update_interval": 2.0,      # 自動更新周期(秒)
}

class VoiceControlTab(ttk.Frame):
    """
    🎤 音声制御タブ - v17.3 基準版
    - 右ペインはログのみ
    - 左上は「統合・稼働状態」：個別ラベル色 + master複合色
    - 自動ステータス更新は常時ON
    - UI順序の最適化
    """
    def __init__(self, parent, message_bus=None, config_manager=None, app_instance=None, shared_volume_var=None, shared_mute_var=None):
        super().__init__(parent)
        self.pack(fill=tk.BOTH, expand=True)

        # 共有
        self.bus = message_bus or get_message_bus()
        self.config = config_manager or UnifiedConfigManager()
        # （修正点A）config_manager 属性を明示的に保持
        if not hasattr(self, "config_manager"):
            self.config_manager = config_manager  # NoneでもOK（互換）
        self.app_instance = app_instance

        # --- 依頼書⑤: 音量・ミュート共有変数を保存 ---
        self._shared_volume_var = shared_volume_var
        self._shared_mute_var = shared_mute_var

        # 状態（voice_managerの重複初期化を削除し、ここで一度だけ初期化）
        self.voice_manager = None
        self.status_job = None
        self.cleaned = False

        self.ns = "voice_control"
        self._ensure_defaults()

        # テストメッセージ
        self.test_messages = [
            "音声テストメッセージです。VoiceManager Singletonが正常に動作しています。",
            "ぎゅるるボット音声制御タブからのテストです。",
            "日本語音声合成の動作確認を行っています。",
            "これは長めのテストメッセージです。複数の文章を含んでいて、音声エンジンの処理能力をテストします。",
            "短いテスト。"
        ]

        logger.info("🎤 音声制御タブ作成開始（v17.3 基準版）")

        self._init_voice_manager()
        self._build_ui()
        self._subscribe_events()
        self._start_auto_status()    # 常時ON
        self._log_version_changes()  # 起動時チェンジログ
        self._publish_ready()

        logger.info("✅ 音声制御タブ作成完了（v17.3 基準版）")

    # ---------- 初期化 ----------
    def _ensure_defaults(self):
        for k, v in DEFAULTS.items():
            key = f"{self.ns}.{k}"
            if self.config.get(key, None) is None:
                self.config.set(key, v)

    def _init_voice_manager(self):
        try:
            if VOICE_SINGLETON_AVAILABLE and get_voice_manager:
                self.voice_manager = get_voice_manager()
                logger.info("🎤 VoiceManager 取得完了")
            else:
                logger.warning("⚠️ VoiceManager 利用不可（UIのみ動作）")
        except Exception as e:
            logger.error(f"❌ VoiceManager初期化エラー: {e}")

    # ---------- UI ----------
    def _build_ui(self):
        main = ttk.Frame(self); main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左: 制御／右: ログのみ（B-1: 大枠タイトルを削除し他タブと統一）
        self.left = ttk.LabelFrame(main, text="", padding=10)
        self.left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        self.right = ttk.LabelFrame(main, text="📝 リアルタイムログ", padding=10)
        self.right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_left_panel()

        self.log_text = scrolledtext.ScrolledText(self.right, wrap=tk.WORD, height=22)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._log("🟢 音声制御タブ 初期化完了 - " + VERSION)

    def _build_left_panel(self):
        # 音声エンジンのマスターリスト（早期初期化）
        self.voice_engines = [
            {"name": "VOICEVOX", "value": "voicevox"},
            {"name": "棒読みちゃん", "value": "bouyomi"},
            {"name": "Windows", "value": "system"},
        ]

        # 0) 統合・稼働状態（B-3/B-4: WebSocketタブと同じスタイルで5項目表示）
        state_frame = ttk.LabelFrame(self.left, text="📡 統合・稼働状態", padding=10)
        state_frame.pack(fill=tk.X, pady=(0, 10))

        # 上段：VoiceManager / 接続エンジン数 / 音声キュー
        row1 = ttk.Frame(state_frame)
        row1.pack(fill=tk.X, pady=(0, 8), anchor="w")

        # VoiceManager
        vm_frame = tk.Frame(row1, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1, width=180, height=28)
        vm_frame.pack(side=tk.LEFT, padx=(0, 10))
        vm_frame.pack_propagate(False)  # 固定サイズを維持
        tk.Label(vm_frame, text="VoiceManager: ", bg="#2b2b2b", fg="white", font=("Arial", 9), anchor="w").pack(side=tk.LEFT, padx=(5, 0), fill=tk.Y)
        self.lbl_vm_status = tk.Label(vm_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"), anchor="w")
        self.lbl_vm_status.pack(side=tk.LEFT, padx=(0, 5), fill=tk.BOTH, expand=True)

        # 接続エンジン数
        engine_frame = tk.Frame(row1, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1, width=180, height=28)
        engine_frame.pack(side=tk.LEFT, padx=(0, 10))
        engine_frame.pack_propagate(False)
        tk.Label(engine_frame, text="接続エンジン数: ", bg="#2b2b2b", fg="white", font=("Arial", 9), anchor="w").pack(side=tk.LEFT, padx=(5, 0), fill=tk.Y)
        self.lbl_engine_count = tk.Label(engine_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"), anchor="w")
        self.lbl_engine_count.pack(side=tk.LEFT, padx=(0, 5), fill=tk.BOTH, expand=True)

        # 音声キュー
        queue_frame = tk.Frame(row1, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1, width=180, height=28)
        queue_frame.pack(side=tk.LEFT, padx=(0, 10))
        queue_frame.pack_propagate(False)
        tk.Label(queue_frame, text="音声キュー: ", bg="#2b2b2b", fg="white", font=("Arial", 9), anchor="w").pack(side=tk.LEFT, padx=(5, 0), fill=tk.Y)
        self.lbl_voice_queue = tk.Label(queue_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"), anchor="w")
        self.lbl_voice_queue.pack(side=tk.LEFT, padx=(0, 5), fill=tk.BOTH, expand=True)

        # 下段：VOICEVOX / 棒読みちゃん / Windows音声
        row2 = ttk.Frame(state_frame)
        row2.pack(fill=tk.X, anchor="w")

        # VOICEVOX
        vvx_frame = tk.Frame(row2, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1, width=180, height=28)
        vvx_frame.pack(side=tk.LEFT, padx=(0, 10))
        vvx_frame.pack_propagate(False)
        tk.Label(vvx_frame, text="VOICEVOX: ", bg="#2b2b2b", fg="white", font=("Arial", 9), anchor="w").pack(side=tk.LEFT, padx=(5, 0), fill=tk.Y)
        self.lbl_voicevox = tk.Label(vvx_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"), anchor="w")
        self.lbl_voicevox.pack(side=tk.LEFT, padx=(0, 5), fill=tk.BOTH, expand=True)

        # 棒読みちゃん
        bou_frame = tk.Frame(row2, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1, width=180, height=28)
        bou_frame.pack(side=tk.LEFT, padx=(0, 10))
        bou_frame.pack_propagate(False)
        tk.Label(bou_frame, text="棒読みちゃん: ", bg="#2b2b2b", fg="white", font=("Arial", 9), anchor="w").pack(side=tk.LEFT, padx=(5, 0), fill=tk.Y)
        self.lbl_bouyomi = tk.Label(bou_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"), anchor="w")
        self.lbl_bouyomi.pack(side=tk.LEFT, padx=(0, 5), fill=tk.BOTH, expand=True)

        # Windows音声
        win_frame = tk.Frame(row2, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1, width=180, height=28)
        win_frame.pack(side=tk.LEFT)
        win_frame.pack_propagate(False)
        tk.Label(win_frame, text="Windows音声: ", bg="#2b2b2b", fg="white", font=("Arial", 9), anchor="w").pack(side=tk.LEFT, padx=(5, 0), fill=tk.Y)
        self.lbl_windows_voice = tk.Label(win_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"), anchor="w")
        self.lbl_windows_voice.pack(side=tk.LEFT, padx=(0, 5), fill=tk.BOTH, expand=True)

        # 1) 音量制御（依頼書⑤: 共有Varと同期）
        vol_frame = ttk.LabelFrame(self.left, text="音量制御", padding=10)
        vol_frame.pack(fill=tk.X, pady=(0, 10))
        rowv = ttk.Frame(vol_frame); rowv.pack(fill=tk.X, pady=5)
        ttk.Label(rowv, text="音量").pack(side=tk.LEFT)

        # 共有Varがあれば初期値を同期、無ければConfigから読み込み
        if self._shared_volume_var is not None:
            initial_volume_pct = self._shared_volume_var.get()
            initial_volume = initial_volume_pct / 100.0
            logger.info(f"✅ 共有音量変数から初期化: {initial_volume_pct}%")
        else:
            initial_volume = float(self.config.get(f"{self.ns}.volume_level", 1.0))
            logger.info(f"⚠️ 共有音量変数未提供、Configから初期化: {int(initial_volume*100)}%")

        self.var_volume = tk.DoubleVar(value=initial_volume)
        vol_scale = ttk.Scale(rowv, from_=0.0, to=2.0, variable=self.var_volume, orient=tk.HORIZONTAL)
        vol_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 10))
        self.lbl_vol = ttk.Label(rowv, text=f"{int(self.var_volume.get()*100)}%")
        self.lbl_vol.pack(side=tk.RIGHT)

        def _on_vol_change(*_):
            v = max(0.0, min(2.0, float(self.var_volume.get())))
            self.config.set(f"{self.ns}.volume_level", v)
            self.lbl_vol.config(text=f"{int(v*100)}%")

            # 共有Varへ同期（無限ループ防止のため値が異なる場合のみ）
            if self._shared_volume_var is not None:
                new_pct = int(v * 100)
                if self._shared_volume_var.get() != new_pct:
                    self._shared_volume_var.set(new_pct)

            self._log(f"🔊 音量 {int(v*100)}%")

        self.var_volume.trace('w', _on_vol_change)

        # 共有Varからの変更を受け取る（AIとチャットタブからの変更を反映）
        if self._shared_volume_var is not None:
            def _on_shared_vol_change(*_):
                new_pct = self._shared_volume_var.get()
                new_val = new_pct / 100.0
                # 無限ループ防止のため値が異なる場合のみ更新
                if abs(self.var_volume.get() - new_val) > 0.001:
                    self.var_volume.set(new_val)
            self._shared_volume_var.trace('w', _on_shared_vol_change)

        # ミュート状態表示（操作UIは置かず、状態表示のみ）
        mute_row = ttk.Frame(vol_frame); mute_row.pack(fill=tk.X, pady=(5, 0))
        self.lbl_mute_status = ttk.Label(mute_row, text="🔊 音声出力：有効")
        self.lbl_mute_status.pack(side=tk.LEFT)

        # 共有Varからのミュート変更を受け取る（AIとチャットタブからの変更を反映）
        if self._shared_mute_var is not None:
            def _on_shared_mute_change(*_):
                muted = bool(self._shared_mute_var.get())
                # VoiceManagerに反映
                if self.voice_manager:
                    try:
                        self.voice_manager.set_mute(muted)
                        logger.info(f"🔇 ミュート状態変更: {'ON' if muted else 'OFF'}")
                    except Exception as e:
                        logger.debug(f"ミュート設定エラー: {e}")
                # 状態表示を更新
                if muted:
                    self.lbl_mute_status.config(text="🔇 音声出力：ミュート中（AIとチャットタブで操作）")
                else:
                    self.lbl_mute_status.config(text="🔊 音声出力：有効")
                self._log(f"🔇 ミュート: {'ON' if muted else 'OFF'}")
            self._shared_mute_var.trace('w', _on_shared_mute_change)
            # 初期状態を反映
            _on_shared_mute_change()

        # 2) 読み上げキャラ（C-6〜C-9: ロール別キャラ選択UI）
        role_frame = ttk.LabelFrame(self.left, text="読み上げキャラ", padding=10)
        role_frame.pack(fill=tk.X, pady=(0, 10))

        # ヘッダー行：ラベル + 配信者 + AIキャラ + 視聴者
        header = ttk.Frame(role_frame)
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="", width=14).pack(side=tk.LEFT)  # 左端の空白
        ttk.Label(header, text="配信者", width=25, anchor="center").pack(side=tk.LEFT, padx=2)
        ttk.Label(header, text="AIキャラ", width=25, anchor="center").pack(side=tk.LEFT, padx=2)
        ttk.Label(header, text="視聴者", width=25, anchor="center").pack(side=tk.LEFT, padx=2)

        # 1行目：音声エンジン選択
        engine_row = ttk.Frame(role_frame)
        engine_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(engine_row, text="音声エンジン", width=14).pack(side=tk.LEFT)

        # 配信者エンジン
        streamer_engine_value = self.config.get("voice.role.streamer.engine", "voicevox")
        streamer_engine_name = self._engine_value_to_name(streamer_engine_value)
        self.var_streamer_engine = tk.StringVar(value=streamer_engine_name)
        cmb_streamer_engine = ttk.Combobox(engine_row, textvariable=self.var_streamer_engine,
                                           values=["VOICEVOX", "Windows"], state="readonly", width=25)
        cmb_streamer_engine.pack(side=tk.LEFT, padx=2)
        cmb_streamer_engine.bind("<<ComboboxSelected>>", lambda e: self._on_role_engine_change("streamer"))

        # AIキャラエンジン
        ai_engine_value = self.config.get("voice.role.ai.engine", "voicevox")
        ai_engine_name = self._engine_value_to_name(ai_engine_value)
        self.var_ai_engine = tk.StringVar(value=ai_engine_name)
        cmb_ai_engine = ttk.Combobox(engine_row, textvariable=self.var_ai_engine,
                                     values=["VOICEVOX", "Windows"], state="readonly", width=25)
        cmb_ai_engine.pack(side=tk.LEFT, padx=2)
        cmb_ai_engine.bind("<<ComboboxSelected>>", lambda e: self._on_role_engine_change("ai"))

        # 視聴者エンジン
        viewer_engine_value = self.config.get("voice.role.viewer.engine", "voicevox")
        viewer_engine_name = self._engine_value_to_name(viewer_engine_value)
        self.var_viewer_engine = tk.StringVar(value=viewer_engine_name)
        cmb_viewer_engine = ttk.Combobox(engine_row, textvariable=self.var_viewer_engine,
                                         values=["VOICEVOX", "Windows"], state="readonly", width=25)
        cmb_viewer_engine.pack(side=tk.LEFT, padx=2)
        cmb_viewer_engine.bind("<<ComboboxSelected>>", lambda e: self._on_role_engine_change("viewer"))

        # 2行目：読み上げキャラ選択
        char_row = ttk.Frame(role_frame)
        char_row.pack(fill=tk.X)
        ttk.Label(char_row, text="読み上げキャラ", width=14).pack(side=tk.LEFT)

        # 配信者キャラ
        self.var_streamer_char = tk.StringVar()
        self.cmb_streamer_char = ttk.Combobox(char_row, textvariable=self.var_streamer_char,
                                              state="readonly", width=25)
        self.cmb_streamer_char.pack(side=tk.LEFT, padx=2)
        self.cmb_streamer_char.bind("<<ComboboxSelected>>", lambda e: self._on_role_char_change("streamer"))

        # AIキャラキャラ
        self.var_ai_char = tk.StringVar()
        self.cmb_ai_char = ttk.Combobox(char_row, textvariable=self.var_ai_char,
                                        state="readonly", width=25)
        self.cmb_ai_char.pack(side=tk.LEFT, padx=2)
        self.cmb_ai_char.bind("<<ComboboxSelected>>", lambda e: self._on_role_char_change("ai"))

        # 視聴者キャラ
        self.var_viewer_char = tk.StringVar()
        self.cmb_viewer_char = ttk.Combobox(char_row, textvariable=self.var_viewer_char,
                                            state="readonly", width=25)
        self.cmb_viewer_char.pack(side=tk.LEFT, padx=2)
        self.cmb_viewer_char.bind("<<ComboboxSelected>>", lambda e: self._on_role_char_change("viewer"))

        # キャラデータ読み込み＆UI初期化
        self._load_default_speakers()
        self._load_bouyomi_voices()  # 棒読みちゃん音声リスト
        self._update_role_speakers()

        # 3) フォールバック順序
        fallback_frame = ttk.LabelFrame(self.left, text="フォールバック順序", padding=10)
        fallback_frame.pack(fill=tk.X, pady=(0, 10))

        # 音声エンジン行
        engine_row = ttk.Frame(fallback_frame)
        engine_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(engine_row, text="音声エンジン", width=14).pack(side=tk.LEFT)

        # エンジン①（初期値を表示名に変換）
        engine1_value = self.config.get("voice.fallback.engine1", "voicevox")
        engine1_name = next((e["name"] for e in self.voice_engines if e["value"] == engine1_value), "VOICEVOX")
        self.var_fallback_engine1 = tk.StringVar(value=engine1_name)
        self.cmb_fallback_engine1 = ttk.Combobox(
            engine_row, textvariable=self.var_fallback_engine1,
            values=[e["name"] for e in self.voice_engines[:2]],  # VOICEVOX, 棒読みちゃん
            state="readonly", width=25
        )
        self.cmb_fallback_engine1.pack(side=tk.LEFT, padx=(0, 5))
        self.cmb_fallback_engine1.bind("<<ComboboxSelected>>", self._on_fallback_engine1_change)

        ttk.Label(engine_row, text="⇨").pack(side=tk.LEFT, padx=(0, 5))

        # エンジン②（初期値を表示名に変換）
        engine2_value = self.config.get("voice.fallback.engine2", "system")
        engine2_name = next((e["name"] for e in self.voice_engines if e["value"] == engine2_value), "Windows")
        self.var_fallback_engine2 = tk.StringVar(value=engine2_name)
        self.cmb_fallback_engine2 = ttk.Combobox(
            engine_row, textvariable=self.var_fallback_engine2,
            values=[],  # 動的に更新
            state="readonly", width=25
        )
        self.cmb_fallback_engine2.pack(side=tk.LEFT, padx=(0, 5))
        self.cmb_fallback_engine2.bind("<<ComboboxSelected>>", self._on_fallback_engine2_change)

        ttk.Label(engine_row, text="⇨").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(engine_row, text="Windows", width=10).pack(side=tk.LEFT)

        # 読み上げキャラ行
        char_row = ttk.Frame(fallback_frame)
        char_row.pack(fill=tk.X)
        ttk.Label(char_row, text="読み上げキャラ", width=14).pack(side=tk.LEFT)

        # キャラ①
        self.var_fallback_char1 = tk.StringVar()
        self.cmb_fallback_char1 = ttk.Combobox(
            char_row, textvariable=self.var_fallback_char1,
            state="readonly", width=25
        )
        self.cmb_fallback_char1.pack(side=tk.LEFT, padx=(0, 5))
        self.cmb_fallback_char1.bind("<<ComboboxSelected>>", self._on_fallback_char1_change)

        ttk.Label(char_row, text="⇨").pack(side=tk.LEFT, padx=(0, 5))

        # キャラ②
        self.var_fallback_char2 = tk.StringVar()
        self.cmb_fallback_char2 = ttk.Combobox(
            char_row, textvariable=self.var_fallback_char2,
            state="readonly", width=25
        )
        self.cmb_fallback_char2.pack(side=tk.LEFT, padx=(0, 5))
        self.cmb_fallback_char2.bind("<<ComboboxSelected>>", self._on_fallback_char2_change)

        # 初期化
        self._update_fallback_engine2_list()
        self._update_fallback_char_lists()

        # 4) テストメッセージ（統一レイアウト）
        test_frame = ttk.LabelFrame(self.left, text="テストメッセージ", padding=10)
        test_frame.pack(fill=tk.X, pady=(0, 10))
        r1 = ttk.Frame(test_frame); r1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r1, text="プリセット", width=14).pack(side=tk.LEFT)
        self.var_test = tk.StringVar(value=self.test_messages[0])
        cmb_test = ttk.Combobox(r1, textvariable=self.var_test, values=self.test_messages, width=56)
        cmb_test.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(r1, text="🎵 再生", command=self._play_selected).pack(side=tk.RIGHT)

        r2 = ttk.Frame(test_frame); r2.pack(fill=tk.X)
        ttk.Label(r2, text="カスタム", width=14).pack(side=tk.LEFT)
        self.var_custom = tk.StringVar()
        ent_custom = ttk.Entry(r2, textvariable=self.var_custom)
        ent_custom.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(r2, text="🎵 再生", command=self._play_custom).pack(side=tk.RIGHT)

        # 注意書き
        note_row = ttk.Frame(test_frame); note_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(note_row, text="", width=14).pack(side=tk.LEFT)  # スペーサー
        note_label = ttk.Label(note_row, text="※ テスト再生は上記「フォールバック順序」の設定を使用します",
                               foreground="#888888", font=("Arial", 8))
        note_label.pack(side=tk.LEFT)

        # 5) 高度テスト
        adv_frame = ttk.LabelFrame(self.left, text="高度テスト", padding=10)
        adv_frame.pack(fill=tk.X, pady=(0, 10))
        ra = ttk.Frame(adv_frame); ra.pack(fill=tk.X)
        ttk.Button(ra, text="🔄 連続テスト", command=self._run_batch).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(ra, text="⚡ 負荷テスト", command=self._run_load).pack(side=tk.LEFT)

        # 6) 基本制御（保存・読み込み・更新・停止・キュークリア）
        btn_row = ttk.Frame(self.left)
        btn_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_row, text="💾 保存", command=self._save_config).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="📂 読み込み", command=self._load_config).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="🔄 音声エンジンの更新", command=self._refresh_engines).pack(side=tk.LEFT, padx=(0, 6))
        self.btn_stop = ttk.Button(btn_row, text="⏸ 停止", command=self._stop,
                                   state=("normal" if stop_voice_manager else "disabled"))
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_clear = ttk.Button(btn_row, text="🗑 キュークリア", command=self._clear,
                                    state=("normal" if clear_voice_queue else "disabled"))
        self.btn_clear.pack(side=tk.LEFT)

    # ---------- 右ログ ----------
    def _log(self, s: str):
        if not hasattr(self, "log_text"): return
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {s}\n"
        try:
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self._trim_logs()
        except Exception:
            pass

    def _trim_logs(self):
        try:
            max_lines = int(self.config.get(f"{self.ns}.max_log_lines", 500) or 500)
        except Exception:
            max_lines = 500
        try:
            content = self.log_text.get("1.0", "end-1c")
            lines = content.splitlines()
            if len(lines) > max_lines:
                keep = lines[-max_lines:]
                self.log_text.delete("1.0", "end")
                self.log_text.insert("end", "\n".join(keep) + "\n")
                self.log_text.see("end")
        except Exception:
            pass

    # ---------- フォールバック順序 ----------
    def _update_fallback_engine2_list(self):
        """エンジン①の選択に応じてエンジン②のリストを更新"""
        try:
            engine1 = self.var_fallback_engine1.get()
            # エンジン①で選択されたものを除外
            available = [e["name"] for e in self.voice_engines if e["name"] != engine1]
            self.cmb_fallback_engine2['values'] = available

            # 現在の選択が利用不可になった場合はリセット
            current = self.var_fallback_engine2.get()
            if current not in available and available:
                self.var_fallback_engine2.set(available[0])
                self.config.set("voice.fallback.engine2", self._engine_name_to_value(available[0]))
        except Exception as e:
            logger.error(f"❌ エンジン②リスト更新エラー: {e}")

    def _update_fallback_char_lists(self):
        """エンジンに応じてキャラリストを更新"""
        try:
            # エンジン①のキャラリスト
            engine1_value = self._engine_name_to_value(self.var_fallback_engine1.get())
            if engine1_value == "voicevox":
                # UI表示：ID抜きのラベルのみ
                char1_list = [self._speaker_display_to_label(sp["display"]) for sp in self.voicevox_speakers]
                self.cmb_fallback_char1['values'] = char1_list
                self.cmb_fallback_char1['state'] = 'readonly'
                # 保存されたIDから復元
                saved_id = self.config.get("voice.fallback.char1_id", 46)
                for sp in self.voicevox_speakers:
                    if sp["id"] == saved_id:
                        self.var_fallback_char1.set(self._speaker_display_to_label(sp["display"]))
                        break
            elif engine1_value == "bouyomi":
                char1_list = [v["display"] for v in self.bouyomi_voices]
                self.cmb_fallback_char1['values'] = char1_list
                self.cmb_fallback_char1['state'] = 'readonly'
                # 保存されたIDから復元
                saved_id = self.config.get("voice.fallback.char1_id", 0)
                for v in self.bouyomi_voices:
                    if v["id"] == saved_id:
                        self.var_fallback_char1.set(v["display"])
                        break
                else:
                    self.var_fallback_char1.set(char1_list[0] if char1_list else "女性1")
            else:
                self.cmb_fallback_char1['values'] = ['（Windows標準音声）']
                self.var_fallback_char1.set('（Windows標準音声）')
                self.cmb_fallback_char1['state'] = 'disabled'

            # エンジン②のキャラリスト
            engine2_value = self._engine_name_to_value(self.var_fallback_engine2.get())
            if engine2_value == "voicevox":
                # UI表示：ID抜きのラベルのみ
                char2_list = [self._speaker_display_to_label(sp["display"]) for sp in self.voicevox_speakers]
                self.cmb_fallback_char2['values'] = char2_list
                self.cmb_fallback_char2['state'] = 'readonly'
                saved_id = self.config.get("voice.fallback.char2_id", 3)
                for sp in self.voicevox_speakers:
                    if sp["id"] == saved_id:
                        self.var_fallback_char2.set(self._speaker_display_to_label(sp["display"]))
                        break
            elif engine2_value == "bouyomi":
                char2_list = [v["display"] for v in self.bouyomi_voices]
                self.cmb_fallback_char2['values'] = char2_list
                self.cmb_fallback_char2['state'] = 'readonly'
                saved_id = self.config.get("voice.fallback.char2_id", 0)
                for v in self.bouyomi_voices:
                    if v["id"] == saved_id:
                        self.var_fallback_char2.set(v["display"])
                        break
                else:
                    self.var_fallback_char2.set(char2_list[0] if char2_list else "女性1")
            else:
                self.cmb_fallback_char2['values'] = ['（Windows標準音声）']
                self.var_fallback_char2.set('（Windows標準音声）')
                self.cmb_fallback_char2['state'] = 'disabled'
        except Exception as e:
            logger.error(f"❌ キャラリスト更新エラー: {e}")

    def _current_engine(self) -> str:
        """現在選択中のエンジンの内部値を返す（フォールバックエンジン1）"""
        engine_name = self.var_fallback_engine1.get()
        return self._engine_name_to_value(engine_name)

    def _engine_name_to_value(self, name: str) -> str:
        """エンジン名からvalueに変換"""
        for e in self.voice_engines:
            if e["name"] == name:
                return e["value"]
        return "system"

    def _engine_value_to_name(self, value: str) -> str:
        """エンジンvalueから表示名に変換"""
        for e in self.voice_engines:
            if e["value"] == value:
                return e["name"]
        return "Windows"

    def _speaker_display_to_label(self, display: str) -> str:
        """
        VOICEVOXリストの display（"キャラ名 - ID:46"）から、
        UI表示用のラベル（"キャラ名"）だけを取り出す。

        Args:
            display: "ずんだもん(ノーマル) - ID:3" 形式の文字列

        Returns:
            "ずんだもん(ノーマル)" のようなラベル（ID部分除去）
        """
        if " - ID:" in display:
            return display.split(" - ID:")[0].strip()
        return display.strip()

    def _speaker_label_to_id(self, label: str):
        """
        UIに表示しているラベルから、対応する VOICEVOX speaker_id を逆引きする。

        Args:
            label: "ずんだもん(ノーマル)" のようなラベル

        Returns:
            speaker_id (int) または None（見つからない場合）
        """
        for sp in self.voicevox_speakers:
            if self._speaker_display_to_label(sp["display"]) == label:
                return sp["id"]
        return None

    def _on_fallback_engine1_change(self, event=None):
        """エンジン①変更時"""
        try:
            engine = self._engine_name_to_value(self.var_fallback_engine1.get())
            self.config.set("voice.fallback.engine1", engine)
            self._update_fallback_engine2_list()
            self._update_fallback_char_lists()
            self._log(f"🎤 フォールバックエンジン① → {self.var_fallback_engine1.get()}")
        except Exception as e:
            logger.error(f"❌ エンジン①変更エラー: {e}")

    def _on_fallback_engine2_change(self, event=None):
        """エンジン②変更時"""
        try:
            engine = self._engine_name_to_value(self.var_fallback_engine2.get())
            self.config.set("voice.fallback.engine2", engine)
            self._update_fallback_char_lists()
            self._log(f"🎤 フォールバックエンジン② → {self.var_fallback_engine2.get()}")
        except Exception as e:
            logger.error(f"❌ エンジン②変更エラー: {e}")

    def _on_fallback_char1_change(self, event=None):
        """キャラ①変更時"""
        try:
            char_label = self.var_fallback_char1.get()
            engine_value = self._engine_name_to_value(self.var_fallback_engine1.get())

            if engine_value == "voicevox":
                # ラベルからspeaker_idを逆引き
                speaker_id = self._speaker_label_to_id(char_label)
                if speaker_id is not None:
                    self.config.set("voice.fallback.char1_id", speaker_id)
                    self._log(f"🎭 フォールバックキャラ① → {char_label}")
            elif engine_value == "bouyomi":
                # 棒読みちゃんの場合、表示名からIDを取得
                for v in self.bouyomi_voices:
                    if v["display"] == char_label:
                        self.config.set("voice.fallback.char1_id", v["id"])
                        self._log(f"🎭 フォールバックキャラ① → {char_label} (ID:{v['id']})")
                        break
        except Exception as e:
            logger.error(f"❌ キャラ①変更エラー: {e}")

    def _on_fallback_char2_change(self, event=None):
        """キャラ②変更時"""
        try:
            char_label = self.var_fallback_char2.get()
            engine_value = self._engine_name_to_value(self.var_fallback_engine2.get())

            if engine_value == "voicevox":
                # ラベルからspeaker_idを逆引き
                speaker_id = self._speaker_label_to_id(char_label)
                if speaker_id is not None:
                    self.config.set("voice.fallback.char2_id", speaker_id)
                    self._log(f"🎭 フォールバックキャラ② → {char_label}")
            elif engine_value == "bouyomi":
                # 棒読みちゃんの場合、表示名からIDを取得
                for v in self.bouyomi_voices:
                    if v["display"] == char_label:
                        self.config.set("voice.fallback.char2_id", v["id"])
                        self._log(f"🎭 フォールバックキャラ② → {char_label} (ID:{v['id']})")
                        break
        except Exception as e:
            logger.error(f"❌ キャラ②変更エラー: {e}")

    # ---------- 設定管理 ----------
    def _save_config(self):
        """設定を unified_config.json に保存"""
        try:
            if self.config:
                self.config.save()
                self._log("💾 設定を unified_config.json に保存しました")
        except Exception as e:
            self._log(f"❌ 設定保存エラー: {e}")
            logger.error(f"❌ 設定保存エラー: {e}", exc_info=True)

    def _load_config(self):
        """設定を unified_config.json から読み込み"""
        try:
            if self.config:
                self.config.load()
                self._reload_ui_from_config()
                self._log("📂 設定を unified_config.json から読み込みました")
        except Exception as e:
            self._log(f"❌ 設定読み込みエラー: {e}")
            logger.error(f"❌ 設定読み込みエラー: {e}", exc_info=True)

    def _reload_ui_from_config(self):
        """設定からUIを再読み込み"""
        try:
            # 音量
            vol = float(self.config.get(f"{self.ns}.volume_level", 1.0))
            self.var_volume.set(vol)

            # フォールバックエンジン
            engine1 = self.config.get("voice.fallback.engine1", "voicevox")
            engine2 = self.config.get("voice.fallback.engine2", "system")
            for e in self.voice_engines:
                if e["value"] == engine1:
                    self.var_fallback_engine1.set(e["name"])
                if e["value"] == engine2:
                    self.var_fallback_engine2.set(e["name"])

            self._update_fallback_engine2_list()
            self._update_fallback_char_lists()
            self._update_role_speakers()

            self._log("✅ UI設定を反映しました")
        except Exception as e:
            logger.error(f"❌ UI再読み込みエラー: {e}")

    # ---------- エンジン・キャラ ----------
    def _is_voicevox_available(self) -> bool:
        """VOICEVOX利用可否を判定"""
        if self.voice_manager:
            return self.voice_manager.engines.get("voicevox", {}).get("available", False)
        return False

    def _is_bouyomi_available(self) -> bool:
        """棒読みちゃん利用可否を判定"""
        if self.voice_manager:
            return self.voice_manager.engines.get("bouyomi", {}).get("available", False)
        return False

    def _load_default_speakers(self):
        """VOICEVOXキャラ一覧をロード（APIから全キャラ取得を試行）"""
        # まずVOICEVOX APIから全キャラを取得
        try:
            import requests
            r = requests.get("http://localhost:50021/speakers", timeout=3)
            r.raise_for_status()
            data = r.json()

            speakers = []
            for sp in data:
                sp_name = sp.get("name", "Unknown")
                for st in sp.get("styles", []):
                    st_name = st.get("name", "")
                    sid = st.get("id")
                    disp = f"{sp_name}({st_name}) - ID:{sid}"
                    speakers.append({"display": disp, "id": sid})

            if speakers:
                self.voicevox_speakers = speakers
                self._log(f"✅ VOICEVOX全キャラ読み込み: {len(speakers)}キャラ")
                return
        except Exception as e:
            self._log(f"⚠️ VOICEVOX API未接続、デフォルトキャラを使用")

        # APIが使えない場合はデフォルトの10キャラ
        self.voicevox_speakers = [
            {"display": "四国めたん(ノーマル) - ID:2", "id": 2},
            {"display": "ずんだもん(ノーマル) - ID:3", "id": 3},
            {"display": "春日部つむぎ(ノーマル) - ID:8", "id": 8},
            {"display": "雨晴はう(ノーマル) - ID:10", "id": 10},
            {"display": "波音リツ(ノーマル) - ID:9", "id": 9},
            {"display": "玄野武宏(ノーマル) - ID:11", "id": 11},
            {"display": "白上虎太郎(ふつう) - ID:12", "id": 12},
            {"display": "青山龍星(ノーマル) - ID:13", "id": 13},
            {"display": "冥鳴ひまり(ノーマル) - ID:14", "id": 14},
            {"display": "ショウ(ノーマル) - ID:46", "id": 46},
        ]

    def _load_bouyomi_voices(self):
        """棒読みちゃんの音声リストを定義"""
        self.bouyomi_voices = [
            {"display": "女性1", "id": 0},
            {"display": "女性2", "id": 1},
            {"display": "男性1", "id": 2},
            {"display": "男性2", "id": 3},
            {"display": "中性", "id": 4},
            {"display": "ロボット", "id": 5},
            {"display": "機械1", "id": 6},
            {"display": "機械2", "id": 7},
        ]

    def _on_role_engine_change(self, role: str):
        """ロール別エンジン変更ハンドラ（C-7）"""
        try:
            engine_name = getattr(self, f"var_{role}_engine").get()
            engine_value = self._engine_name_to_value(engine_name)
            self.config.set(f"voice.role.{role}.engine", engine_value)
            self._update_role_speaker_combo(role)
            self._log(f"🎵 {role}のエンジンを変更: {engine_name}")
        except Exception as e:
            self._log(f"❌ {role}エンジン変更エラー: {e}")
            logger.error(f"❌ {role}エンジン変更エラー: {e}", exc_info=True)

    def _on_role_char_change(self, role: str):
        """ロール別キャラ変更ハンドラ（C-8）"""
        try:
            char_label = getattr(self, f"var_{role}_char").get()
            # ラベルからspeaker_idを逆引き
            speaker_id = self._speaker_label_to_id(char_label)
            if speaker_id is not None:
                self.config.set(f"voice.role.{role}.speaker_id", speaker_id)
                self._log(f"🎭 {role}のキャラを変更: {char_label}")
            else:
                self._log(f"⚠️ {role}のキャラ選択: IDが見つかりません")
        except Exception as e:
            self._log(f"❌ {role}キャラ変更エラー: {e}")
            logger.error(f"❌ {role}キャラ変更エラー: {e}", exc_info=True)

    def _update_role_speakers(self):
        """全ロールのキャラコンボボックスを更新（C-9）"""
        for role in ["streamer", "ai", "viewer"]:
            self._update_role_speaker_combo(role)

    def _update_role_speaker_combo(self, role: str):
        """指定ロールのキャラコンボボックスを更新"""
        try:
            engine = self.config.get(f"voice.role.{role}.engine", "voicevox")
            cmb = getattr(self, f"cmb_{role}_char")
            var = getattr(self, f"var_{role}_char")

            if engine == "voicevox":
                # VOICEVOXキャラ一覧を設定（UI表示：ID抜きのラベルのみ）
                cmb['values'] = [self._speaker_display_to_label(sp["display"]) for sp in self.voicevox_speakers]
                cmb['state'] = 'readonly'

                # 保存されたspeaker_idから初期値を設定
                saved_id = self.config.get(f"voice.role.{role}.speaker_id", None)
                if saved_id is not None:
                    for sp in self.voicevox_speakers:
                        if sp["id"] == saved_id:
                            var.set(self._speaker_display_to_label(sp["display"]))
                            break
                else:
                    # 未設定の場合はデフォルト（ID:46 = ショウ）
                    for sp in self.voicevox_speakers:
                        if sp["id"] == 46:
                            var.set(self._speaker_display_to_label(sp["display"]))
                            break
            else:
                # OS TTS選択時
                cmb['values'] = ['（Windows標準音声）']
                cmb.set('（Windows標準音声）')
                cmb['state'] = 'disabled'
        except Exception as e:
            self._log(f"❌ {role}キャラUI更新エラー: {e}")
            logger.error(f"❌ {role}キャラUI更新エラー: {e}", exc_info=True)

    def _refresh_engines(self):
        """音声エンジンの再検出（E-1）"""
        try:
            self._log("🔄 音声エンジンを再検出中...")
            if self.voice_manager:
                # VoiceManagerのエンジン検出を実行
                self.voice_manager._detect_engines()

                # 検出結果をログに出力
                vvx_available = self.voice_manager.engines.get("voicevox", {}).get("available", False)
                os_tts_available = self.voice_manager.engines.get("os_tts", {}).get("available", False)

                if vvx_available:
                    self._log("✅ VOICEVOX: 検出成功")
                else:
                    self._log("⚠️ VOICEVOX: 未検出")

                if os_tts_available:
                    self._log("✅ Windows音声: 利用可能")
                else:
                    self._log("⚠️ Windows音声: 利用不可")

                # 統合・稼働状態パネルを即座に更新
                self._refresh_integration_panel()
                self._log("✅ 音声エンジンの再検出完了")
            else:
                self._log("⚠️ VoiceManagerが初期化されていません")
        except Exception as e:
            self._log(f"❌ 音声エンジン再検出エラー: {e}")
            logger.error(f"❌ 音声エンジン再検出エラー: {e}", exc_info=True)

    def _open_speakers_page(self):
        """キャラ検索ポップアップ（VOICEVOX /speakers を読み込み、アプリ内で選択）"""
        try:
            import requests
            r = requests.get("http://localhost:50021/speakers", timeout=3)
            r.raise_for_status()
            data = r.json()  # [{"name":..., "styles":[{"name":..., "id":...}, ...]}, ...]
            flat = []
            for sp in data:
                sp_name = sp.get("name", "Unknown")
                for st in sp.get("styles", []):
                    st_name = st.get("name", "")
                    sid = st.get("id")
                    disp = f"{sp_name}({st_name}) - ID:{sid}"
                    flat.append((disp, sid))
            if not flat:
                raise RuntimeError("キャラデータが空です")

            # ポップアップUI
            win = tk.Toplevel(self)
            win.title("キャラ検索")
            win.geometry("520x420")
            win.transient(self.winfo_toplevel())
            win.grab_set()

            frm = ttk.Frame(win, padding=10); frm.pack(fill=tk.BOTH, expand=True)
            qvar = tk.StringVar()
            ent = ttk.Entry(frm, textvariable=qvar); ent.pack(fill=tk.X, pady=(0, 6))
            lst = tk.Listbox(frm, height=16); lst.pack(fill=tk.BOTH, expand=True)

            full_items = [d for d in flat]
            def refresh_list():
                q = (qvar.get() or "").strip().lower()
                lst.delete(0, "end")
                for disp, sid in full_items:
                    if (not q) or (q in disp.lower()):
                        lst.insert("end", disp)
            def apply_selection(evt=None):
                try:
                    idx = lst.curselection()
                    if not idx: return
                    disp = lst.get(idx[0])
                    self.var_speaker_disp.set(disp)
                    sid = int(disp.split("ID:")[-1])
                    self.config.set(f"{self.ns}.speaker_id", sid)
                    self._log(f"🔎 キャラ選択: {disp}")
                    win.destroy()
                except Exception as e:
                    self._log(f"⚠️ キャラ反映エラー: {e}")

            btns = ttk.Frame(frm); btns.pack(fill=tk.X, pady=(6, 0))
            ttk.Button(btns, text="決定", command=apply_selection).pack(side=tk.RIGHT)
            ttk.Button(btns, text="閉じる", command=win.destroy).pack(side=tk.RIGHT, padx=6)

            lst.bind("<Double-Button-1>", apply_selection)
            qvar.trace_add("write", lambda *_: refresh_list())
            refresh_list(); ent.focus_set()

        except Exception:
            # フォールバック：ブラウザで開く
            try:
                import webbrowser
                webbrowser.open("http://localhost:50021/speakers")
                self._log("🔎 キャラ検索: /speakers をブラウザで開きました（フォールバック）")
            except Exception:
                self._log("⚠️ キャラ検索に失敗しました")

    # ---------- 再生・テスト ----------
    def _get_fallback_priority_char(self):
        """フォールバック順序の最優先キャラを取得（左から有効なもの）"""
        # エンジン①が利用可能か確認
        engine1_value = self._engine_name_to_value(self.var_fallback_engine1.get())
        engine1_available = False

        if engine1_value == "voicevox":
            engine1_available = self._is_voicevox_available()
        elif engine1_value == "bouyomi":
            engine1_available = self._is_bouyomi_available()
        else:  # system
            engine1_available = True  # Windows音声は常に利用可能

        if engine1_available:
            char_disp = self.var_fallback_char1.get()

            # VOICEVOXは表示文字列より「保存済みID」を優先（UI表示形式に依存しない）
            if engine1_value == "voicevox":
                saved_id = self.config.get("voice.fallback.char1_id", 0)
                try:
                    saved_id = int(saved_id)
                except Exception:
                    saved_id = 0
                logger.debug(f"🔎 フォールバック①: config保存ID={saved_id} (表示={char_disp})")
                return engine1_value, saved_id, char_disp

            return engine1_value, self._get_char_id_from_display(char_disp, engine1_value), char_disp

        # エンジン①が利用不可の場合、エンジン②を試す
        engine2_value = self._engine_name_to_value(self.var_fallback_engine2.get())
        char_disp = self.var_fallback_char2.get()

        if engine2_value == "voicevox":
            saved_id = self.config.get("voice.fallback.char2_id", 0)
            try:
                saved_id = int(saved_id)
            except Exception:
                saved_id = 0
            logger.debug(f"🔎 フォールバック②: config保存ID={saved_id} (表示={char_disp})")
            return engine2_value, saved_id, char_disp

        return engine2_value, self._get_char_id_from_display(char_disp, engine2_value), char_disp

    def _get_char_id_from_display(self, display: str, engine: str):
        """表示名からキャラIDを取得"""
        if engine == "voicevox":
            # 旧形式: "～ - ID:123" にも対応
            if "ID:" in display:
                return int(display.split("ID:")[-1])

            # 現行UI形式: ID抜きラベル → 逆引きしてspeaker_idを取得
            sid = self._speaker_label_to_id(display)
            return int(sid) if sid is not None else 0

        elif engine == "bouyomi":
            for v in self.bouyomi_voices:
                if v["display"] == display:
                    return v["id"]
            return 0

        else:  # system
            return 0

    def _play_selected(self):
        """プリセットメッセージをフォールバック順序の最優先キャラで再生"""
        text = (self.var_test.get() or "").strip()
        if text:
            engine, speaker_id, char_disp = self._get_fallback_priority_char()
            self._speak_with_fallback(text, engine, speaker_id, char_disp, label="プリセット")

    def _play_custom(self):
        """カスタムメッセージをフォールバック順序の最優先キャラで再生"""
        text = (self.var_custom.get() or "").strip()
        if text:
            engine, speaker_id, char_disp = self._get_fallback_priority_char()
            self._speak_with_fallback(text, engine, speaker_id, char_disp, label="カスタム")

    def _speak_with_fallback(self, text: str, engine: str, speaker_id: int, char_disp: str, label: str = ""):
        """フォールバック順序に基づいて音声再生"""
        vol = float(self.config.get(f"{self.ns}.volume_level", 1.0) or 1.0)

        tag = f"[{label}]" if label else ""
        self._log(f"▶️ 再生{tag} engine={engine} char={char_disp} (ID:{speaker_id}) volume={int(vol*100)}%")

        if not speak_text:
            self._log("❌ speak_text が利用できません")
            return

        try:
            speak_text(text, username="VoiceControl", speaker_id=speaker_id, volume=vol)
            self._log(f"✅ 再生成功: {char_disp}")
        except TypeError as e:
            self._log(f"⚠️ TypeError発生、互換フォールバック: {e}")
            try:
                speak_text(text)
            except Exception as e:
                self._log(f"❌ 再生エラー: {e}")
        except Exception as e:
            self._log(f"❌ 再生エラー: {e}")

    def _speak(self, text: str):
        """シンプルなテキスト読み上げ（デフォルトパラメータ使用）"""
        if not speak_text:
            self._log("❌ speak_text が利用できません")
            return
        try:
            vol = float(self.config.get(f"{self.ns}.volume_level", 1.0) or 1.0)
            speak_text(text, username="VoiceControl", volume=vol)
        except Exception as e:
            self._log(f"❌ 再生エラー: {e}")

    def _speak_with_speaker(self, text: str, speaker_id: int, speaker_name: str = ""):
        """
        指定したキャラIDで音声を再生する（ランダムテスト用）

        Args:
            text: 読み上げテキスト
            speaker_id: VOICEVOXキャラID
            speaker_name: キャラ名（ログ表示用）
        """
        engine = self._current_engine()
        vol = float(self.config.get(f"{self.ns}.volume_level", 1.0) or 1.0)

        tag = f"[{speaker_name}]" if speaker_name else f"[ID:{speaker_id}]"
        self._log(f"▶️ 再生{tag} engine={engine} speaker_id={speaker_id} volume={int(vol*100)}%")

        if not speak_text:
            self._log("❌ speak_text が利用できません"); return
        try:
            # ✅ v17.5.x 修正: speaker_id と volume を正しく渡す
            speak_text(text, username="VoiceControl", speaker_id=speaker_id, volume=vol)
            self._log(f"✅ 再生成功: speaker_id={speaker_id}, volume={int(vol*100)}%")
        except TypeError as e:
            self._log(f"⚠️ TypeError発生、互換フォールバック: {e}")
            try: speak_text(text)   # 互換フォールバック
            except Exception as e: self._log(f"❌ 再生エラー: {e}")
        except Exception as e:
            self._log(f"❌ 再生エラー: {e}")

    def _run_batch(self):
        def worker():
            try:
                n, itv = 5, 0.7
                self._log(f"🔄 連続テスト開始: {n}回 / {itv}s（全エンジンからランダムキャラ）")
                import random

                # 接続中の全エンジンのキャラを収集
                all_speakers = []
                if self._is_voicevox_available() and self.voicevox_speakers:
                    for sp in self.voicevox_speakers:
                        all_speakers.append({"engine": "voicevox", "id": sp["id"], "name": sp["display"]})
                if self._is_bouyomi_available() and hasattr(self, "bouyomi_voices"):
                    for bv in self.bouyomi_voices:
                        all_speakers.append({"engine": "bouyomi", "id": bv["id"], "name": bv["display"]})
                # Windows音声は常に利用可能
                all_speakers.append({"engine": "system", "id": 0, "name": "Windows音声"})

                for i in range(n):
                    if all_speakers:
                        speaker = random.choice(all_speakers)
                        self._speak_with_speaker(f"テスト {i+1} 回目", speaker["id"], speaker["name"])
                    else:
                        self._speak(f"テスト {i+1} 回目")
                    time.sleep(itv)
                self._log("✅ 連続テスト完了")
            except Exception as e:
                self._log(f"❌ 連続テストエラー: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _run_load(self):
        def worker():
            try:
                n = 10
                self._log(f"⚡ 負荷テスト開始: 並列 {n} 発話（全エンジンからランダムキャラ）")
                import random

                # 接続中の全エンジンのキャラを収集
                all_speakers = []
                if self._is_voicevox_available() and self.voicevox_speakers:
                    for sp in self.voicevox_speakers:
                        all_speakers.append({"engine": "voicevox", "id": sp["id"], "name": sp["display"]})
                if self._is_bouyomi_available() and hasattr(self, "bouyomi_voices"):
                    for bv in self.bouyomi_voices:
                        all_speakers.append({"engine": "bouyomi", "id": bv["id"], "name": bv["display"]})
                # Windows音声は常に利用可能
                all_speakers.append({"engine": "system", "id": 0, "name": "Windows音声"})

                ths = []
                for i in range(n):
                    if all_speakers:
                        speaker = random.choice(all_speakers)
                        t = threading.Thread(
                            target=self._speak_with_speaker,
                            args=(f"負荷テスト {i+1}", speaker["id"], speaker["name"]),
                            daemon=True
                        )
                    else:
                        t = threading.Thread(target=self._speak, args=(f"負荷テスト {i+1}",), daemon=True)
                    t.start(); ths.append(t)
                    time.sleep(0.05)
                for t in ths: t.join(timeout=0.2)
                self._log("✅ 負荷テスト完了")
            except Exception as e:
                self._log(f"❌ 負荷テストエラー: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        if stop_voice_manager:
            try: stop_voice_manager(); self._log("⏸ 再生停止")
            except Exception as e: self._log(f"❌ 停止エラー: {e}")

    def _clear(self):
        if clear_voice_queue:
            try: clear_voice_queue(); self._log("🗑 キュークリア")
            except Exception as e: self._log(f"❌ キュークリアエラー: {e}")

    # ---------- 自動ステータス ----------
    def _start_auto_status(self):
        self._schedule_status()

    def _schedule_status(self):
        try:
            interval = float(self.config.get(f"{self.ns}.update_interval", 2.0) or 2.0)
        except Exception:
            interval = 2.0
        if self.status_job:
            try: self.after_cancel(self.status_job)
            except Exception: pass
        self.status_job = self.after(int(interval*1000), self._tick_status)

    def _tick_status(self):
        """定期的に統合・稼働状態パネルを更新（B-3/B-4）"""
        try:
            self._refresh_integration_panel()
        except Exception as e:
            logger.error(f"❌ ステータス更新エラー: {e}")
        finally:
            self._schedule_status()

    def _refresh_integration_panel(self):
        """5項目の統合・稼働状態を更新（B-3/B-4）"""
        # 1) VoiceManager統合状態の判定
        if VOICE_SINGLETON_AVAILABLE:
            missing = []
            if get_voice_status is None: missing.append("status")
            if stop_voice_manager is None: missing.append("stop")
            if clear_voice_queue is None: missing.append("clear")
            integration = "完全統合" if not missing else "部分統合"
        else:
            integration = "利用不可"

        vm_color = {"完全統合": "#90EE90", "部分統合": "#FFA500", "利用不可": "#FF4444"}.get(integration, "#FFD700")
        self.lbl_vm_status.config(text=integration, fg=vm_color)

        # 2) 接続エンジン数の判定
        engine_count = 0
        if self.voice_manager:
            try:
                if self.voice_manager.engines.get("voicevox", {}).get("available", False):
                    engine_count += 1
                if self.voice_manager.engines.get("bouyomi", {}).get("available", False):
                    engine_count += 1
                if self.voice_manager.engines.get("os_tts", {}).get("available", False):
                    engine_count += 1
                # Fallbackは常に利用可能なので、最低1個は保証される
                if engine_count == 0:
                    engine_count = 1  # Fallbackのみ
            except Exception:
                engine_count = 0

        engine_color = "#90EE90" if engine_count >= 2 else "#FFA500" if engine_count == 1 else "#FF4444"
        self.lbl_engine_count.config(text=f"{engine_count}個", fg=engine_color)

        # 3) Windows音声（OS TTS）の判定
        windows_available = False
        if self.voice_manager:
            try:
                windows_available = self.voice_manager.engines.get("os_tts", {}).get("available", False)
            except Exception:
                pass

        windows_text = "✅ 利用可能" if windows_available else "❌ 利用不可"
        windows_color = "#90EE90" if windows_available else "#FF4444"
        self.lbl_windows_voice.config(text=windows_text, fg=windows_color)

        # 4) VOICEVOX接続状態
        vvx_available = False
        if self.voice_manager:
            try:
                vvx_available = self.voice_manager.engines.get("voicevox", {}).get("available", False)
            except Exception:
                pass

        if vvx_available:
            vvx_text = "✅ 接続中"
            vvx_color = "#90EE90"
        else:
            vvx_text = "❌ 未検出"
            vvx_color = "#FF4444"
        self.lbl_voicevox.config(text=vvx_text, fg=vvx_color)

        # 5) 棒読みちゃん接続状態
        bou_available = False
        if self.voice_manager:
            try:
                bou_available = self.voice_manager.engines.get("bouyomi", {}).get("available", False)
            except Exception:
                pass

        if bou_available:
            bou_text = "✅ 接続中"
            bou_color = "#90EE90"
        else:
            bou_text = "❌ 未検出"
            bou_color = "#FF4444"
        self.lbl_bouyomi.config(text=bou_text, fg=bou_color)

        # 6) 音声キューの待ち件数
        queue_size = 0
        if self.voice_manager:
            try:
                queue_size = self.voice_manager.voice_queue.qsize()
            except Exception:
                pass

        if queue_size == 0:
            queue_text = "待ちなし"
            queue_color = "#FFFFFF"
        else:
            queue_text = f"待ち: {queue_size}件"
            queue_color = "#FFA500"
        self.lbl_voice_queue.config(text=queue_text, fg=queue_color)

    # ---------- Bus / READY ----------
    def _subscribe_events(self):
        """
        Voiceタブで必要なイベント購読をまとめて登録

        ❌ v17.3.1: AI_RESPONSE 購読を無効化
        - VOICE_REQUEST は AIIntegrationManager が一元発行
        - tab_voice は直接 AI_RESPONSE を購読しない
        """
        try:
            # ❌ v17.3.1: AI_RESPONSE 購読を無効化（二重読み上げ防止）
            # self.bus.subscribe("AI_RESPONSE", self._on_ai_response_for_speak)
            logger.info("📡 AI_RESPONSE 購読は無効化されています（v17.3.1）")
        except Exception as e:
            logger.warning(f"⚠️ subscribe 失敗: {e}")

    def _on_ai_response_for_speak(self, data, sender=None):
        """
        AI応答テキストを即時に読み上げ（既定ON）。Configの 'voice.auto_speak_ai' が False ならスキップ。
        """
        try:
            # 追加: トグル判定
            auto = True
            try:
                if hasattr(self, "config_manager") and self.config_manager:
                    auto = bool(self.config_manager.get("voice.auto_speak_ai", True))
            except Exception:
                auto = True
            if not auto:
                return

            text = (data or {}).get("text", "")
            if not text:
                return
            if speak_text:
                speak_text(text)
                self._log(f"🎵 読み上げ: {text[:40]}...")
            else:
                self._log("⚠️ speak_text が利用できません（VoiceManager未統合）")
        except Exception as e:
            self._log(f"❌ 読み上げエラー: {e}")


    def _publish_ready(self):
        try:
            if self.bus:
                self.bus.publish(Events.TAB_READY, {'tab': 'voice_control', 'status': 'ready'}, sender='tab_voice')
        except Exception:
            pass

    # ---------- チェンジログ ----------
    def _log_version_changes(self):
        """前回起動バージョンとの差分をログに出し、現在版を保存"""
        try:
            last_key = f"{self.ns}.last_version"
            prev = self.config.get(last_key, None)
            cur = VERSION
            def idx(v): return VERSIONS_ORDER.index(v) if v in VERSIONS_ORDER else -1

            if prev is None:
                self._log(f"📦 新規導入: {cur}")
                if cur in CHANGELOG:
                    for line in CHANGELOG[cur]:
                        self._log(f"• {line}")
            else:
                if prev == cur:
                    self._log(f"ℹ️ バージョン: {cur}（変更点なし）")
                else:
                    self._log(f"⬆️ 更新検出: {prev} → {cur}")
                    p_i, c_i = idx(prev), idx(cur)
                    if p_i != -1 and c_i != -1 and c_i >= p_i:
                        for v in VERSIONS_ORDER[p_i+1:c_i+1]:
                            if v in CHANGELOG:
                                self._log(f"— {v} の更新点 —")
                                for line in CHANGELOG[v]:
                                    self._log(f"• {line}")
                    else:
                        if cur in CHANGELOG:
                            self._log(f"— {cur} の更新点 —")
                            for line in CHANGELOG[cur]:
                                self._log(f"• {line}")
            self.config.set(last_key, cur)
        except Exception as e:
            self._log(f"⚠️ バージョン履歴の記録に失敗: {e}")

    # ---------- クリーンアップ ----------
    def cleanup(self):
        if self.cleaned: return
        self.cleaned = True
        try:
            if self.status_job: self.after_cancel(self.status_job)
        except Exception:
            pass

# ===== スタンドアロン起動 =====
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Voice Control Tab (v17.3 基準版)")
    app = VoiceControlTab(root)
    def _on_close():
        try: app.cleanup()
        except Exception: pass
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()

# ===== Factory exports for main integration =====

def create_voice_tab(parent, message_bus=None, config_manager=None, app_instance=None, shared_volume_var=None, shared_mute_var=None, **kwargs):
    """
    推奨: メインから呼ばれるタブ生成ファクトリ
    依頼書⑤: 共有Var対応
    """
    return VoiceControlTab(
        parent,
        message_bus=message_bus,
        config_manager=config_manager,
        app_instance=app_instance,
        shared_volume_var=shared_volume_var,
        shared_mute_var=shared_mute_var
    )

# 後方互換エイリアス
create_tab = create_voice_tab
VoiceTab = VoiceControlTab

# 明示エクスポート
__all__ = [
    "VoiceControlTab",
    "VoiceTab",
    "create_voice_tab",
    "create_tab",
]
