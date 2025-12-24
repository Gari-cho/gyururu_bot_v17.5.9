#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==========================================================
# 🧩 Gyururu Bot File Metadata
# ==========================================================
# 作成日時: 2025-11-08
# 対応バージョン: v17.5.9
# ディレクトリ / ファイル名: main_v17_5_9.py
# ファイルの役割:
#   ぎゅるるボット v17.5.9 メインアプリケーション
#   クリーン・統合版（AIIntegrationManager直接使用）
#
# 主な更新内容:
#   - シグネチャ自動判別機能追加（_sigsafe_call）
#   - VoiceChain/ChatHandler呼び出しを例外ログなしに変更
#   - 引数不一致でも必ず正しい形で呼べるように修正
#
# 注意事項:
#   - inspect.signatureで動的に引数判別
#   - TypeError例外を完全に回避
#   - 既存の動作を維持しつつ安全性を向上
#
# 作者 / 編集者: ガリガリマッチョ💪😉
# Build Tag: GYM-2025C
# ==========================================================
"""
ぎゅるるボット v17.5.9 — メイン（クリーン・統合版）
--------------------------------------------------
• 古いパッチローダー（ai_integration_complete_patch.py）を完全削除
• AIIntegrationManager を直接利用する構成に統一
• v17.5.9 導線ルールに準拠した最小限かつ安全な実装

※ v17.5.9 標準メインとして扱う想定。
"""

from __future__ import annotations

import os
import sys
import traceback
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Optional, Any, Dict, Callable
from typing import Any, Optional
import subprocess

import logging
import inspect

# ==========================================================
# 🔧 sys.path 調整（プロジェクト直下からの起動を前提）
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ==========================================================
# 🌱 .env / 環境変数ロード
# ==========================================================
try:
    from dotenv import load_dotenv

    ENV_LOADED = load_dotenv(os.path.join(BASE_DIR, ".env"))
except Exception:
    ENV_LOADED = False

# ==========================================================
# 📦 共有モジュールの読み込み
# ==========================================================
try:
    from shared.message_bus import MessageBus

except Exception as e:
    print(f"[FATAL] shared.message_bus の読み込みに失敗しました: {e}")
    raise

try:
    from shared.unified_config_manager import UnifiedConfigManager, get_config_manager
except Exception as e:
    print(f"[FATAL] shared.unified_config_manager の読み込みに失敗しました: {e}")
    raise

try:
    from shared.logger import get_logger, setup_quiet_logging
except Exception:
    # 最低限の logger フォールバック
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

    def setup_quiet_logging(default_level: str = "INFO") -> None:
        logging.getLogger().setLevel(
            getattr(logging, default_level.upper(), logging.INFO)
        )

# グローバルロガー
logger = get_logger("gyururu_main_v17_3")

# ==========================================================
# 🛡️ グローバル例外フック（起動時の例外を確実にログに記録）
# ==========================================================
def _install_global_excepthook():
    """
    GUI起動中にどこかで落ちたときも、必ずログに残すためのフック。
    未捕捉の例外をキャッチして、ログに出力する。
    """
    def _handle_exception(exc_type, exc_value, exc_tb):
        # CTRL+C はスルー（任意）
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        logger.critical("💥 未捕捉例外が発生しました（アプリが異常終了します）", exc_info=(exc_type, exc_value, exc_tb))

        # 念のためコンソールにも出す
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle_exception

# ==========================================================
# 📁 作業ディレクトリをスクリプトのあるフォルダに固定（相対パス対策）
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(BASE_DIR)
    logger.info(f"📂 作業ディレクトリを BASE_DIR に変更しました: {BASE_DIR}")
except Exception as e:
    logger.warning(f"⚠️ 作業ディレクトリ変更に失敗しました: {e}")

# ==========================================================
# 🧠 AI 統合マネージャ読み込み
# ==========================================================
AI_MANAGER_IMPORT_OK = False
AIIntegrationManager = None

try:
    from ai_integration_manager import AIIntegrationManager as _AIIntegrationManager

    AIIntegrationManager = _AIIntegrationManager
    AI_MANAGER_IMPORT_OK = True
    logger.info("🧠 AIIntegrationManager 読み込み成功 (v17.3)")
except Exception as e:
    logger.warning(f"AIIntegrationManager読み込み失敗: {e}")

# ChatHandler（v17.5 以降は正式に未使用）
# v17.3 導線ルールブックでは「ChatHandler は使わない」前提のため、
# オプション機能として静かにスタブにフォールバックする。
CHAT_HANDLER_AVAILABLE = False
attach_chat_consumer = None  # type: ignore
detach_chat_consumer = None  # type: ignore

try:
    from chat_handler import attach_chat_consumer, detach_chat_consumer

    CHAT_HANDLER_AVAILABLE = True
    # v17.5: 警告なしで静かに成功（存在する場合のみ）
except Exception:
    # v17.5: 存在しない場合はスタブで代替（警告なし）
    CHAT_HANDLER_AVAILABLE = False
    # スタブ関数（呼ばれても何もしない）
    def attach_chat_consumer(*args, **kwargs):  # type: ignore
        """v17.5 以降では未使用のスタブ。呼ばれても何もしない。"""
        pass

    def detach_chat_consumer(*args, **kwargs):  # type: ignore
        """v17.5 以降では未使用のスタブ。呼ばれても何もしない。"""
        pass

# VoiceChain bootstrap（AI/音声連携の最小回路）
VOICECHAIN_AVAILABLE = False
bootstrap_voice_chain = None  # type: ignore

try:
    from bootstrap_voice_chain import bootstrap_voice_chain as _bootstrap_voice_chain

    VOICECHAIN_AVAILABLE = True
    bootstrap_voice_chain = _bootstrap_voice_chain
    logger.info("🔗 VoiceChain Bootstrap OK")
except Exception as e:
    VOICECHAIN_AVAILABLE = False
    logger.warning(f"VoiceChain Bootstrap利用不可: {e}")

# ==========================================================
# 🧠 シグネチャ安全呼び出しユーティリティ
# ==========================================================
def _sigsafe_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    与えられた関数のシグネチャを調べ、
    渡された引数の中から「使える分だけ」を選んで安全に呼び出す。

    - 余分なキーワード引数で TypeError が出るのを防ぐ
    - 位置引数はそのまま使い、足りない分は無視（デフォルトを利用）
    """
    if func is None:
        return None

    try:
        sig = inspect.signature(func)
    except Exception:
        # シグネチャ取得に失敗した場合は、そのまま呼ぶ
        return func(*args, **kwargs)

    # 位置引数はそのまま通す（足りない分はデフォルトで処理される前提）
    bound_args = []
    for i, a in enumerate(args):
        bound_args.append(a)

    # 使えるキーワードだけ抽出
    accepted_kwargs: Dict[str, Any] = {}
    for name, p in sig.parameters.items():
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,):
            continue
        if name in kwargs:
            accepted_kwargs[name] = kwargs[name]

    try:
        return func(*bound_args, **accepted_kwargs)
    except TypeError:
        # 万一ここでも TypeError が出たら、最後のフォールバックとして
        # 「位置引数のみ」で呼んでみる（logger など付けるだけのケースを想定）
        try:
            return func(*bound_args)
        except Exception:
            # それでもダメなら諦める
            raise


# ==========================================================
# 🧱 アプリ設定用データクラス
# ==========================================================
@dataclass
class AppConfig:
    title: str = "ぎゅるるボット v17.5.9 - Stream Nexus"
    width: int = 1200
    height: int = 800


# ==========================================================
# 🧩 タブコンテナ（Notebook）
# ==========================================================
class GyururuTabContainer(ttk.Notebook):
    def __init__(self, master: tk.Widget, message_bus: MessageBus, config_manager: UnifiedConfigManager, **kwargs: Any):
        super().__init__(master, **kwargs)

        # Notebook（タブ）文字を太字＋少しサイズUP（全タブ共通）
        style = ttk.Style()
        TAB_FONT_FAMILY = "Segoe UI"   # Windows前提。環境により自動フォールバックされます
        TAB_FONT_SIZE = 12             # ← 大きすぎたため調整（元は14）

        style.configure(
            "TNotebook.Tab",
            font=(TAB_FONT_FAMILY, TAB_FONT_SIZE, "bold"),
            padding=(12, 6)  # (左右, 上下) クリックしやすく
        )

        # 選択中タブだけ少し強調（テーマにより効かない場合あり：効かなければ無視でOK）
        style.map(
            "TNotebook.Tab",
            padding=[("selected", (14, 8)), ("!selected", (12, 6))]
        )

        self.message_bus = message_bus
        self.config_manager = config_manager
        self._tabs: Dict[str, tk.Frame] = {}

        # --- 依頼書⑤: 音量・ミュート共有変数（タブ間で完全同期） ---
        self.shared_volume_var = tk.IntVar(value=80)  # 0〜200%（音声制御タブと統一）
        self.shared_mute_var = tk.BooleanVar(value=False)

        # 各タブの生成
        self._create_tabs()

    # --------------------------------------------------
    # 🧱 各タブ生成
    # --------------------------------------------------
    def _create_tabs(self) -> None:
        """
        v17.3 基本タブ構成:
          1. WebSocket 管理       (tab_websocket)
          2. AIとチャット         (tab_chat)
          3. 音声制御             (tab_voice)
          4. 配信者設定           (tab_streamer_profile)
          5. AIキャラ設定         (tab_ai_unified)
          6. OBS演出効果         (tab_obs_effects)
          7. 設定管理             (tab_settings)
        """

        # 1. WebSocket 管理タブ
        if create_websocket_tab is not None:
            ws_frame = ttk.Frame(self)
            self.add(ws_frame, text="📡 WebSocket")
            self._tabs["websocket"] = ws_frame
            try:
                _sigsafe_call(
                    create_websocket_tab,
                    ws_frame,
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                )
            except Exception as e:
                logger.error(f"❌ WebSocketタブ初期化エラー: {e}", exc_info=True)
                for child in ws_frame.winfo_children():
                    child.destroy()
                ttk.Label(
                    ws_frame,
                    text="WebSocketタブ初期化に失敗しました",
                ).pack(padx=8, pady=8)
        else:
            frame = ttk.Frame(self)
            self.add(frame, text="📡 WebSocket(読み込み失敗)")
            ttk.Label(
                frame,
                text="WebSocketタブが読み込めませんでした",
            ).pack(padx=8, pady=8)

        # 2. AIとチャットタブ
        if CHAT_TAB_AVAILABLE and create_chat_tab is not None:
            chat_frame = ttk.Frame(self)
            self.add(chat_frame, text="💬 AIとチャット")
            self._tabs["chat"] = chat_frame
            try:
                # v17.3 正式シグネチャ: (parent, message_bus, config_manager, app_instance=None)
                # 依頼書⑤: 音量・ミュート共有変数を注入
                _sigsafe_call(
                    create_chat_tab,
                    chat_frame,
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                    app_instance=self,
                    shared_volume_var=self.shared_volume_var,
                    shared_mute_var=self.shared_mute_var,
                )
            except Exception as e:
                logger.error(f"❌ Chatタブ初期化エラー: {e}", exc_info=True)
                for child in chat_frame.winfo_children():
                    child.destroy()
                ttk.Label(
                    chat_frame,
                    text="Chatタブ初期化中にエラーが発生しました",
                ).pack(padx=8, pady=8)
        else:
            frame = ttk.Frame(self)
            self.add(frame, text="💬 AIとチャット(読み込み失敗)")
            ttk.Label(
                frame,
                text="AIとチャットタブが読み込めませんでした",
            ).pack(padx=8, pady=8)

        # 3. 音声制御タブ
        if "create_voice_tab" in globals() and create_voice_tab is not None:
            voice_frame = ttk.Frame(self)
            self.add(voice_frame, text="🎤 音声制御")
            self._tabs["voice"] = voice_frame
            try:
                # 依頼書⑤: 音量・ミュート共有変数を注入
                _sigsafe_call(
                    create_voice_tab,
                    voice_frame,
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                    app_instance=None,
                    shared_volume_var=self.shared_volume_var,
                    shared_mute_var=self.shared_mute_var,
                )
            except Exception as e:
                logger.error(f"❌ 音声制御タブ初期化エラー: {e}", exc_info=True)
                for child in voice_frame.winfo_children():
                    child.destroy()
                ttk.Label(
                    voice_frame,
                    text="音声制御タブ初期化中にエラーが発生しました",
                ).pack(padx=8, pady=8)
        else:
            frame = ttk.Frame(self)
            self.add(frame, text="🎤 音声制御(読み込み失敗)")
            ttk.Label(
                frame,
                text="音声制御タブが読み込めませんでした",
            ).pack(padx=8, pady=8)

        # 4. 配信者設定タブ
        if "create_streamer_profile_tab" in globals() and create_streamer_profile_tab is not None:
            streamer_frame = ttk.Frame(self)
            self.add(streamer_frame, text="🎬 配信者設定")
            self._tabs["streamer"] = streamer_frame
            try:
                _sigsafe_call(
                    create_streamer_profile_tab,
                    streamer_frame,
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                )
            except Exception as e:
                logger.error(f"❌ 配信者設定タブ初期化エラー: {e}", exc_info=True)
                for child in streamer_frame.winfo_children():
                    child.destroy()
                ttk.Label(
                    streamer_frame,
                    text="配信者設定タブ初期化中にエラーが発生しました",
                ).pack(padx=8, pady=8)
        else:
            frame = ttk.Frame(self)
            self.add(frame, text="🎬 配信者設定(読み込み失敗)")
            ttk.Label(
                frame,
                text="配信者設定タブが読み込めませんでした",
            ).pack(padx=8, pady=8)

        # 5. AIキャラ設定タブ（ai_unified）
        if "create_ai_unified_tab" in globals() and create_ai_unified_tab is not None:
            aiu_frame = ttk.Frame(self)
            self.add(aiu_frame, text="🤖 AIキャラ設定")
            self._tabs["ai_unified"] = aiu_frame
            try:
                _sigsafe_call(
                    create_ai_unified_tab,
                    aiu_frame,
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                )
            except Exception as e:
                logger.error(f"❌ AIキャラ設定タブ初期化エラー: {e}", exc_info=True)
                for child in aiu_frame.winfo_children():
                    child.destroy()
                ttk.Label(
                    aiu_frame,
                    text="AIキャラ設定タブ初期化中にエラーが発生しました",
                ).pack(padx=8, pady=8)
        else:
            frame = ttk.Frame(self)
            self.add(frame, text="🤖 AIキャラ設定(読み込み失敗)")
            ttk.Label(
                frame,
                text="AIキャラ設定タブが読み込めませんでした",
            ).pack(padx=8, pady=8)

        # 6. OBS演出効果タブ
        if "create_obs_effects_tab" in globals() and create_obs_effects_tab is not None:
            obs_frame = ttk.Frame(self)
            self.add(obs_frame, text="📺 OBS演出")
            self._tabs["obs_effects"] = obs_frame
            try:
                _sigsafe_call(
                    create_obs_effects_tab,
                    obs_frame,
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                )
            except Exception as e:
                logger.error(f"❌ OBS演出タブ初期化エラー: {e}", exc_info=True)
                for child in obs_frame.winfo_children():
                    child.destroy()
                ttk.Label(
                    obs_frame,
                    text="OBS演出タブ初期化中にエラーが発生しました",
                ).pack(padx=8, pady=8)
        else:
            frame = ttk.Frame(self)
            self.add(frame, text="📺 OBS演出(読み込み失敗)")
            ttk.Label(
                frame,
                text="OBS演出効果タブが読み込めませんでした",
            ).pack(padx=8, pady=8)

        # 7. 設定管理タブ
        if "create_settings_tab" in globals() and create_settings_tab is not None:
            settings_frame = ttk.Frame(self)
            self.add(settings_frame, text="⚙️ 設定管理")
            self._tabs["settings"] = settings_frame
            try:
                _sigsafe_call(
                    create_settings_tab,
                    settings_frame,
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                )
            except Exception as e:
                logger.error(f"❌ 設定管理タブ初期化エラー: {e}", exc_info=True)
                for child in settings_frame.winfo_children():
                    child.destroy()
                ttk.Label(
                    settings_frame,
                    text="設定管理タブ初期化中にエラーが発生しました",
                ).pack(padx=8, pady=8)
        else:
            frame = ttk.Frame(self)
            self.add(frame, text="⚙️ 設定管理(読み込み失敗)")
            ttk.Label(
                frame,
                text="設定管理タブが読み込めませんでした",
            ).pack(padx=8, pady=8)

# ==========================================================
# 🎤 音声系・タブ系モジュール
# ==========================================================
# 0. VoiceManager Singleton（補助：メイン側からの利用）
try:
    from shared.voice_manager_singleton import get_voice_manager
except Exception as e:
    logger.warning(f"VoiceManager Singleton読み込み失敗: {e}")
    get_voice_manager = None  # type: ignore

# ① WebSocketタブ
try:
    from tab_websocket.app import create_websocket_tab
except Exception as e:
    logger.warning(f"WebSocketタブ読み込み失敗: {e}")
    create_websocket_tab = None  # type: ignore

# ② AIとチャットタブ
try:
    from tab_chat.app import create_tab as create_chat_tab
    CHAT_TAB_AVAILABLE = True
except Exception as e:
    create_chat_tab = None
    CHAT_TAB_AVAILABLE = False
    logger.warning(f"⚠️ tab_chat.create_tab 読み込み失敗（継続可）: {e}")

# ③ 音声制御タブ（tab_voice）
try:
    from tab_voice.app import create_tab as create_voice_tab
    VOICE_TAB_AVAILABLE = True
except Exception as e:
    create_voice_tab = None
    VOICE_TAB_AVAILABLE = False
    logger.warning(f"⚠️ tab_voice.create_tab 読み込み失敗（継続可）: {e}")

# ④ 配信者設定タブ
try:
    from tab_streamer_profile.app import create_streamer_profile_tab
    STREAMER_TAB_AVAILABLE = True
except Exception as e:
    create_streamer_profile_tab = None
    STREAMER_TAB_AVAILABLE = False
    logger.warning(f"⚠️ 配信者設定タブ読み込み失敗（継続可）: {e}")

# ⑤ AIキャラ設定タブ（ai_unified）
AI_UNIFIED_IMPORT_OK = False
install_ai_tab = None  # type: ignore
try:
    from tab_ai_unified.app import install_ai_tab as _install_ai_tab
    from tab_ai_unified.app import create_tab as create_ai_unified_tab

    install_ai_tab = _install_ai_tab
    AI_UNIFIED_IMPORT_OK = True
    logger.info("🧩 ai_unified: install_ai_tab フック検出")
except Exception as e:
    create_ai_unified_tab = None  # type: ignore
    logger.warning(f"ai_unified 読み込み失敗: {e}")

# ⑥ OBS演出効果タブ
try:
    from tab_obs_effects.app import create_obs_effects_tab
    OBS_TAB_AVAILABLE = True
except Exception as e:
    create_obs_effects_tab = None
    OBS_TAB_AVAILABLE = False
    logger.warning(f"⚠️ OBSエフェクトタブ読み込み失敗（継続可）: {e}")

# ⑦ 設定管理タブ
try:
    from tab_settings.app import create_settings_tab
    SETTINGS_TAB_AVAILABLE = True
except Exception as e:
    create_settings_tab = None
    SETTINGS_TAB_AVAILABLE = False
    logger.warning(f"⚠️ 設定管理タブ読み込み失敗（継続可）: {e}")

# ==========================================================
# 🎛 メインアプリケーションクラス
# ==========================================================
class GyururuMainApp:
    def __init__(self, root: tk.Tk, config: Optional[AppConfig] = None):
        self.root = root
        self.config = config or AppConfig()
        self.root.title(self.config.title)
        self.running = False

        logger.info("🔧 1/7 ログ設定開始")
        # --------------------------------------------------
        # 🔇 ログ静音（必要以上にログを出さない）
        # --------------------------------------------------
        try:
            setup_quiet_logging(default_level=os.getenv("GYURURU_LOG_LEVEL", "INFO"))
            logger.info("✅ 1/7 ログ設定完了")
        except Exception as e:
            logger.warning(f"logging setup skipped: {e}")

        logger.info("🔧 2/7 MessageBus / ConfigManager 初期化開始")
        # --------------------------------------------------
        # 📡 MessageBus / ConfigManager
        # --------------------------------------------------
        # v17.3 ではシンプルにローカル MessageBus を生成
        self.message_bus: MessageBus = MessageBus()

        try:
            self.config_manager: UnifiedConfigManager = get_config_manager()
        except Exception:
            # フォールバック（単体起動など）
            self.config_manager = UnifiedConfigManager()
        logger.info("✅ 2/7 MessageBus / ConfigManager 初期化完了")

        logger.info("🔧 3/7 VoiceManager 初期化開始")
        # --------------------------------------------------
        # 🎤 VoiceManager
        # --------------------------------------------------
        self.voice_manager = None
        if get_voice_manager is not None:
            try:
                # v17.3 標準: message_bus と config_manager を渡す
                self.voice_manager = get_voice_manager(
                    message_bus=self.message_bus,
                    config_manager=self.config_manager,
                )
                logger.info("✅ 3/7 VoiceManager 初期化完了")
            except TypeError:
                # 古い引数パターンにも対応
                self.voice_manager = _sigsafe_call(
                    get_voice_manager,
                    self.message_bus,
                )
                logger.info("✅ 3/7 VoiceManager 初期化完了 (fallback)")
            except Exception as e:
                logger.error(f"❌ VoiceManager初期化エラー: {e}", exc_info=True)
                logger.info("⚠️ VoiceManager なしで続行します")
        else:
            logger.info("⚠️ 3/7 VoiceManager 利用不可（スキップ）")

        logger.info("🔧 4/7 AIIntegrationManager 初期化開始")
        # --------------------------------------------------
        # 🧠 AI統合マネージャ（v17.3 正式構文）
        # --------------------------------------------------
        self.ai_manager = None
        self.ai_connector = None

        if AI_MANAGER_IMPORT_OK and AIIntegrationManager is not None:
            try:
                # 👉 v17.3.1: message_bus と config_manager を明示的に渡す
                self.ai_manager = AIIntegrationManager(
                    message_bus=self.message_bus,
                    config_manager=self.config_manager
                )
                logger.info("✅ 4/7 AIIntegrationManager 初期化完了")
            except Exception as e:
                logger.error(f"❌ AIIntegrationManager初期化失敗: {e}", exc_info=True)
                self.ai_manager = None
                logger.info("⚠️ AIIntegrationManager なしで続行します")
        else:
            logger.info("⚠️ 4/7 AIIntegrationManager 利用不可（スキップ）")

        # Chatタブなどから参照する共通AIコネクタとして共有
        self.ai_connector = self.ai_manager

        # 起動直後に確定ステータスを配信（AI_STATUS / AI_STATUS_UPDATE）
        if self.ai_manager and hasattr(self.ai_manager, "start"):
            try:
                self.ai_manager.start()
                logger.info("🚀 AIIntegrationManager.start() 呼び出し完了")
            except Exception as e:
                logger.warning(f"⚠️ AIIntegrationManager.start() でエラー: {e}")

        logger.info("🔧 5/7 メインウィンドウ構築開始")
        # --------------------------------------------------
        # 🎛 メインUI（Notebook）
        # --------------------------------------------------
        self._setup_main_window()
        logger.info("✅ 5/7 メインウィンドウ構築完了")

        logger.info("🔧 6/7 タブ構築開始")
        self._setup_tabs()
        logger.info("✅ 6/7 タブ構築完了")

        logger.info("🔧 7/7 最終初期化（VoiceChain / BouyomiBridge）開始")
        # --------------------------------------------------
        # 🔗 VoiceChain / ChatHandler 連携（最小回路）
        # --------------------------------------------------
        self._attach_voice_chain()
        self._attach_chat_handler()

        # --------------------------------------------------
        # 🌉 BouyomiIpcBridge 自動起動（MCV連携用）
        # --------------------------------------------------
        self._bouyomi_bridge_process = None
        self._start_bouyomi_bridge()
        logger.info("✅ 7/7 最終初期化完了")

        # 閉じるときのハンドラ
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # --------------------------------------------------
    # 🪟 メインウィンドウ初期化
    # --------------------------------------------------
    def _setup_main_window(self) -> None:
        self.root.geometry(f"{self.config.width}x{self.config.height}")
        self.root.minsize(900, 600)

        # ルートに1つだけ Notebook を置く
        self.notebook = GyururuTabContainer(
            master=self.root,
            message_bus=self.message_bus,
            config_manager=self.config_manager,
        )
        self.notebook.pack(fill="both", expand=True)

    # --------------------------------------------------
    # 🧩 タブ初期化（必要なら追加の初期化処理）
    # --------------------------------------------------
    def _setup_tabs(self) -> None:
        # 追加のタブ連携やメッセージ購読処理をここで記述可能
        logger.info("🧩 タブ初期化完了")

    # --------------------------------------------------
    # 🔗 VoiceChain 最小回路
    # --------------------------------------------------
    def _attach_voice_chain(self) -> None:
        if not VOICECHAIN_AVAILABLE or bootstrap_voice_chain is None:
            logger.warning("VoiceChain Bootstrap が利用できないため、最小回路はスキップします")
            return

        try:
            # v17.3 正式仕様想定:
            #   bootstrap_voice_chain(message_bus=..., config_manager=..., voice_manager=..., ai_manager=...)
            _sigsafe_call(
                bootstrap_voice_chain,
                message_bus=self.message_bus,
                config_manager=self.config_manager,
                voice_manager=self.voice_manager,
                ai_manager=self.ai_manager,
            )
            logger.info("🔗 VoiceChain bootstrap 起動（互換ラッパ）")
        except Exception as e:
            logger.error(f"VoiceChain bootstrap エラー: {e}", exc_info=True)

    # --------------------------------------------------
    # 💬 ChatHandler 最小回路
    # --------------------------------------------------
    def _attach_chat_handler(self) -> None:
        """
        ❌ v17.3.1: ChatHandler は使用しない（導線ルールブックに準拠）
        AI_REQUEST は tab_chat/app.py からのみ発行する。
        VOICE_REQUEST は AIIntegrationManager からのみ発行する。
        """
        logger.info("⚠️ ChatHandler は v17.3.1 で無効化されています（導線ルール準拠）")
        return

        # 以下のコードは v17.3.1 で無効化されました
        # if not CHAT_HANDLER_AVAILABLE or attach_chat_consumer is None:
        #     logger.warning("ChatHandler が利用できないため、最小回路はスキップします")
        #     return
        #
        # try:
        #     # v17.3 正式仕様想定:
        #     #   attach_chat_consumer(message_bus=..., config_manager=..., ai_manager=..., voice_manager=...)
        #     _sigsafe_call(
        #         attach_chat_consumer,
        #         message_bus=self.message_bus,
        #         config_manager=self.config_manager,
        #         ai_manager=self.ai_manager,
        #         voice_manager=self.voice_manager,
        #     )
        #     logger.info("💬 ChatHandler attach 完了（互換ラッパ）")
        # except Exception as e:
        #     logger.error(f"ChatHandler attach エラー: {e}", exc_info=True)

    # --------------------------------------------------
    # 🛑 ChatHandler 切り離し
    # --------------------------------------------------
    def _detach_chat_handler(self) -> None:
        """
        ❌ v17.3.1: ChatHandler は使用しないため、detach も不要
        """
        logger.info("⚠️ ChatHandler は v17.3.1 で無効化されています（detach 不要）")
        return

        # 以下のコードは v17.3.1 で無効化されました
        # if not CHAT_HANDLER_AVAILABLE or detach_chat_consumer is None:
        #     return
        #
        # try:
        #     _sigsafe_call(
        #         detach_chat_consumer,
        #         message_bus=self.message_bus,
        #     )
        #     logger.info("💬 ChatHandler detach 完了（互換ラッパ）")
        # except Exception as e:
        #     logger.error(f"ChatHandler detach エラー: {e}", exc_info=True)

    # --------------------------------------------------
    # 🌉 BouyomiIpcBridge 起動・停止
    # --------------------------------------------------
    def _start_bouyomi_bridge(self) -> None:
        """MCV連携用のBouyomiIpcBridgeを起動（完全防御版）"""
        logger.debug("_start_bouyomi_bridge() 呼び出し開始")
        try:
            # exeファイルのパスを構築
            bridge_exe = os.path.join(
                BASE_DIR,
                "bouyomi_ipc_bridge",
                "bin",
                "Release",
                "net48",
                "BouyomiIpcBridge.exe"
            )
            logger.debug(f"bridge_exe パス: {bridge_exe}")

            # exeが存在するか確認
            if not os.path.exists(bridge_exe):
                logger.info("⚠️ BouyomiIpcBridge.exe が見つかりません")
                logger.info("   MCV連携を使用する場合は、bouyomi_ipc_bridge\\build.bat を実行してビルドしてください")
                logger.info("   （アプリ起動には影響ありません）")
                return  # 静かに抜ける（絶対に例外を投げない）

            # バックグラウンドでexeを起動
            logger.debug("subprocess.Popen 実行開始")
            self._bouyomi_bridge_process = subprocess.Popen(
                [bridge_exe],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"🌉 BouyomiIpcBridge 起動成功: PID={self._bouyomi_bridge_process.pid}")

        except FileNotFoundError as e:
            # ファイルが見つからない場合
            logger.info(f"⚠️ BouyomiIpcBridge.exe が見つかりません: {e}")
            logger.info("   （アプリ起動には影響ありません）")
            self._bouyomi_bridge_process = None
        except Exception as e:
            # その他すべての例外をキャッチ（絶対にアプリを落とさない）
            logger.info(f"⚠️ BouyomiIpcBridge 起動エラー: {e}")
            logger.info("   MCV連携は利用できませんが、他の機能は正常に動作します")
            self._bouyomi_bridge_process = None

    def _stop_bouyomi_bridge(self) -> None:
        """BouyomiIpcBridgeを停止（すべてのプロセスを終了）"""
        # 1. 自動起動したプロセスを停止
        if self._bouyomi_bridge_process:
            try:
                self._bouyomi_bridge_process.terminate()
                self._bouyomi_bridge_process.wait(timeout=5)
                logger.info("🌉 BouyomiIpcBridge 停止完了（自動起動分）")
            except Exception as e:
                logger.warning(f"⚠️ BouyomiIpcBridge 停止エラー: {e}")
                try:
                    self._bouyomi_bridge_process.kill()
                except Exception:
                    pass
            finally:
                self._bouyomi_bridge_process = None

        # 2. すべてのBouyomiIpcBridge.exeを停止（手動起動分も含む）
        try:
            import psutil
            terminated_count = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] == 'BouyomiIpcBridge.exe':
                        proc.terminate()
                        terminated_count += 1
                        logger.info(f"🌉 BouyomiIpcBridge 停止: PID={proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if terminated_count > 0:
                logger.info(f"🌉 BouyomiIpcBridge 全プロセス停止完了: {terminated_count}個")
        except ImportError:
            # psutilがない場合はスキップ
            logger.debug("psutilがインストールされていないため、手動起動分の停止をスキップ")
        except Exception as e:
            logger.warning(f"⚠️ BouyomiIpcBridge 全プロセス停止エラー: {e}")

    # --------------------------------------------------
    # 🚪 終了ハンドラ
    # --------------------------------------------------
    def on_close(self) -> None:
        logger.info("🛑 アプリケーション終了処理開始")

        # BouyomiIpcBridge 停止
        self._stop_bouyomi_bridge()

        # ChatHandler 切り離し
        self._detach_chat_handler()

        # VoiceManager クリーンアップ
        try:
            if self.voice_manager and hasattr(self.voice_manager, "shutdown"):
                self.voice_manager.shutdown()
                logger.info("🎤 VoiceManager shutdown 完了")
        except Exception as e:
            logger.error(f"VoiceManager shutdown エラー: {e}", exc_info=True)

        self.root.destroy()
        logger.info("✅ アプリケーション終了")

    # --------------------------------------------------
    # ▶️ メインループ
    # --------------------------------------------------
    def run(self) -> None:
        self.running = True
        logger.info("🚀 ぎゅるるボット v17.3 起動（統合版）")
        self.root.mainloop()
        self.running = False


# ==========================================================
# 🧪 セルフテスト用エントリポイント
# ==========================================================
def main() -> None:
    # グローバル例外フックをインストール（起動時の例外を確実にログに記録）
    _install_global_excepthook()
    logger.info("🚀 Gyururu Bot メイン起動開始")

    try:
        root = tk.Tk()
    except Exception as e:
        print(f"[FATAL] Tkinter の初期化に失敗しました: {e}")
        logger.critical(f"[FATAL] Tkinter の初期化に失敗しました: {e}", exc_info=True)
        sys.exit(1)

    app = GyururuMainApp(root)
    try:
        logger.info("▶ mainloop 開始")
        app.run()
        logger.info("⏹ mainloop 終了（正常終了）")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt により終了しました")
    except Exception as e:
        logger.error(f"メインループ中に例外: {e}", exc_info=True)
        traceback.print_exc()
    finally:
        try:
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()
