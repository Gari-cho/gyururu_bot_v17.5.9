# -*- coding: utf-8 -*-
"""
💬 AIとチャットタブ - v17.3 統一仕様対応版
- AI設定の反映
- 色分け表示（ユーザー/AI）
- VoiceManager Singleton 統合
- MessageBus 統一（get_message_bus()）
- 例外・ロギング強化
- 後方互換（Events が無い環境でも文字列キーで動作）
"""

# --- import path (プロジェクト直下を import 対象に) ---
import os as _os, sys as _sys
_THIS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.abspath(_os.path.join(_THIS_DIR, ".."))  # プロジェクト直下
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)
del _os, _sys, _THIS_DIR, _PROJECT_ROOT
# ---------------------------------------------------------

# .env を常時読込（API_KEY 等を即利用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
from datetime import datetime, timezone, timedelta
import sys
import os
import random
import logging

# ロギング設定（ルートロガーの設定を継承）
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ===== 共有モジュールの解決（成功すれば本物 / 失敗時のみ限定フォールバック） =====
MESSAGEBUS_AVAILABLE = False
EVENTS_AVAILABLE = False
CONFIG_MANAGER_AVAILABLE = False
VOICE_SINGLETON_AVAILABLE = False
STANDALONE_MINIBUS = None  # 本当に単体実行時だけ使う

# --- Events（なければ最小互換を用意） ---
try:
    from shared.event_types import Events
    EVENTS_AVAILABLE = True
except Exception:
    class Events:
        ONECOMME_COMMENT = "ONECOMME_COMMENT"
        CHAT_MESSAGE = "CHAT_MESSAGE"
        USER_JOIN = "USER_JOIN"
        VOICE_REQUEST = "VOICE_REQUEST"
        TAB_READY = "TAB_READY"
        AI_RESPONSE = "AI_RESPONSE"
        APP_STARTED = "APP_STARTED"

# --- MessageBus ---
try:
    from shared.message_bus import get_message_bus
    MESSAGEBUS_AVAILABLE = True
    logger.info("✅ MessageBus関連インポート成功")
except Exception as e:
    logger.warning(f"⚠️ MessageBus 利用不可（限定フォールバックに切替）: {e}")

    # v17.3 規約：原則スタブ禁止だが、単体実行用に“最小限”保持
    class _MiniBus:
        def __init__(self):
            self._subs = {}
        def publish(self, event, data=None, sender=None):
            key = str(getattr(event, "name", getattr(event, "value", event))).upper()
            for cb in self._subs.get(key, []):
                try:
                    cb(data or {}, sender)
                except Exception as ex:
                    logger.error(f"MiniBus callback error @ {key}: {ex}")
        def subscribe(self, event, callback):
            key = str(getattr(event, "name", getattr(event, "value", event))).upper()
            self._subs.setdefault(key, []).append(callback)
        def unsubscribe(self, event, callback):
            key = str(getattr(event, "name", getattr(event, "value", event))).upper()
            if key in self._subs and callback in self._subs[key]:
                self._subs[key].remove(callback)

    STANDALONE_MINIBUS = _MiniBus()
    def get_message_bus():
        # 単体実行のみの緊急避難。統合起動では本物が必ず使われる想定。
        return STANDALONE_MINIBUS

# --- UnifiedConfigManager ---
try:
    from shared.unified_config_manager import UnifiedConfigManager
    CONFIG_MANAGER_AVAILABLE = True
    logger.info("✅ UnifiedConfigManager インポート成功")
except Exception as e:
    logger.warning(f"⚠️ UnifiedConfigManager 利用不可: {e}")
    class UnifiedConfigManager:
        def __init__(self):
            self._cfg = {}
        def get(self, key, default=None):
            cur = self._cfg
            try:
                for k in key.split('.'):
                    if isinstance(cur, dict):
                        cur = cur.get(k, {})
                    else:
                        return default
            except Exception:
                return default
            return default if cur == {} else cur
        def set(self, key, val):
            cur = self._cfg
            parts = key.split('.')
            for k in parts[:-1]:
                cur = cur.setdefault(k, {})
            cur[parts[-1]] = val
        def save(self):
            # ✅ v17.6.1 追加: 警告ログを出力
            logger.warning("⚠️ フォールバック UnifiedConfigManager は save() に対応していません。shared.unified_config_manager が正しくインポートされていることを確認してください。")
            return

# --- VoiceManager Singleton ---
try:
    from shared.voice_manager_singleton import get_voice_manager, speak_text, get_voice_status
    VOICE_SINGLETON_AVAILABLE = True
    logger.info("✅ VoiceManager Singleton インポート成功")
except Exception as e:
    logger.warning(f"⚠️ VoiceManager Singleton 未使用: {e}")

# --- UI共通ヘルパー ---
try:
    from shared.ui_helpers import apply_statusbar_style
except Exception:
    # フォールバック：共通関数が見つからない場合は何もしない
    def apply_statusbar_style(widget):
        return "#66DD66", "#000000"

# ============================================================
# 🔧 返答開始境界ヘルパ
# ============================================================
def _resolve_start_boundary(config, stream_api=None, now_ms=None):
    """
    返答開始の境界（UTC ms）を一度だけ確定して返す。
    mode: on_connect | stream_start | since_timestamp
    """
    try:
        mode = (config.get("chat.start_mode", "on_connect") or "on_connect").strip()
    except Exception:
        mode = "on_connect"

    now_ms = now_ms or int(time.time() * 1000)

    if mode == "on_connect":
        boundary = now_ms

    elif mode == "stream_start":
        boundary = None
        try:
            if stream_api and hasattr(stream_api, "get_stream_start_timestamp_ms"):
                boundary = stream_api.get_stream_start_timestamp_ms()
        except Exception:
            boundary = None
        boundary = boundary or now_ms  # 取得できなければ接続時刻にフォールバック

    elif mode == "since_timestamp":
        try:
            ts = int(config.get("chat.start_since_ts", 0) or 0)
        except Exception:
            ts = 0
        boundary = ts if ts > 0 else now_ms

    else:
        boundary = now_ms  # 不明モードは安全側で接続時刻

    try:
        config.set("chat.last_boundary_ts", boundary)
        config.save()
    except Exception:
        pass

    return boundary

# ============================================================
# 🔧 AI設定を送信直前に反映するヘルパー
# ============================================================
def _apply_ai_settings_on_demand(ai_connector, config_manager):
    """送信直前にAI設定タブの内容を反映(都度読み出し)"""
    try:
        ai_conf = (config_manager.get("ai", {}) or {}) if config_manager else {}
        sys_prompt = ai_conf.get("system_prompt") or ai_conf.get("persona") or ""
        temperature = ai_conf.get("temperature")
        model = ai_conf.get("model") or ai_conf.get("provider_model")

        # モデル指定(AIコネクタ側が対応していれば反映)
        try:
            if hasattr(ai_connector, "config") and isinstance(getattr(ai_connector, "config"), dict):
                if model:
                    ai_connector.config["model"] = model
            for meth in ("set_model", "set_current_model", "set_provider_model"):
                if hasattr(ai_connector, meth) and callable(getattr(ai_connector, meth)):
                    if model:
                        getattr(ai_connector, meth)(model)
        except Exception:
            pass

        return {
            "system_prompt": sys_prompt or None,
            "temperature": float(temperature) if temperature is not None else None,
            "model": model or None,
        }
    except Exception:
        return {"system_prompt": None, "temperature": None, "model": None}

# ===== チャットの色分けタグ管理 =====
class ChatDisplayColorized:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.message_count = 0
        self.max_messages = 1000

        # ① 表示色（前景色）
        self.platform_colors = {
            'youtube': '#FF0000',
            'twitch': '#9146FF',
            'niconico': '#FF6600',
            'twitcasting': '#00A0E9',
            'mildom': '#FF1744',
            'openrec': '#3F51B5',
            'reality': '#E91E63',
            'onecomme': '#00FF80',
            'showroom': '#66BB6A',
            'bilibili': '#00A1D6',
            'test': '#FFA500',
            'manual': '#FFFFFF',
            'ai': '#44FF44',
            'system': '#FFD700',
            'unknown': '#CCCCCC',
        }

        # ② 絵文字
        self.platform_emojis = {
            'youtube': '📺', 'twitch': '🎮', 'niconico': '📹',
            'twitcasting': '📱', 'mildom': '🎯', 'openrec': '🔴',
            'reality': '🌟', 'onecomme': '💬', 'showroom': '🏠',  # 🔧 追加
            'bilibili': '🅱️',  # 🔧 追加（雰囲気アイコン）
            'test': '🧪', 'manual': '👤', 'ai': '🤖', 'system': '⚙️', 'unknown': '❓',
        }

        # ③ プレフィクス
        self.platform_prefixes = {
            'youtube': 'YT', 'twitch': 'TW', 'niconico': 'ニコ',
            'twitcasting': 'ツイキャス', 'mildom': 'Mildom',
            'openrec': 'オープンレック', 'reality': 'REALITY',
            'onecomme': 'わんコメ', 'test': 'TEST', 'manual': '手動',
            'ai': 'AI', 'system': 'SYS', 'unknown': '?',
        }

        # ④ 正規化テーブル（表記ゆれ・別名 → 正規キー）
        self.platform_aliases = {
            'youtube': {'youtube', 'yt', 'youtubelive', 'youtube_live', 'youTube'},
            'twitch': {'twitch', 'twitchtv'},
            # 🔧 ニコ生系のゆれ追加
            'niconico': {'niconico', 'nicovideo', 'nico', 'ニコ', 'ニコニコ', 'nicolive', 'ニコ生', 'niconama', 'nico-live'},
            'twitcasting': {'twitcasting', 'twicas', 'twitcast', 'ツイキャス'},
            'mildom': {'mildom', 'md'},
            'openrec': {'openrec', 'openrec.tv', 'or'},
            'reality': {'reality', 'rl'},
            'onecomme': {'onecomme', 'あんコメ', 'わんコメ', 'comment_tester', 'comment-tester', 'comment tester', 'commenttester'},
            'showroom': {'showroom', 'sr', 'show-room', 'shoowroom', 'showrom'},  # 🔧 追加（ありがちなタイプミスも拾う）
            'bilibili': {'bilibili', 'bili', 'bili-bili', 'biliili', 'bilibli'},  # 🔧 追加（biliili 等の誤字も回収）
            'test': {'test', 'tester'},
            'manual': {'manual', '手動'},
            'ai': {'ai', 'gemini', 'chatgpt', 'claude', 'localai'},
            'system': {'system', 'sys'},
        }

        self._setup_text_tags()
        logger.info("✅ 色分け表示システム初期化完了")
        
        # --- StartBoundary 確定（接続直後の過去コメント暴走防止） ---
        try:
            cfg = getattr(self, "config_manager", None)
            self._boundary_ts = _resolve_start_boundary(cfg if cfg else {}, stream_api=None)
            self._ignored_count = 0
            try:
                mode = cfg.get("chat.start_mode", "on_connect") if cfg else "on_connect"
            except Exception:
                mode = "on_connect"
            logger.info(f"[StartBoundary] mode={mode} boundary_ts={self._boundary_ts}")
        except Exception as e:
            logger.warning(f"[StartBoundary] 初期化に失敗しました: {e}")
            self._boundary_ts = int(time.time() * 1000)
            self._ignored_count = 0

    # ▼ユーティリティ：サービス名を正規キーへ
    def normalize_platform(self, raw_value: str) -> str:
        s = (raw_value or '').strip().lower()
        if not s:
            return 'unknown'
        if s in self.platform_colors:
            return s
        for canon, aliases in self.platform_aliases.items():
            if s in aliases:
                return canon
        if 'comment' in s and 'tester' in s:
            return 'onecomme'
        return 'unknown'

    def _norm_platform(self, raw: str) -> str:
        return self.normalize_platform(raw)

    def tag_for_platform(self, platform: str) -> str:
        return f"plat_{self.normalize_platform(platform)}"

    def _setup_text_tags(self):
        # 共通タグ
        self.text_widget.tag_configure("name", foreground="#ECEFF1", font=("Segoe UI", 10, "bold"))
        self.text_widget.tag_configure("msg", foreground="#ECEFF1", font=("Segoe UI", 10))
        self.text_widget.tag_configure("timestamp", foreground="#90A4AE")
        self.text_widget.tag_configure("premium", foreground="#FFD700", font=("Segoe UI", 10, "bold"))
        self.text_widget.tag_configure("first_time", foreground="#80DEEA", font=("Segoe UI", 10, "bold"))
        self.text_widget.tag_configure("username", foreground="#CFD8DC", font=("Segoe UI", 10, "bold"))

        # 役割別の名前色（配信者・AI・視聴者）
        self.text_widget.tag_configure("role_streamer", foreground="#4FC3F7", font=("Segoe UI", 10, "bold"))  # 水色
        self.text_widget.tag_configure("role_ai", foreground="#00C853", font=("Segoe UI", 10, "bold"))  # 緑
        self.text_widget.tag_configure("role_viewer", foreground="#ECEFF1", font=("Segoe UI", 10, "bold"))  # 白

        # プラットフォーム別の名前色
        for key, col in self.platform_colors.items():
            self.text_widget.tag_configure(f"plat_{key}", foreground=col, font=("Segoe UI", 10, "bold"))

    def _append_chat_row(self, username, text, role="viewer", platform="onecomme"):
        """
        左に「名前：」（役割別色）、右側に本文（インデント）で揃える。
        役割優先: 配信者(水色)・AI(緑)・視聴者(白)
        """
        if not text:
            return

        # 役割ベースの色分け（配信者・AI優先）
        if role in ("streamer", "user"):  # userも配信者として扱う
            name_tag = "role_streamer"
        elif role == "ai" or platform in ("ai", "gemini", "chatgpt", "claude"):
            name_tag = "role_ai"
        else:
            # 視聴者またはその他の役割
            plat_key = self._norm_platform(platform)
            name_tag = f"plat_{plat_key}" if f"plat_{plat_key}" in self.text_widget.tag_names() else "role_viewer"

        # 表示用：絵文字・接頭辞
        plat_key = self._norm_platform(platform)
        emoji = self.platform_emojis.get(plat_key, "")
        prefix = self.platform_prefixes.get(plat_key, "")
        display_name = f"{emoji}{prefix} {username}：" if prefix else f"{emoji}{username}："

        # インデント：名前幅にあわせて左余白
        indent_px = max(100, 12 * len(display_name))
        indent_tag = f"indent_{len(display_name)}"
        if indent_tag not in self.text_widget.tag_names():
            self.text_widget.tag_configure(indent_tag, lmargin1=indent_px, lmargin2=indent_px)

        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", display_name, (name_tag,))
        self.text_widget.insert("end", text + "\n", ("msg", indent_tag))
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")

    def add_formatted_message(self, msg_data):
        try:
            username = msg_data.get('username', '匿名')
            message = msg_data.get('message', msg_data.get('text', ''))
            platform = self._detect_platform(msg_data)
            self._append_chat_row(username, message, role=msg_data.get('message_type', 'viewer'), platform=platform)
            self.message_count += 1
            if self.message_count > self.max_messages:
                self._cleanup_old_messages()
            prefix = self.platform_prefixes.get(platform, '?')
            logger.debug(f"💬 チャット表示: [{prefix}] {username}: {message[:30]}...")
        except Exception as e:
            logger.error(f"❌ チャット表示エラー: {e}")
            self._insert_fallback_message(msg_data)

    def _detect_platform(self, msg_data):
        if 'platform' in msg_data and msg_data['platform']:
            return self.normalize_platform(str(msg_data['platform']))
        if 'service' in msg_data and msg_data['service']:
            return self.normalize_platform(str(msg_data['service']))
        service_id = str(msg_data.get('service_id', '')).lower()
        if service_id:
            return self.normalize_platform(service_id)
        source = str(msg_data.get('source', '')).lower()
        for p in self.platform_colors:
            if p in source:
                return p
        msg_type = str(msg_data.get('message_type', '')).lower()
        if msg_type in ['ai', 'system', 'test']:
            return msg_type
        return 'unknown'

    # 旧式フォールバック（基本使わない）
    def _insert_colored_message(self, timestamp, username, message, platform, is_premium, is_first_time):
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, f"[{timestamp}] ", ("timestamp",))
            emoji = self.platform_emojis.get(platform, '❓')
            prefix = self.platform_prefixes.get(platform, '?')
            self.text_widget.insert(tk.END, f"{emoji}{prefix} ", (f"plat_{platform}",))
            self.text_widget.insert(tk.END, f"{username}: ", ("username",))
            self.text_widget.insert(tk.END, f"{message}\n", ("msg",))
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
        except Exception as e:
            logger.error(f"❌ 色分けメッセージ挿入エラー: {e}")
            self.text_widget.config(state=tk.DISABLED)

    def _insert_fallback_message(self, msg_data):
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] エラー表示: {msg_data}\n")
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)
        except Exception as e:
            logger.error(f"❌ フォールバック表示エラー: {e}")

    def _cleanup_old_messages(self):
        try:
            self.text_widget.config(state=tk.NORMAL)
            lines = self.text_widget.get("1.0", tk.END).split('\n')
            keep_lines = lines[len(lines)//2:]
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", '\n'.join(keep_lines))
            self.text_widget.config(state=tk.DISABLED)
            self.message_count = len(keep_lines)
            logger.debug(f"🧹 古いメッセージクリア: {self.message_count}件保持")
        except Exception as e:
            logger.error(f"❌ メッセージクリアエラー: {e}")

    def clear_chat(self):
        try:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.config(state=tk.DISABLED)
            self.message_count = 0
            logger.info("🗑️ チャット履歴クリア完了")
        except Exception as e:
            logger.error(f"❌ チャットクリアエラー: {e}")

    def export_chat_log(self, file_path):
        try:
            content = self.text_widget.get(1.0, tk.END)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"📄 ログ保存完了: {file_path}")
        except Exception as e:
            logger.error(f"❌ ログ保存エラー: {e}")

# ===== フォールバックAI =====
class AIConnectorFixed:
    def __init__(self):
        self.response_count = 0
        self.responses = [
            "やっほー!今日もいい天気ぎゅる〜",
            "色分け対応版が正常に動作してるぎゅる!",
            "VoiceManager Singletonもばっちりぎゅる🎤",
            "何かお手伝いできることはあるぎゅる?😊",
            "MessageBus統合も完璧ぎゅる〜✨",
            "応答確率100%でお答えしてるぎゅる💪",
            "YouTubeGemini緑・色分けもキレイぎゅる🎨"
        ]
        logger.info("✅ AIConnector(フォールバック)初期化完了")

    def get_response(self, message):
        try:
            message_lower = message.lower()
            if 'こんにちは' in message_lower or 'hello' in message_lower:
                response = "やっほー!今日もいい天気ぎゅる〜"
            elif 'テスト' in message_lower or 'test' in message_lower:
                response = "色分けテスト動作確認完了ぎゅる!VoiceManager Singletonも正常動作中ぎゅる🔥"
            elif 'ありがとう' in message_lower:
                response = "どういたしましてぎゅる!お役に立てて嬉しいぎゅる✨"
            elif '色' in message_lower or 'カラー' in message_lower:
                response = "色分け機能が追加されたぎゅる!YouTube赤・Twitch紫・ニコニコオレンジで見やすくなったぎゅる🎨"
            else:
                response = random.choice(self.responses)
            self.response_count += 1
            return response
        except Exception as e:
            logger.error(f"❌ AI応答エラー: {e}")
            return "申し訳ございませんぎゅる。AI応答でエラーが発生したぎゅる。"

    def chat(self, message, **kwargs):
        return self.get_response(message)

    def generate(self, message, **kwargs):
        return self.get_response(message)

    def get_statistics(self):
        return {'response_count': self.response_count, 'fallback_mode': True}

# ===== メインアプリ =====
class ChatAppCompleteFixed:
    def __init__(self, master, message_bus=None, config_manager=None, app_instance=None, shared_volume_var=None, shared_mute_var=None):
        # 🐛 DEBUG: __init__ 呼び出しログ
        import uuid
        init_id = str(uuid.uuid4())[:8]
        logger.info(f'🐛 [DEBUG {init_id}] ChatApp.__init__ 開始: id(self)={id(self)}')

        self.master = master
        self.message_bus = message_bus or get_message_bus()
        self.app_instance = app_instance
        self.running = True

        # ========================================
        # GUI Queue 初期化（必ず subscribe より前）
        # ========================================
        import queue
        self.gui_queue = queue.Queue()
        self._gui_queue_running = False
        logger.info("✅ GUI Queue 初期化（subscribe より前）")

        logger.info("🚀 ChatApp 初期化開始...")
        logger.info(f'🐛 [DEBUG {init_id}] message_bus={self.message_bus}, id(message_bus)={id(self.message_bus)}')

        # --- ConfigManager を確定（注入 or シングルトン取得） ---
        self.config_manager = config_manager
        if self.config_manager is None:
            try:
                from shared.unified_config_manager import get_config_manager as _get_cfg
                self.config_manager = _get_cfg()
                logger.info("✅ UnifiedConfigManager インポート成功")
            except Exception as e:
                logger.warning(f"⚠️ UnifiedConfigManager 未使用: {e}")
                self.config_manager = None

        # === VoiceManager Singleton 統合（v17.3 標準） ===
        self.voice_manager = None
        try:
            from shared.voice_manager_singleton import get_voice_manager as _get_vm
            self.voice_manager = _get_vm(config_manager=self.config_manager)
            _st = getattr(self.voice_manager, "status", lambda: {"available": True})()
            if not _st.get("available", True):
                logger.warning("⚠️ VoiceManager: available=False（ChatTab）")
            logger.info("✅ VoiceManager 統合OK (ChatApp)")
        except Exception as e:
            logger.warning(f"⚠️ VoiceManager Singleton 未使用: {e}")
            self.voice_manager = None

        # 既存の基本設定初期化（AI有効/応答確率など）
        self._init_basic_config()

        # ============================
        # ここから UI 変数の初期化
        # ============================

        # 二重発火防止フラグ
        self._ai_reply_guard = False

        # Phase 2-4: AI リクエスト履歴（多重発行防止）
        # 形式: [(text, timestamp), ...]
        self._ai_request_history = []
        self._ai_request_history_max = 10  # 保持する履歴の最大数
        self._ai_request_duplicate_window = 5.0  # 重複判定の時間窓（秒）

        # Phase 2: 応答確率スライダーの自動保存タイマー（デバウンス用）
        self._response_prob_save_timer = None

        # MessageBus 二重購読防止フラグ (Phase 1.3)
        self._messagebus_integrated = False
        self._ai_status_subscribed = False

        # AI応答モード（0=キーワード, 1=全返答）
        # Phase 2: 設定から初期値を読み込む
        default_mode = 1  # デフォルトは全返答
        if self.config_manager:
            mode_str = self.config_manager.get('ai.response_mode', 'always')
            default_mode = 0 if mode_str == 'keyword_only' else 1
        self.ai_reply_mode = tk.IntVar(value=default_mode)
        # Phase 2: 変更時に自動保存
        self.ai_reply_mode.trace_add('write', lambda *args: self._on_reply_mode_change())

        # 音声読み上げの対象（すべて ON で開始）
        self.tts_streamer_enabled = tk.BooleanVar(value=True)
        self.tts_ai_enabled = tk.BooleanVar(value=True)
        self.tts_viewer_enabled = tk.BooleanVar(value=True)

        # 応答確率（%）
        # Phase 2: 設定から初期値を読み込む
        try:
            default_prob = 100
            if self.config_manager:
                prob_float = float(self.config_manager.get("ai.response_probability", 1.0))
                default_prob = int(prob_float * 100)
        except Exception:
            default_prob = 100
        self.ai_probability = tk.IntVar(value=default_prob)
        # 旧バージョン互換用
        self.ai_probability_var = self.ai_probability
        # Phase 2: 変更時に自動保存（既存の _on_probability_change を使用）
        self.ai_probability.trace_add('write', lambda *args: self._on_probability_change())

        # --- AIステータス内部フラグ（表示用の現在状態を保持） ---
        self._ai_connected = False
        self._ai_provider = "-"
        self._ai_model = "-"

        # 直近に受信したAI統合状態（重複SYS行の抑制用）
        # 形式: (provider, model, connected_bool)
        self._last_ai_status = None

        # 直近に受信したAI_RESPONSE（重複応答の抑制用）
        self._last_ai_response_ts = None
        self._last_ai_response_text_prefix = None

        # --- Shared audio controls (依頼書⑤: 音声制御タブと完全連動) ---
        # 上位から注入された共有Varを使用（無ければフォールバック）
        if shared_volume_var is not None:
            self.shared_volume_var = shared_volume_var
            logger.info("✅ 共有音量変数を受け取りました（タブ間連動）")
        else:
            self.shared_volume_var = tk.IntVar(value=80)
            logger.info("⚠️ 共有音量変数が未提供（スタンドアロンモード）")

        if shared_mute_var is not None:
            self.shared_mute_var = shared_mute_var
            logger.info("✅ 共有ミュート変数を受け取りました（タブ間連動）")
        else:
            self.shared_mute_var = tk.BooleanVar(value=False)
            logger.info("⚠️ 共有ミュート変数が未提供（スタンドアロンモード）")

        # ============================
        # ここまで UI 変数の初期化
        # ============================

        # フレームの配置（タブ/スタンドアロン自動判定）
        if isinstance(master, (tk.Frame, ttk.Frame)):
            self.frame = self.master
            self.is_tab_mode = True
            logger.info("🎫 タブモード:親フレームに直接配置")
        else:
            self.frame = tk.Frame(self.master, bg='#2b2b2b')
            self.frame.pack(fill=tk.BOTH, expand=True)
            self.is_tab_mode = False
            logger.info("🖥️ スタンドアロンモード:新規フレーム作成")

        # モジュール初期化・UI構築・バス購読など
        self._init_modules()
        self._build_complete_ui()
        self._init_color_tags()
        self._setup_messagebus_integration()

        # === AI ステータス連携 ===
        if self.message_bus:
            # Phase 1.3: AI_STATUS_UPDATE 二重購読防止ガード
            if not self._ai_status_subscribed:
                try:
                    # ステータス更新とテスト結果を購読
                    self.message_bus.subscribe("AI_STATUS_UPDATE", self._on_ai_status_update)
                    self.message_bus.subscribe("AI_TEST_RESULT", self._on_ai_test_result)
                    self._ai_status_subscribed = True  # ガードフラグをセット
                except Exception as e:
                    logger.warning(f"AIステータス購読エラー: {e}")
            else:
                logger.debug("⚠️ AI_STATUS_UPDATE購読は既に完了しています（二重実行防止）")

            # Phase 1.3.1: AI_STATUS_REQUEST の自動発行を削除
            # AI状態は ai_integration_manager.start() が APP_STARTED 受信時に自動通知する
            logger.info("✅ AI_STATUS_UPDATE購読完了（初回通知は AIIntegrationManager から自動発行されます）")

        # --- StartBoundary を確定（接続前コメントへの一斉返答を防止）---
        try:
            cfg = getattr(self, "config_manager", None)
            self._boundary_ts = _resolve_start_boundary(cfg if cfg else {}, stream_api=None)
            self._ignored_count = 0
            try:
                mode = cfg.get("chat.start_mode", "on_connect") if cfg else "on_connect"
            except Exception:
                mode = "on_connect"
            logger.info(f"[StartBoundary] mode={mode} boundary_ts={self._boundary_ts}")
        except Exception as e:
            logger.warning(f"[StartBoundary] 初期化に失敗しました: {e}")
            self._boundary_ts = int(time.time() * 1000)
            self._ignored_count = 0

        # --- 返答開始ポイント UI の組み立て ---
        # （v17.6: _build_complete_ui 内で呼び出されるため、ここでは不要）

        # クリーンアップの登録
        self._setup_cleanup()

        # ステータス整形（ログ用）
        status_info = {
            'voice': "利用可能" if VOICE_SINGLETON_AVAILABLE else "利用不可",
            'config': "利用可能" if CONFIG_MANAGER_AVAILABLE else "利用不可",
            'messagebus': "接続済み" if self.message_bus else "未接続",
            'ai_integrated': "統合済み" if (self.app_instance and hasattr(self.app_instance, 'ai_connector')) else "フォールバック"
        }
        logger.info(
            f"✅ ChatApp初期化完了(Voice: {status_info['voice']}, "
            f"Config: {status_info['config']}, "
            f"Bus: {status_info['messagebus']}, "
            f"AI: {status_info['ai_integrated']})"
        )

        # ========================================
        # GUI Queue ドレイン開始（root が確定した後に実行）
        # ========================================
        self._start_gui_queue_drain()

    # ========================================
    # GUI Queue 関連メソッド（スレッドセーフなUI更新）
    # ========================================

    def _start_gui_queue_drain(self):
        """
        GUI Queue のドレイン処理を開始する。
        root.after で1回だけ登録し、以降は _drain_gui_queue が自己再帰する。
        """
        if not self._gui_queue_running:
            self._gui_queue_running = True
            # 33ms ≒ 30fps で開始
            self.master.after(33, self._drain_gui_queue)
            logger.info("✅ GUI Queue ドレイン開始")

    def _drain_gui_queue(self):
        """
        GUIスレッドで安全にキューを処理する。
        最大10件を一度に処理して、33ms後に再実行。
        """
        import queue
        processed = 0
        try:
            # 最大10件を処理（無制限drainは危険）
            for _ in range(10):
                try:
                    event_name, payload = self.gui_queue.get_nowait()
                except queue.Empty:
                    # キューが空 = 正常系
                    break
                else:
                    # イベント取得成功、処理を実行
                    processed += 1
                    try:
                        self._handle_event_in_gui_thread(event_name, payload)
                    except Exception as e:
                        logger.error(f"❌ GUI Queue ハンドラエラー ({event_name}): {e}", exc_info=True)
        except Exception as e:
            # 想定外のエラー（queue.Empty 以外）
            logger.error(f"❌ GUI Queue drain エラー: {e}", exc_info=True)
        finally:
            # 自己再帰（1箇所だけ after を使う）
            if self._gui_queue_running and hasattr(self, 'master'):
                self.master.after(33, self._drain_gui_queue)

    def _handle_event_in_gui_thread(self, event_name: str, payload: dict):
        """
        GUIスレッドで実行されることが保証された状態でイベントを処理。
        各イベントに対応する _impl メソッドを呼び出す。
        """
        try:
            if event_name == "AI_STATUS_UPDATE":
                self._on_ai_status_update_impl(payload)
            elif event_name == "AI_RESPONSE":
                self._on_ai_response_impl(payload, None)
            elif event_name == "CHAT_MESSAGE":
                self._on_chat_message_impl(payload, None)
            elif event_name == "ONECOMME_COMMENT":
                self._on_onecomme_comment_v173_impl(payload, None)
            else:
                logger.warning(f"⚠️ 未対応のGUI Queueイベント: {event_name}")
        except Exception as e:
            logger.error(f"❌ GUI イベント処理エラー ({event_name}): {e}", exc_info=True)

    # ========================================
    # 以下、既存メソッド
    # ========================================

    def _on_onecomme_comment_v173(self, data, sender=None):
        """
        MessageBus ハンドラ（ラッパー）: GUI Queue に積むだけ。
        実際の処理は _on_onecomme_comment_v173_impl で行う。
        """
        # 保険: gui_queue が存在しない場合は作成
        if not hasattr(self, "gui_queue") or self.gui_queue is None:
            import queue
            self.gui_queue = queue.Queue()
            logger.warning("⚠️ gui_queue が未初期化だったため作成しました（ONECOMME）")
        self.gui_queue.put(("ONECOMME_COMMENT", data))

    def _on_onecomme_comment_v173_impl(self, data, sender=None):
        """
        【GUI Queue 経由で呼ばれる】
        OneCommeからの受信コメントをUIに反映し、必要ならAIへも回す（v17.3 Phase 4 導線版）。
        - UI表示: 既存の _append_onecomme_to_ui を使用
        - 棒読みコマンドフィルタ: /SE, /SPEED などはスキップ
        - 音声読み上げ: voice_read_viewer がTrueなら VOICE_REQUEST を発行
        - キーワード判定: _should_call_ai() によるトリガーキーワードチェック
        - AI連携: キーワードが含まれる場合のみ AI_REQUEST を発行
        """
        try:
            # 既存: UIへの表示・タグ色分けなど
            self._append_onecomme_to_ui(data)

            # カウンター更新
            self.stats['received_comments'] += 1
            self._update_stats_display()

            # --- テキスト抽出 -------------------------
            text = str(data.get("text", "")).strip()
            # ✅ 修正: 表示とAIで同じ名前を使う（username を最優先）
            # message_bridge が username/user 両方を付与するので、username を優先
            user = str(
                data.get("username")   # UI側と同じフィールド（最優先）
                or data.get("user")    # 旧仕様 / bridge からの値
                or data.get("author")  # さらに古い互換用
                or ""
            ).strip() or "viewer"
            if not text:
                return

            # ✅ Phase 4: 棒読みちゃんコマンドのフィルタリング
            # /SE, /SPEED, /VOLUME, /TONE, /VOICE, /SKIP などはスキップ
            if text.startswith("/"):
                # 一部のコマンドは VoiceManager に委譲（将来実装）
                logger.debug(f"[ONECOMME] 棒読みコマンドを検出（スキップ）: {text}")
                return

            # ✅ v17.5.x 修正: 視聴者コメントの読み上げ追加
            # voice_read_viewer がTrueなら VOICE_REQUEST を発行
            # OneComme経由は全て視聴者扱い（配信者コメントは手動入力に限定）
            if self.voice_read_viewer.get():
                self._send_voice_request(text, user, role='viewer')
                logger.info(f"🎤 [ONECOMME] 視聴者コメント読み上げ: {user} - {text[:30]}...")

            # ✅ Phase 4: キーワード判定（_should_call_ai による）
            # トリガーキーワード（例：「ぎゅるる」「ギュルル」）が含まれる場合のみ AI_REQUEST
            should_respond, matched_char = self._should_call_ai(text)
            if not should_respond:
                logger.debug(f"[ONECOMME] キーワード未検出（AI応答スキップ）: {text[:30]}...")
                return

            # ✅ Phase 4: キーワードが含まれる場合のみ AI_REQUEST を発行
            payload = {
                "text": text,
                "source": "onecomme",
                "user": user,
                "username": user,  # v17.5 互換（AIIntegrationManager 用）
                "meta": {"tab": "chat", "route": "ONECOMME_COMMENT"},
                "character_name": matched_char,  # ✅ v17.6+: キーワードにヒットしたキャラ名
            }

            if getattr(self, "message_bus", None) and MESSAGEBUS_AVAILABLE:
                self._do_ai_request(payload, sender="chat_tab_onecomme")
                logger.info("📡 [ONECOMME] キーワード検出 → AI_REQUEST 送信: user=%s, text=%s...", user, text[:30])
            else:
                logger.warning("⚠️ MessageBus未接続のため AI_REQUEST を送信できません（ONECOMME）")

        except Exception as e:
            logger.error(f"ONECOMME_COMMENT処理エラー(v17.3 Phase 4): {e}")
            self.stats['errors'] += 1
            self._update_stats_display()


    def _append_streamer_to_ui(self, text: str):
        """
        配信者（手動入力）のメッセージを統合チャットに表示
        v17.5.7: streamer.display_name に統一
        """
        try:
            if hasattr(self, "chat_display") and self.chat_display:
                # 配信者名を取得（設定から）
                streamer_name = "配信者"
                try:
                    if self.config_manager:
                        # v17.5.7: streamer.display_name に統一
                        streamer_name = self.config_manager.get("streamer.display_name", "配信者") or "配信者"
                except Exception:
                    pass

                data = {
                    "username": streamer_name,
                    "message": text,
                    "platform": "manual",
                    "message_type": "user",
                }
                self.chat_display.add_formatted_message(data)

                # 入力欄をクリア
                if hasattr(self, "input_box"):
                    self.input_box.delete("1.0", "end")
        except Exception as e:
            logger.error(f"配信者メッセージ表示エラー: {e}")

    def _append_onecomme_to_ui(self, data: dict):
        """
        OneCommeコメントを統合チャットに表示

        ※ここでは「配信者/視聴者」を見た目上区別せず、
          すべて viewer 相当として扱う。
        """
        try:
            if hasattr(self, "chat_display") and self.chat_display:
                # 🔹 名前の優先順
                #   message_bridge 側で username/user を必ず入れている想定
                username = (
                    data.get("username")
                    or data.get("user")
                    or data.get("author")
                    or "匿名"
                )

                # 🔹 本文
                message = data.get("text") or data.get("message") or ""

                # 🔹 プラットフォーム
                #   - 直接渡されていればそれを優先
                #   - なければ raw 内から best-effort で推定
                platform = data.get("service") or data.get("platform")
                raw = data.get("raw") or {}
                if not platform:
                    platform = (
                        raw.get("service")
                        or raw.get("platform")
                        or raw.get("site")
                        or raw.get("provider")
                        or raw.get("source")
                        or "onecomme"
                    )

                # 🔍 DEBUG: MCV形式のコメントの raw を確認
                if username == "MCV" or platform == "onecomme":
                    logger.info(f"[MCV_DEBUG] username={username}, platform={platform}")
                    logger.info(f"[MCV_DEBUG] message={message[:50]}...")
                    logger.info(f"[MCV_DEBUG] raw keys={list(raw.keys())}")
                    logger.info(f"[MCV_DEBUG] raw={raw}")

                # 🔸 MCV互換形式の解析
                #   OneComme の MCV互換モードでは「@名前さん. 本文」形式で来る可能性がある
                import re
                if username == "MCV" and message.startswith("@"):
                    m = re.match(r"^@(.+?)さん\.\s*(.*)$", message)
                    if m:
                        real_name = m.group(1).strip()
                        real_msg = m.group(2).strip()
                        logger.info(f"[MCV_PARSE] 解析成功: name={real_name}, msg={real_msg[:30]}...")
                        username = real_name
                        message = real_msg
                    else:
                        logger.debug(f"[MCV_PARSE] パターン不一致: {message[:50]}")

                # 🔸 platform のマッピング改善
                #   MCV経由でもサービス情報があれば反映
                if platform in ("onecomme", "unknown"):
                    # raw 内から YouTube/Twitch などを探す
                    service_hint = (
                        raw.get("channel")
                        or raw.get("channelName")
                        or raw.get("userId")
                        or ""
                    )
                    if isinstance(service_hint, str):
                        service_lower = service_hint.lower()
                        if "youtube" in service_lower or "yt" in service_lower:
                            platform = "youtube"
                        elif "twitch" in service_lower or "tw" in service_lower:
                            platform = "twitch"
                        elif "nico" in service_lower or "nicolive" in service_lower:
                            platform = "nicolive"

                chat_data = {
                    "username": username,
                    "message": message,
                    "platform": platform,
                    # 🔹 見た目上はすべて視聴者として扱う
                    "message_type": "viewer",
                }
                self.chat_display.add_formatted_message(chat_data)
        except Exception as e:
            logger.error(f"ONECOMMEコメント表示エラー: {e}")

    def _on_streamer_send(self, *args, **kwargs):
        """
        配信者が手動で入力→送信したときのUI反映とAI投げ。
        v17.5.3: _do_ai_request() に統一（キャラ設定の自動反映）
        v17.5.7: CHAT_MESSAGE を publish して OBS 演出タブに配線
        """
        try:
            text = self.input_box.get("1.0", "end").strip()
            if not text:
                return

            # 既存: UIへの追加（自分の発言として色分け）
            self._append_streamer_to_ui(text)

            # v17.5.7: OBS 演出タブへの配線（CHAT_MESSAGE を publish）
            if self.message_bus and MESSAGEBUS_AVAILABLE:
                try:
                    # 配信者名を取得（v17.5.7: streamer.display_name に統一）
                    streamer_name = "配信者"
                    if hasattr(self, 'config_manager') and self.config_manager:
                        streamer_name = self.config_manager.get("streamer.display_name", "配信者") or "配信者"

                    chat_data = {
                        "username": streamer_name,
                        "text": text,
                        "platform": "manual",
                        "timestamp": datetime.now().isoformat(),
                        "role": "streamer",  # OBS 演出タブ用
                    }

                    self.message_bus.publish(
                        Events.CHAT_MESSAGE,
                        chat_data,
                        sender="chat_tab_streamer",
                    )
                    logger.info(f"📡 CHAT_MESSAGE published from ChatTab (streamer): {streamer_name}")
                except Exception as e:
                    logger.error(f"CHAT_MESSAGE publish エラー: {e}")

            # ✅ v17.5.3: _do_ai_request() を使用してキャラ設定を自動反映
            if self.message_bus:
                payload = {
                    "text": text,
                    "source": "streamer",
                    "user": "streamer",
                    "meta": {"tab": "chat", "route": "STREAMER_SEND"},
                }
                self._do_ai_request(payload, sender="chat_tab_streamer")

        except Exception as e:
            logger.error(f"STREAMER_SEND処理エラー: {e}")

    def _on_ai_status_update(self, payload: dict, **_) -> None:
        """
        MessageBus ハンドラ（ラッパー）: GUI Queue に積むだけ。
        実際の処理は _on_ai_status_update_impl で行う。
        """
        # 保険: gui_queue が存在しない場合は作成
        if not hasattr(self, "gui_queue") or self.gui_queue is None:
            import queue
            self.gui_queue = queue.Queue()
            logger.warning("⚠️ gui_queue が未初期化だったため作成しました（AI_STATUS）")
        self.gui_queue.put(("AI_STATUS_UPDATE", payload))

    def _on_ai_status_update_impl(self, payload: dict) -> None:
        """
        【GUI Queue 経由で呼ばれる】
        AI_STATUS_UPDATE を受けて、Chatタブ上部の「AI統合ステータス」ラベルと
        内部フラグ(_ai_connected, _ai_provider, _ai_model)を更新する。
        """
        try:
            logger.info(f"🔍 [Task C] _on_ai_status_update() 呼び出し開始: payload={payload}")

            # AIIntegrationManager から飛んでくる想定ペイロード:
            # {
            #   'provider': 'gemini',
            #   'model': 'gemini-2.5-flash',
            #   'has_api_key': True,
            #   'connector_available': True,
            #   'standalone_mode': False,
            #   'fallback_only': False,
            #   'reason': 'status_request',
            # }
            provider = str(
                payload.get("active")
                or payload.get("provider")
                or "-"
            )
            model = str(payload.get("model") or "-")
            logger.info(f"🔍 [Task C] provider={provider}, model={model}")

            has_key = payload.get("has_api_key", None)  # None or True or False
            connector_ok = bool(payload.get("connector_available", False))
            standalone = bool(payload.get("standalone_mode", False))
            fallback_only = bool(payload.get("fallback_only", False))
            is_fallback = bool(payload.get("is_fallback", False))  # ✅ v17.5: 実態フラグ
            reason = payload.get("reason") or ""

            # 内部状態を更新
            self._ai_provider = provider
            self._ai_model = model

            # ===== 正式な接続判定 =====
            # v17.5: is_fallback=True または provider='fallback' の場合は必ずフォールバック
            logger.info(f"🔍 [Task C] 接続判定開始: is_fallback={is_fallback}, connector_ok={connector_ok}, has_key={has_key}, standalone={standalone}, fallback_only={fallback_only}")
            if is_fallback or provider in ['fallback', 'local-echo', 'echo']:
                self._ai_connected = False
                status_text = "未接続"
                fg = "#AA0000"  # 赤系
                ai_state_text = f"フォールバック: {provider} / {model}"
                logger.info(f"🔍 [Task C] → フォールバック判定: _ai_connected=False")
            # - connector_available=True
            # - has_api_key が False 明示でない（None or True）
            # - standalone_mode ではない
            # - fallback_only ではない
            elif connector_ok and (has_key is None or has_key is True) and not standalone and not fallback_only:
                self._ai_connected = True
                status_text = f"{provider} / {model}（接続中）"
                fg = "#008800"  # 緑系
                ai_state_text = f"統合済み: {provider} / {model}"
                logger.info(f"🔍 [Task C] → 接続OK判定: _ai_connected=True")
            else:
                self._ai_connected = False
                status_text = "未接続"
                fg = "#AA0000"  # 赤系
                ai_state_text = f"フォールバック: {provider} / {model}"
                logger.info(f"🔍 [Task C] → その他（未接続）判定: _ai_connected=False")

            # ===== UIラベル反映 =====
            # v17.5.x: reason="test" の場合は UIラベルを変えない（テスト結果はログだけ）
            logger.info(f"🔍 [Task C] UIラベル更新チェック: reason={reason}, reason!='test'={reason != 'test'}")
            if reason != "test":
                # AIキャララベル更新（新規追加）
                has_label = hasattr(self, "ai_character_label") and self.ai_character_label
                logger.info(f"🔍 [Task C] ai_character_label存在チェック: {has_label}")
                if has_label:
                    try:
                        # AIキャラ表示名の決定（プロバイダ / モデル）
                        logger.info(f"🔍 [Task C] ラベルテキスト決定: _ai_connected={self._ai_connected}, provider={provider}")
                        if self._ai_connected and provider not in ['fallback', 'local-echo', 'echo']:
                            # プロバイダー名を整形
                            provider_display = {
                                'gemini': 'Gemini',
                                'openai': 'OpenAI',
                                'anthropic': 'Claude',
                            }.get(provider.lower(), provider.capitalize())

                            # "Gemini / gemini-2.5-flash" のような形式で表示
                            ai_char_text = f"{provider_display} / {model}"
                            ai_char_color = "#90EE90"  # 明るい緑
                            logger.info(f"🔍 [Task C] → 接続表示: {ai_char_text}")
                        else:
                            ai_char_text = "未接続"
                            ai_char_color = "#FF4444"  # 赤
                            logger.info(f"🔍 [Task C] → 未接続表示")

                        self.ai_character_label.config(text=ai_char_text, fg=ai_char_color)
                        logger.info(f"✅ [Task C] ai_character_label更新成功: {ai_char_text}")
                    except Exception as ui_e:
                        logger.warning(f"⚠️ [Task C] AIキャララベル更新失敗: {ui_e}", exc_info=True)

            # ログ出力（デバッグ用）
            logger.info(
                f"[AI_STATUS] connected={self._ai_connected} "
                f"provider={provider} model={model} "
                f"has_key={has_key} connector_ok={connector_ok} "
                f"is_fallback={is_fallback} reason={reason}"
            )

            # --- 重複チェック（状態変化がない場合はSYS行を出さない） ---
            current_status = (provider, model, self._ai_connected)
            last_status = getattr(self, "_last_ai_status", None)
            self._last_ai_status = current_status

            # v17.5: reason="test" の場合は特別扱い（テスト結果としてログ出力）
            if reason == "test":
                test_msg = f"🔍 接続テスト結果: {ai_state_text}"
                try:
                    self._append_system_line(test_msg, tag="SYS")
                except Exception:
                    pass
                return

            # 状態が前回と同じなら、SYS行の追記はスキップ（静かに内部だけ更新）
            if last_status == current_status:
                logger.debug(f"[AI_STATUS] 状態変化なし、SYS行スキップ: {current_status}")
                return

            # ここまで来たら「状態が変わった」とみなしてSYSログを追加
            try:
                # ⚠ fg= は渡さない。タグ "SYS" 側の色設定に任せる
                self._append_system_line(
                    f"🤖 SYS: 現在のAI統合状態 → {ai_state_text}",
                    tag="SYS",
                )
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"AI status update handling error: {e}")

    def _on_ai_test_result(self, payload: dict, **_) -> None:
        """AI_TEST_RESULT を受けて接続テスト結果を表示する。"""
        try:
            ok = bool(payload.get("ok"))
            provider = payload.get("provider") or "-"
            model = payload.get("model") or "-"
            msg = "✅ 接続テスト成功" if ok else "❌ 接続テスト失敗"
            text = f"[AI] {msg}: {provider} / {model}"
            if hasattr(self, "_log"):
                self._log(text)
            else:
                logger.info(text)
        except Exception as e:
            logger.warning(f"AI test result handling error: {e}")
            
    def _do_ai_request(self, payload: dict, sender: str = "chat_tab") -> None:
        """
        AI_REQUEST を MessageBus に投げる共通ルート。
        どこからでもこれを呼べば AIIntegrationManager に届く。

        v17.5.2: キャラ設定を自動的に追加
        v17.6+: character_name パラメータでキャラ別設定に対応
        """
        if not self.message_bus:
            logger.warning("⚠️ MessageBus が無いため AI_REQUEST を送信できません")
            return

        try:
            # ✅ v17.6+: character_name が指定されている場合は、そのキャラの設定を使用
            character_name = payload.get("character_name")

            # ✅ v17.5.2/v17.6+: キャラ設定を UnifiedConfigManager から取得して payload に追加
            if self.config_manager:
                try:
                    # v17.6+: character_name が指定されている場合は、そのキャラクターの設定を取得
                    if character_name:
                        logger.info(f"🎭 キャラクター '{character_name}' の設定を読み込みます")

                        # ai_characters から該当キャラの設定を取得
                        ai_characters = self.config_manager.get("ai_characters", {})
                        char_data = ai_characters.get(character_name, {})

                        if not char_data:
                            logger.warning(f"⚠️ キャラクター '{character_name}' が見つかりません。デフォルト設定を使用します。")
                            # デフォルト設定にフォールバック
                            character_name = None
                        else:
                            # キャラ固有の設定を取得
                            base_settings = char_data.get("base_settings", {})
                            personality_settings = char_data.get("personality", {})
                            streaming_settings = char_data.get("streaming", {})

                            # システムプロンプトの構築（複数ソースから）
                            system_prompt_parts = []

                            # 基本情報
                            if base_settings.get("personality"):
                                system_prompt_parts.append(f"性格: {base_settings['personality']}")
                            if base_settings.get("features"):
                                system_prompt_parts.append(f"特徴: {base_settings['features']}")

                            # 人格設定
                            if personality_settings.get("ai_relationship"):
                                system_prompt_parts.append(f"関係性: {personality_settings['ai_relationship']}")

                            # 配信スタイル
                            if streaming_settings.get("style"):
                                system_prompt_parts.append(f"配信スタイル: {streaming_settings['style']}")

                            # 特記事項
                            if base_settings.get("notes"):
                                system_prompt_parts.append(f"特記事項: {base_settings['notes']}")
                            if personality_settings.get("notes"):
                                system_prompt_parts.append(f"追加情報: {personality_settings['notes']}")

                            system_prompt = "\n".join(system_prompt_parts)

                            # キャラ設定を取得
                            personality = base_settings.get("personality", "")
                            ai_name = base_settings.get("display_name") or character_name
                            age = personality_settings.get("age", "")
                            speaking_style = base_settings.get("speaking_style", "")
                            background = personality_settings.get("background", "")

                            # 応答文字数制限（キャラ固有 or グローバル）
                            response_length_limit = base_settings.get("response_length_limit") or self.config_manager.get("ai.response_length_limit", 200)

                    # v17.5.2: デフォルト設定（character_name が無い場合、または見つからなかった場合）
                    if not character_name:
                        # システムプロンプト（最優先）
                        system_prompt = self.config_manager.get("ai.system_prompt", "")
                        if not system_prompt:
                            # ai.system_prompt がない場合は ai_personality から構築
                            system_prompt = self.config_manager.get("ai_personality.system_prompt", "")

                        # キャラ設定
                        personality = self.config_manager.get("ai_personality.basic_info.personality", "")
                        ai_name = self.config_manager.get("ai_personality.basic_info.name", "ぎゅるる")
                        age = self.config_manager.get("ai_personality.basic_info.age", "")
                        speaking_style = self.config_manager.get("ai_personality.basic_info.speaking_style", "")
                        background = self.config_manager.get("ai_personality.basic_info.background", "")

                        # ✅ v17.5.2: 応答文字数制限
                        response_length_limit = self.config_manager.get("ai.response_length_limit", 200)

                    # 応答文字数制限の検証
                    if not response_length_limit or not isinstance(response_length_limit, (int, float)):
                        response_length_limit = 200

                    # payload に追加（既存のキーは上書きしない）
                    payload.setdefault("system_prompt", system_prompt)
                    payload.setdefault("personality", personality)
                    payload.setdefault("ai_name", ai_name)
                    payload.setdefault("age", age)
                    payload.setdefault("speaking_style", speaking_style)
                    payload.setdefault("background", background)
                    payload.setdefault("response_length_limit", int(response_length_limit))

                    logger.debug(
                        f"🧩 キャラ設定をAI_REQUESTに追加: "
                        f"ai_name={ai_name}, personality={personality[:30] if personality else '(空)'}..., "
                        f"response_limit={response_length_limit}文字"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ キャラ設定の取得エラー（AI_REQUESTは続行）: {e}")

            # v17.3 の正式イベント名で送信
            self.message_bus.publish(Events.AI_REQUEST, payload, sender=sender)
            logger.info(
                f"🤖 AI_REQUEST 発行: sender={sender}, "
                f"text={payload.get('text') or payload.get('user_message') or ''}"
            )
        except Exception as e:
            logger.error(f"AI_REQUEST publish error: {e}")

    def _build_start_boundary_ui(self, parent):
        """
        返答開始ポイント（Start Boundary）のUIを作成
        - モード：接続時点 / 配信開始 / 任意の日時
        - 任意日時の入力欄（JST）
        - 今をセット / 適用 ボタン
        """
        # ラッパーフレーム
        frame = tk.LabelFrame(parent, text="返答開始ポイント（Start Boundary）", padx=8, pady=8)
        frame.pack(fill="x", padx=8, pady=8)

        # 設定のロード
        cfg = getattr(self, "config_manager", None)
        start_mode = "on_connect"
        since_ts_ms = 0
        try:
            if cfg:
                start_mode = cfg.get("chat.start_mode", "on_connect")
                since_ts_ms = int(cfg.get("chat.start_since_ts", 0) or 0)
        except Exception:
            pass

        # 変数
        self.start_mode_var = tk.StringVar(value=start_mode)
        # 任意日時（JST表示）の文字列変数
        self.since_dt_var = tk.StringVar(value=self._utc_ms_to_jst_str(since_ts_ms) if since_ts_ms > 0 else "")

        # ラジオボタン群（横並び）
        radios_frame = tk.Frame(frame)
        radios_frame.pack(fill="x")

        tk.Radiobutton(
            radios_frame, text="接続時点から（既定）", value="on_connect",
            variable=self.start_mode_var
        ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Radiobutton(
            radios_frame, text="配信の開始時点から", value="stream_start",
            variable=self.start_mode_var
        ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Radiobutton(
            radios_frame, text="任意の日時から（JST）", value="since_timestamp",
            variable=self.start_mode_var
        ).pack(side=tk.LEFT, padx=(0, 10))

        # 日時入力フィールドを同じ行に配置
        tk.Label(radios_frame, text="日時（JST, 例: 2025-10-27 21:00:30）").pack(side="left")
        entry = tk.Entry(radios_frame, textvariable=self.since_dt_var, width=24)
        entry.pack(side="left", padx=(6, 6))
        tk.Button(radios_frame, text="今をセット", command=self._set_now_to_since).pack(side="left", padx=(0, 6))
        tk.Button(radios_frame, text="適用", command=self._apply_start_boundary).pack(side="left")

    def _set_now_to_since(self):
        """『今をセット』：任意日時欄に現在(JST)を秒まで入れる"""
        now_jst = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
        self.since_dt_var.set(now_jst)

    def _apply_start_boundary(self):
        """
        『適用』：設定を保存→境界を再計算→UIに反映→（任意）バスに通知
        """
        try:
            mode = (self.start_mode_var.get() or "on_connect").strip()
            cfg = getattr(self, "config_manager", None)

            # 保存
            if cfg:
                cfg.set("chat.start_mode", mode)

                if mode == "since_timestamp":
                    # JST文字列 → UTC ms へ変換
                    ts_ms = self._jst_str_to_utc_ms(self.since_dt_var.get().strip())
                    cfg.set("chat.start_since_ts", int(ts_ms))
                else:
                    # 任意日時はクリアしておく（好みで保持でもOK）
                    cfg.set("chat.start_since_ts", 0)

                cfg.save()

            # 即時再計算（次の受信から有効）
            self._boundary_ts = _resolve_start_boundary(cfg if cfg else {}, stream_api=None)

            # 任意：メッセージバスで他タブへ通知（必要なら有効化）
            if hasattr(self, "message_bus") and self.message_bus:
                try:
                    self.message_bus.publish("CONFIG/START_BOUNDARY_UPDATED", {"mode": mode, "boundary_ts": self._boundary_ts})
                except Exception:
                    pass

            logger.info(f"[StartBoundary UI] 適用: mode={mode}, boundary_ts={self._boundary_ts}")
        except Exception as e:
            logger.error(f"[StartBoundary UI] 適用エラー: {e}")

    # ==== JST/UTC 変換ヘルパ ====

    def _jst_str_to_utc_ms(self, jst_str):
        """
        'YYYY-MM-DD HH:MM[:SS]' (JST) → UTC ms
        秒は省略可能（省略時は :00 扱い）
        不正値は現在時刻でフォールバック
        """
        try:
            if not jst_str:
                raise ValueError("empty string")
        
            jst_str = jst_str.strip()
        
            # 秒あり（HH:MM:SS）と秒なし（HH:MM）の両方に対応
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                try:
                    dt_jst = datetime.strptime(jst_str, fmt).replace(
                        tzinfo=timezone(timedelta(hours=9))
                    )
                    utc_ms = int(dt_jst.astimezone(timezone.utc).timestamp() * 1000)
                    logger.debug(f"[JST→UTC] {jst_str} → {utc_ms} ms (fmt={fmt})")
                    return utc_ms
                except ValueError:
                    continue  # 次のフォーマットを試す
        
            # どちらのフォーマットも失敗
            raise ValueError(f"日時フォーマット不正: {jst_str}")
        
        except Exception as e:
            logger.warning(f"日時変換エラー: {e} → 現在時刻にフォールバック")
            return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _utc_ms_to_jst_str(self, utc_ms):
        """
        UTC ms → 'YYYY-MM-DD HH:MM:SS' (JST)
        秒まで表示
        """
        try:
            if not utc_ms:
                return ""
            dt_utc = datetime.fromtimestamp(int(utc_ms) / 1000.0, tz=timezone.utc)
            jst_str = dt_utc.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
            return jst_str
        except Exception as e:
            logger.warning(f"UTC→JST変換エラー: {e}")
            return ""


    def _init_basic_config(self):
        if hasattr(self.master, 'title'):
            self.master.title("ぎゅるるボット v17.0 - AIとチャット(完全統合版)")
            self.master.geometry("1200x800")
            self.master.configure(bg='#2b2b2b')
            self.is_standalone = True
        else:
            try:
                if hasattr(self.master, 'configure'):
                    self.master.configure(bg='#2b2b2b')
            except Exception:
                pass
            self.is_standalone = False

        if self.config_manager and CONFIG_MANAGER_AVAILABLE:
            try:
                ai_enabled = self.config_manager.get('ai.enabled', True)
                voice_enabled = self.config_manager.get('voice.enabled', True)
                ai_prob_config = self.config_manager.get('ai.response_probability', 1.0)
                ai_prob_percent = int(ai_prob_config * 100) if isinstance(ai_prob_config, float) else int(ai_prob_config)
                logger.info(f"📖 設定読み込み: AI={ai_enabled}, 音声={voice_enabled}, 応答確率={ai_prob_percent}%")
            except Exception as e:
                logger.warning(f"⚠️ 設定読み込みエラー: {e} - デフォルト値使用")
                ai_enabled = True
                voice_enabled = True
                ai_prob_percent = 100
        else:
            ai_enabled = True
            voice_enabled = True
            ai_prob_percent = 100

        self.ai_enabled = tk.BooleanVar(value=ai_enabled)

        # ✅ v17.5.x 修正: 音声読み上げ設定を UnifiedConfig から読み込み
        # 粒度分割：配信者 / AI / 視聴者
        cfg = getattr(self, "config_manager", None)
        voice_read_streamer_default = True
        voice_read_ai_default = True
        voice_read_viewer_default = True
        # ✅ v17.6.1 修正: 条件チェックを保存時と統一
        if cfg and CONFIG_MANAGER_AVAILABLE:
            try:
                voice_read_streamer_default = bool(cfg.get("voice.read.streamer", True))
                voice_read_ai_default = bool(cfg.get("voice.read.ai", True))
                voice_read_viewer_default = bool(cfg.get("voice.read.viewer", True))
                logger.info(f"💾 音声読み上げ設定を読み込み: 配信者={voice_read_streamer_default}, AI={voice_read_ai_default}, 視聴者={voice_read_viewer_default}")
            except Exception as e:
                logger.warning(f"⚠️ 音声読み上げ設定の読み込みに失敗、デフォルト値を使用: {e}")

        self.voice_read_streamer = tk.BooleanVar(value=voice_read_streamer_default)
        self.voice_read_ai = tk.BooleanVar(value=voice_read_ai_default)
        self.voice_read_viewer = tk.BooleanVar(value=voice_read_viewer_default)

        # 音声読み上げ設定変更時のコールバック
        self.voice_read_streamer.trace_add('write', lambda *args: self._on_voice_setting_change('配信者', self.voice_read_streamer.get()))
        self.voice_read_ai.trace_add('write', lambda *args: self._on_voice_setting_change('AIキャラ', self.voice_read_ai.get()))
        self.voice_read_viewer.trace_add('write', lambda *args: self._on_voice_setting_change('視聴者', self.voice_read_viewer.get()))

        self.ai_probability = tk.IntVar(value=ai_prob_percent)

        cfg = getattr(self, "config_manager", None)
        if cfg:
            self._ai_enabled = bool(cfg.get("ai.enabled", True))
            try:
                self._ai_prob = int(cfg.get("ai.response_probability", 1.0) * 100)
            except Exception:
                self._ai_prob = 100
        else:
            self._ai_enabled = True
            self._ai_prob = 100

        self.processed_messages = set()
        self.stats = {'received_comments': 0, 'ai_responses': 0, 'voice_requests': 0, 'errors': 0}

    def _init_modules(self):
        """
        v17.3 仕様：
        Chatタブは AIConnector を直接保持しない。
        すべてのAI問い合わせは MessageBus 経由で AIIntegrationManager に委譲する。
        """
        logger.info("🔧 AI Connector 初期化（v17.3仕様）")

        # v17.2 の古い DI / Fallback ロジックは廃止
        self.ai_connector = None

        logger.info("✅ ChatTab: AIConnector を保持せず、MessageBus 経由に統一しました")

    def _init_color_tags(self):
        txt = self.chat_widget
        try:
            txt.tag_configure("user_streamer", foreground="#4FC3F7")
            txt.tag_configure("ai_fallback", foreground="#FFFFFF")
            txt.tag_configure("ai_gemini", foreground="#00C853")
            txt.tag_configure("meta_mono", foreground="#B0BEC5")
            logger.info("✅ 色分けタグ初期化完了(user_streamer/ai_fallback/ai_gemini)")
        except Exception as e:
            logger.debug(f"tag_configure error: {e}")

    def _append_chat_colored(self, prefix: str, text: str, *, role: str = "system", provider: str = None):
        # 旧UI（当面残す）。新UIは ChatDisplayColorized.add_formatted_message() 経由で揃え表示。
        if role == "user":
            tag = "user_streamer"
        elif role == "ai":
            tag = "ai_gemini" if (str(provider or "").lower().startswith("gemini")) else "ai_fallback"
        else:
            tag = "meta_mono"

        try:
            line = f"{prefix} {text}\n"
            self.chat_widget.config(state=tk.NORMAL)
            self.chat_widget.insert("end", line, (tag,))
            self.chat_widget.see("end")
            self.chat_widget.config(state=tk.DISABLED)
        except Exception as e:
            logger.error(f"_append_chat_colored error: {e}")
            
    def _append_system(self, message: str, tag: str = "SYS") -> None:
        """
        システム系メッセージを統合チャットに追加するヘルパー。
        ChatDisplayColorized があればそちらを優先し、なければ logger にフォールバック。
        v17.3.1 Phase 1.2: プレフィックス除去を強化（複数パターン対応）
        """
        try:
            # ✅ ChatDisplayColorized 経由で統合チャットに表示
            if hasattr(self, "chat_display") and self.chat_display:
                clean = (message or "").strip()
                # 旧フォーマットのプレフィックスを完全に除去（二重表示防止）
                # ※ ChatDisplayColorized が自動的に "⚙️SYS システム：" を付加するため、
                #    元メッセージからは完全に除去する
                prefixes_to_remove = [
                    "⚙️SYS システム：", "⚙️ SYS システム：",
                    "🤖 SYS システム：", "🤖SYS システム：",
                    "⚙️SYS：", "🤖SYS：",
                    "⚙️ SYS: ", "⚙️SYS: ",
                    "🤖 SYS: ", "🤖SYS: ",
                    "SYS: ", "SYS：",
                ]
                for prefix in prefixes_to_remove:
                    clean = clean.replace(prefix, "")
                clean = clean.strip()

                data = {
                    "username": "システム",
                    "message": clean,
                    "platform": "system",
                    "message_type": "system",
                }
                self.chat_display.add_formatted_message(data)
            else:
                # GUIがまだ整っていない場合はログだけ
                logger.info(message)
        except Exception as e:
            logger.error(f"SYSメッセージ表示エラー: {e}")
            logger.info(message)

    def _append_system_line(self, message: str, tag: str = "SYS") -> None:
        """
        _append_system のエイリアス（後方互換性のため）
        """
        self._append_system(message, tag)

    def is_ai_enabled(self) -> bool:
        """
        AI機能が有効化されているかを返す
        """
        try:
            if hasattr(self, "ai_enabled"):
                return bool(self.ai_enabled.get())
            return False
        except Exception:
            return False

    def _get_current_provider(self) -> str:
        try:
            ai = getattr(self, "ai_connector", None)
            if not ai:
                return ""
            prov = getattr(ai, "current", None)
            if prov:
                return str(prov).lower()
            if hasattr(ai, "current_provider"):
                cp = getattr(ai, "current_provider", None)
                if hasattr(cp, "name"):
                    return str(cp.name).lower()
            return ""
        except Exception:
            return ""

    def _call_ai(self, text: str) -> str:
        """
        実際にAIコネクタを叩いてテキストを取得する。
        - ここでは「文字列を返す」だけに専念する。
        - MessageBus への AI_RESPONSE 送信は AIIntegrationManager 側の仕事。
        """
        text = (text or "").strip()
        if not text:
            return ""

        # 1) app_instance / self.ai_connector を優先して取得
        ai_conn = getattr(self, "ai_connector", None)

        if ai_conn is None and hasattr(self, "app_instance") and self.app_instance:
            ai_conn = getattr(self.app_instance, "ai_connector", None)

        if ai_conn is None and hasattr(self, "app_instance") and self.app_instance:
            ai_conn = getattr(self.app_instance, "ai_manager", None)

        # 2) AIコネクタが使えればそれを優先
        try:
            if ai_conn is not None and hasattr(ai_conn, "generate_reply"):
                return ai_conn.generate_reply(prompt=text, user="ユーザー")
        except Exception as e:
            logger.warning(f"AI コネクタ呼び出しエラー: {e}")

        # 3) それでもダメならローカルの簡易応答を返す
        return self._build_fallback_reply(text)

    def _build_complete_ui(self):
        main_container = ttk.Frame(self.frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # 1. AIステータス
        self._create_connection_status_panel(main_container)
        # 2. 返答開始ポイント
        self._build_start_boundary_ui(main_container)
        # 3. 統合チャット表示
        self._create_chat_display_area(main_container)
        # 4. メッセージ送信・AI制御・音声制御
        self._create_control_panel(main_container)

    def _create_connection_status_panel(self, parent):
        """
        v17.5.x: AIステータスパネル
        - 1段目：AIキャラ表示ラベル（プロバイダ/モデル）＋テストボタン2つ
        - 2段目：カウンター表示のみ
        """
        status_frame = ttk.LabelFrame(parent, text="📡 AIステータス", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        # 1段目：AIキャラ表示 + テストボタン（左寄せ）
        top_row = ttk.Frame(status_frame)
        top_row.pack(fill=tk.X, pady=(0, 8), anchor="w")

        # AIキャラ ステータス（左端）
        ai_char_frame = tk.Frame(top_row, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1)
        ai_char_frame.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(ai_char_frame, text="AIキャラ：", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.ai_character_label = tk.Label(ai_char_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"))
        self.ai_character_label.pack(side=tk.LEFT, padx=(0, 5))

        # MessageBusテストボタン
        test_btn = tk.Button(top_row, text="📡 MessageBusテスト", bg="#2196F3", fg="white", font=("Arial", 9), command=self.send_test_message)
        test_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 音声テストボタン
        voice_test_btn = tk.Button(top_row, text="🎤 音声テスト", bg="#9C27B0", fg="white", font=("Arial", 9), command=self._test_voice_singleton)
        voice_test_btn.pack(side=tk.LEFT)

        # 2段目：カウント表示のみ（左寄せ）
        counter_row = ttk.Frame(status_frame)
        counter_row.pack(fill=tk.X, anchor="w")

        # カウント表示（左端）
        self.stats_label = tk.Label(counter_row, text="受信: 0 | AI応答: 0 | 音声: 0 | エラー: 0", fg="#FFD700", bg="#2b2b2b", font=("Arial", 9))
        self.stats_label.pack(side=tk.LEFT)

    def _create_chat_display_area(self, parent):
        chat_frame = ttk.LabelFrame(parent, text="💬 統合チャット表示(色分け対応版)", padding="10")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.chat_widget = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            height=20,
            bg="#1e1e1e",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=("Consolas", 10) if os.name == 'nt' else ("monospace", 10),
            state=tk.DISABLED,
            selectbackground="#444444",
            selectforeground="#ffffff"
        )
        self.chat_widget.pack(fill=tk.BOTH, expand=True)

        self.chat_display = ChatDisplayColorized(self.chat_widget)
        self._setup_chat_context_menu()
        self._show_startup_message()

    def _setup_chat_context_menu(self):
        self.chat_context_menu = tk.Menu(self.chat_widget, tearoff=0)
        self.chat_context_menu.add_command(label="コピー", command=self._copy_selected_text)
        self.chat_context_menu.add_command(label="全選択", command=self._select_all_text)
        self.chat_context_menu.add_command(label="クリア", command=self._clear_chat)
        self.chat_context_menu.add_separator()
        self.chat_context_menu.add_command(label="ログ保存", command=self._save_chat_log)
        self.chat_widget.bind("<Button-3>", self._show_context_menu)

    def _create_control_panel(self, parent):
        control_frame = ttk.LabelFrame(parent, text="✏️ メッセージ送信・AI制御・音声制御", padding="10")
        control_frame.pack(fill=tk.X)

        input_frame = ttk.Frame(control_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        self.message_entry = tk.Entry(
            input_frame,
            font=("Consolas", 11) if os.name == 'nt' else ("monospace", 11),
            bg="#2d2d2d",
            fg="#ffffff",
            insertbackground="#ffffff"
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.message_entry.bind("<Return>", self._send_message)

        send_btn = tk.Button(input_frame, text="📤 送信", command=self._send_message, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=8)
        send_btn.pack(side=tk.RIGHT)

        self._create_ai_voice_controls(control_frame)

    def _build_context_menu(self):
        try:
            self.chat_context_menu = tk.Menu(self.master, tearoff=0)
            self.chat_context_menu.add_command(label="コピー", command=self._ctx_copy_selection)
            self.chat_context_menu.add_command(label="全選択", command=self._ctx_select_all)
        except Exception as e:
            logger.error(f"❌ コンテキストメニュー生成エラー: {e}")

    def _show_context_menu(self, event):
        try:
            self._last_context_target = event.widget
            if hasattr(self.chat_context_menu, "tk_popup"):
                self.chat_context_menu.tk_popup(event.x_root, event.y_root)
            else:
                self.chat_context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"❌ コンテキストメニュー表示エラー: {e}")
        finally:
            try:
                self.chat_context_menu.grab_release()
            except Exception:
                pass

    def _get_active_text_widget(self):
        cand = getattr(self, "_last_context_target", None)
        if cand is not None:
            return cand
        for name in ("chat_text", "chat_display_text", "chat_display", "txt_chat"):
            w = getattr(self, name, None)
            if w is not None:
                return w
        return None

    def _ctx_copy_selection(self):
        try:
            w = self._get_active_text_widget()
            if w is None:
                return
            text = None
            try:
                text = w.get("sel.first", "sel.last")
            except Exception:
                pass
            if text is None:
                try:
                    text = w.selection_get()
                except Exception:
                    pass
            if text:
                self.master.clipboard_clear()
                self.master.clipboard_append(text)
                logger.info("📋 クリップボードへコピー")
        except Exception as e:
            logger.error(f"❌ コピー失敗: {e}")

    def _ctx_select_all(self):
        try:
            w = self._get_active_text_widget()
            if w is None:
                return
            try:
                w.tag_add("sel", "1.0", "end-1c")
                w.mark_set("insert", "1.0")
                w.see("insert")
            except Exception:
                try:
                    w.selection_range(0, "end")
                    w.icursor(0)
                except Exception:
                    pass
            logger.info("🔎 全選択")
        except Exception as e:
            logger.error(f"❌ 全選択失敗: {e}")

    def _create_ai_voice_controls(self, parent):
        """
        画面上部の操作パネル（並び順）
        [音声読み上げ] → [AI応答モード] → [応答確率スライダー]
        ・ラベルフレームの見出しは「音声読み上げ」「AI応答」に限定
        ・応答確率のラベル文字は廃止（スライダー自身に％表示が出る想定）
        """
        frm = tk.Frame(parent, bg="#222222")
        frm.pack(fill=tk.X, padx=6, pady=4)

        # --- 音声読み上げ（3チェック） ---
        voice_box = tk.LabelFrame(frm, text="音声読み上げ", bg="#222222", fg="#E0E0E0")
        voice_box.pack(side=tk.LEFT, padx=6)

        tk.Checkbutton(
            voice_box, text="配信者", variable=self.voice_read_streamer,
            bg="#222222", fg="#E0E0E0", selectcolor="#333333"
        ).pack(side=tk.LEFT, padx=6, pady=4)

        tk.Checkbutton(
            voice_box, text="AIキャラ", variable=self.voice_read_ai,
            bg="#222222", fg="#E0E0E0", selectcolor="#333333"
        ).pack(side=tk.LEFT, padx=6, pady=4)

        tk.Checkbutton(
            voice_box, text="視聴者", variable=self.voice_read_viewer,
            bg="#222222", fg="#E0E0E0", selectcolor="#333333"
        ).pack(side=tk.LEFT, padx=6, pady=4)

        # --- AI応答モード（ラジオ：キーワード反応 / 全返答） ---
        ai_box = tk.LabelFrame(frm, text="AI応答", bg="#222222", fg="#E0E0E0")
        ai_box.pack(side=tk.LEFT, padx=6)

        # self.ai_reply_mode は __init__ で初期化済み

        tk.Radiobutton(
            ai_box, text="キーワード反応", variable=self.ai_reply_mode, value=0,
            bg="#222222", fg="#E0E0E0", selectcolor="#333333"
        ).pack(side=tk.LEFT, padx=6, pady=4)

        tk.Radiobutton(
            ai_box, text="全返答", variable=self.ai_reply_mode, value=1,
            bg="#222222", fg="#E0E0E0", selectcolor="#333333"
        ).pack(side=tk.LEFT, padx=6, pady=4)

        # --- 応答確率（ラベル無し、フレームだけ。%はスライダー側が表示） ---
        prob_box = tk.LabelFrame(frm, text="応答確率", bg="#222222", fg="#E0E0E0")
        prob_box.pack(side=tk.LEFT, padx=6)

        # 追加の動的な数値ラベルは作らない
        self.ai_prob_scale = tk.Scale(
            prob_box, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.ai_probability,
            command=lambda v: self._on_probability_change(),  # Phase 2: スライダー移動時にコールバック
            bg="#222222", fg="#E0E0E0",
            troughcolor="#333333",
            highlightthickness=0,
            length=220
        )
        self.ai_prob_scale.pack(side=tk.LEFT, padx=6, pady=2)

        # --- 音声制御（音量・ミュート・停止・キュークリア）---
        audio_control_box = tk.LabelFrame(frm, text="音声制御", bg="#222222", fg="#E0E0E0")
        audio_control_box.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)

        audio_row = tk.Frame(audio_control_box, bg="#222222")
        audio_row.pack(fill=tk.X, padx=6, pady=4)

        tk.Label(audio_row, text="音量", bg="#222222", fg="#E0E0E0").pack(side=tk.LEFT, padx=(0, 4))

        self.volume_scale = tk.Scale(
            audio_row,
            from_=0,
            to=200,
            orient=tk.HORIZONTAL,
            command=self._on_volume_changed,
            bg="#222222",
            fg="#E0E0E0",
            troughcolor="#333333",
            highlightthickness=0,
            length=120
        )
        self.volume_scale.set(self.shared_volume_var.get())
        self.volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.mute_check = tk.Checkbutton(
            audio_row,
            text="ミュート",
            variable=self.shared_mute_var,
            command=self._on_mute_toggled,
            bg="#222222",
            fg="#E0E0E0",
            selectcolor="#333333"
        )
        self.mute_check.pack(side=tk.LEFT, padx=(0, 8))

        # ミュート説明行（グローバルミュートの説明）
        mute_desc_row = tk.Frame(audio_control_box, bg="#222222")
        mute_desc_row.pack(fill=tk.X, padx=6, pady=(0, 4))
        tk.Label(
            mute_desc_row,
            text="※配信全体に適用されます（音声制御タブと共通）",
            bg="#222222",
            fg="#999999",
            font=("Arial", 8)
        ).pack(side=tk.LEFT, padx=(0, 0))

        self.btn_stop = tk.Button(
            audio_row,
            text="停止",
            command=self._on_voice_stop,
            bg="#FF5722",
            fg="white",
            font=("Arial", 9),
            width=5
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_clear = tk.Button(
            audio_row,
            text="クリア",
            command=self._on_voice_clear_queue,
            bg="#FF9800",
            fg="white",
            font=("Arial", 9),
            width=5
        )
        self.btn_clear.pack(side=tk.LEFT)

        # --- 音声制御タブからの変更を受け取る（依頼書⑤: 双方向同期） ---
        def _on_shared_volume_change(*_):
            """音声制御タブで音量が変更されたときにスライダーを更新"""
            try:
                new_val = self.shared_volume_var.get()
                # 無限ループ防止のため値が異なる場合のみ更新
                if self.volume_scale.get() != new_val:
                    self.volume_scale.set(new_val)
            except Exception as e:
                logger.debug(f"共有音量変数からのスライダー更新エラー: {e}")

        self.shared_volume_var.trace('w', _on_shared_volume_change)

    def _setup_messagebus_integration(self):
        """
        MessageBus イベント購読の一元管理メソッド
        Phase 1.3: 二重購読を完全に防止
        """
        logger.debug("🐛 [DEBUG] _setup_messagebus_integration 開始")
        if not self.message_bus:
            logger.info("📡 MessageBus未設定 - スタンドアロンモード")
            return

        # Phase 1.3: 二重購読防止ガード
        if self._messagebus_integrated:
            logger.warning("⚠️ MessageBus統合は既に完了しています（二重実行防止）")
            return

        try:
            # 🐛 DEBUG: subscribe 呼び出しログ（インスタンスID付き）
            logger.info(
                f'🐛 [DEBUG] _setup_messagebus_integration 開始: '
                f'id(self)={id(self)}, id(message_bus)={id(self.message_bus)}'
            )
            logger.debug("🐛 [DEBUG] CHAT_MESSAGE, AI_RESPONSE, ONECOMME_COMMENT を購読します")

            # v17.3.1: 必要最小限の3イベントのみ購読
            self.message_bus.subscribe(Events.CHAT_MESSAGE, self._on_chat_message)
            logger.info("🐛 [DEBUG] CHAT_MESSAGE 購読完了")

            self.message_bus.subscribe(Events.AI_RESPONSE, self._on_ai_response)
            logger.info(f'🐛 [DEBUG] AI_RESPONSE 購読完了: handler={self._on_ai_response}')

            self.message_bus.subscribe(Events.ONECOMME_COMMENT, self._on_onecomme_comment)
            logger.info("🐛 [DEBUG] ONECOMME_COMMENT 購読完了")

            # v17: 配信者プロフィール更新イベントを購読
            self.message_bus.subscribe(Events.STREAMER_PROFILE_UPDATE, self._on_streamer_profile_update)
            logger.info("🐛 [DEBUG] STREAMER_PROFILE_UPDATE 購読完了")

            # ★ AIステータス更新イベントを購読（二重購読を防ぐため、既に購読済みでない場合のみ）
            if not self._ai_status_subscribed:
                self.message_bus.subscribe("AI_STATUS_UPDATE", self._on_ai_status_update)
                logger.info("🐛 [DEBUG] AI_STATUS_UPDATE 購読完了")

            self._publish_tab_ready()
            self._messagebus_integrated = True  # ガードフラグセット

            # ★ Chatタブ初期化完了後に一度だけステータス問い合わせ
            try:
                self.message_bus.publish(
                    "AI_STATUS_REQUEST",
                    {"reason": "startup"},
                    sender="tab_chat",
                )
                logger.info("🛰 AI_STATUS_REQUEST を送信しました（reason='startup'）")
            except Exception as req_err:
                logger.exception(f"AI_STATUS_REQUEST 送信に失敗しました: {req_err}")

            logger.info("✅ MessageBus購読: CHAT_MESSAGE / AI_RESPONSE / ONECOMME_COMMENT / AI_STATUS_UPDATE")
            logger.debug(f"🐛 [DEBUG] ChatApp インスタンスID: {id(self)}")
        except Exception as e:
            logger.error(f"❌ MessageBus統合エラー: {e}")

    def _show_startup_message(self) -> None:
        """
        起動時にチャット欄へ状態サマリを1度だけ表示。
        v17.0～v17.3 用の共通フォーマット。
        """
        try:
            # 応答確率
            try:
                prob = int(self.ai_probability.get())
            except Exception:
                prob = 100

            voice = "利用可能" if self.voice_manager else "利用不可"
            cfg = "利用可能" if self.config_manager else "利用不可"
            bus = "接続済み" if self.message_bus else "未接続"

            ai_state = "統合済み" if getattr(self, "_ai_connected", False) else "フォールバック"
            provider = getattr(self, "_ai_provider", "-") or "-"
            model = getattr(self, "_ai_model", "-") or "-"

            lines = [
                "⚙️SYS システム：🎨 AIとチャット v17.0 が起動しました!",
                f"📊 応答確率: {prob}% (設定読み込み完了)",
                f"🎤 VoiceManager: {voice}",
                f"⚙️ ConfigManager: {cfg}",
                f"📡 MessageBus: {bus}",
                f"🤖 AI統合: {ai_state} ({provider} / {model})",
                "✅ 媒体別色分け機能対応済み",
                "🎨 配信者(水色)・AI Gemini(緑)・その他(白)",
                "💬 メッセージを入力してテストしてください!",
            ]

            for line in lines:
                # ここも fg= は渡さない。タグ "SYS" だけ指定
                self._append_system_line(line, tag="SYS")

        except Exception as e:
            logger.warning(f"startup message show error: {e}")

    def _test_voice_singleton(self):
        """
        🎤 音声テストボタン用の安全テスター
        優先度:
          1) MessageBus へ VOICE_REQUEST を発行（購読者がいれば再生）
          2) フォールバックで VoiceManager Singleton を直接呼び出し

        v17.5.4 (Task D): チャット表示を追加
        """
        try:
            sample_text = "ボイスのテストです。聞こえていますか？"

            # --- チャット表示追加 (Task D) ---
            try:
                self._append_system_line(f"🎤 音声テスト: {sample_text}", tag="SYS")
            except Exception as e:
                logger.debug(f"チャット表示追加失敗: {e}")

            # --- 1) MessageBus 経由 ---
            published = False
            try:
                if getattr(self, "message_bus", None):
                    try:
                        from shared import event_types as _evt
                        evt_name = getattr(_evt, "VOICE_REQUEST", "VOICE_REQUEST")
                    except Exception:
                        evt_name = "VOICE_REQUEST"

                    payload = {
                        "text": sample_text,
                        "username": "System",
                        "priority": "normal",
                        "source": "chat_tab_test",
                    }
                    self.message_bus.publish(evt_name, payload, sender="chat_app")
                    logger.info("🎤 VOICE_REQUEST 発行（テスト）: %s", sample_text)
                    published = True
            except Exception as e:
                logger.debug("Bus経由 VOICE_REQUEST 発行に失敗: %s", e)

            # --- 2) 直接呼び出し（フォールバック） ---
            direct_ok = False
            try:
                try:
                    from shared.voice_manager_singleton import speak_text as _speak_text
                    _speak_text(text=sample_text, username="System")
                    logger.info("🔊 VoiceManager.speak_text 直接呼び出し成功")
                    direct_ok = True
                except Exception as e_st:
                    logger.debug("speak_text 呼び出し失敗: %s", e_st)
                    from shared import voice_manager_singleton as _vm
                    vm = getattr(_vm, "get_instance", None)
                    vm = vm() if callable(vm) else getattr(_vm, "voice_manager", None) or getattr(_vm, "VOICE_MANAGER", None) or _vm

                    for attr in ("speak", "say", "enqueue", "enqueue_tts", "request"):
                        fn = getattr(vm, attr, None)
                        if callable(fn):
                            try:
                                fn(sample_text)
                                logger.info("🔊 VoiceManager 直接呼び出し成功: %s()", attr)
                                direct_ok = True
                                break
                            except Exception as inner_e:
                                logger.debug("VoiceManager.%s 呼び出し失敗: %s", attr, inner_e)
            except Exception as e:
                logger.debug("VoiceManager 直接呼び出し準備失敗: %s", e)

            if not published and not direct_ok:
                try:
                    messagebox.showinfo(
                        "音声テスト",
                        "VOICE_REQUEST の購読者が見つからず、VoiceManager の直接呼び出しも失敗しました。\n"
                        "メインアプリ経由で起動するか、音声系の購読/初期化をご確認ください。"
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.error("❌ _test_voice_singleton エラー: %s", e)

    # ===== イベントハンドラー =====
    def _on_chat_message(self, data, sender=None):
        """
        MessageBus ハンドラ（ラッパー）: GUI Queue に積むだけ。
        実際の処理は _on_chat_message_impl で行う。
        """
        # 保険: gui_queue が存在しない場合は作成
        if not hasattr(self, "gui_queue") or self.gui_queue is None:
            import queue
            self.gui_queue = queue.Queue()
            logger.warning("⚠️ gui_queue が未初期化だったため作成しました（CHAT_MESSAGE）")
        self.gui_queue.put(("CHAT_MESSAGE", data))

    def _on_chat_message_impl(self, data, sender=None):
        """
        【GUI Queue 経由で呼ばれる】
        CHAT_MESSAGE の表示処理。
        """
        try:
            logger.debug(f"[DEBUG] _on_chat_message 呼び出し: data={data}, sender={sender}")
            logger.info(f"[ChatTab Debug] CHAT_MESSAGE受信確認: {data}")
            username = data.get("username") or data.get("user") or "unknown"
            text = data.get("text") or data.get("message") or ""
            service = data.get("service") or data.get("platform") or "manual"
            source = data.get("source") or "chat"
            if not text:
                logger.debug("[ChatTab Debug] 空のテキストのため処理スキップ")
                return

            # 新UIで表示
            self.chat_display.add_formatted_message({
                "username": username,
                "message": text,          # ← 'text' ではなく 'message' にする
                "platform": service or "manual",
                "message_type": "streamer"
            })
            logger.info("💬 CHAT_MESSAGE表示: %s: %s", username, text)

            # カウンター更新
            self.stats['received_comments'] += 1
            self._update_stats_display()

            # 配信者の読み上げ
            if self.voice_read_streamer.get():
                self._send_voice_request(text, username, role='streamer')

            # AI自動返信（確率/キーワードは AIキャラ設定タブで）
            self._maybe_ai_auto_reply(text, source=source)

        except Exception as e:
            logger.error(f"❌ _on_chat_message エラー: {e}")
            self.stats['errors'] += 1
            self._update_stats_display()

    def _on_ai_response(self, data, sender=None):
        """
        MessageBus ハンドラ（ラッパー）: GUI Queue に積むだけ。
        実際の処理は _on_ai_response_impl で行う。
        """
        # 保険: gui_queue が存在しない場合は作成
        if not hasattr(self, "gui_queue") or self.gui_queue is None:
            import queue
            self.gui_queue = queue.Queue()
            logger.warning("⚠️ gui_queue が未初期化だったため作成しました（AI_RESPONSE）")
        self.gui_queue.put(("AI_RESPONSE", data))

    def _on_ai_response_impl(self, data, sender=None):
        """
        【GUI Queue 経由で呼ばれる】
        AI応答表示のみ（読み上げは行わない）

        v17.3.1 導線ルール:
        - VOICE_REQUEST は AIIntegrationManager が一括発行
        - tab_chat は表示のみを担当（二重発行を防止）

        v17 Refactor: 重複応答ガードについて
        - 過去の問題: Gemini仮想応答が2行出る（"Userさん" と "ユーザーさん" で別々に発行）
        - 現在の状態: 上流（AIIntegrationManager）での発行は一本化済み
        - このガードの役割: 念のための保険（上流で万が一重複発行された場合の防御）
        - 将来的な対応: 二重応答が1週間以上発生しなければ削除検討可能
        """
        try:
            # ⚠️ v17 保険: 念のための重複チェック（連続する同一または類似のAI応答をスキップ）
            # 上流（AIIntegrationManager）での発行が安定したら削除可能
            ts = data.get("ts")
            ai_text_check = data.get("ai_response") or data.get("text") or ""

            if ts and ai_text_check:
                # v17.5: ユーザー名部分を正規化してから比較（"Userさん" / "ユーザーさん" 問題を解決）
                import re
                normalized_text = re.sub(
                    r"(\[.*?\])\s+.*?さん、",
                    r"\1 <user>さん、",
                    ai_text_check
                )
                text_prefix = normalized_text[:50]
                last_ts = getattr(self, "_last_ai_response_ts", None)
                last_prefix = getattr(self, "_last_ai_response_text_prefix", None)

                # 同じ ts または 0.5秒以内 & 先頭50文字が同じ
                if last_ts and last_prefix:
                    time_diff = abs(ts - last_ts) if ts and last_ts else 999
                    if ts == last_ts or (time_diff < 0.5 and text_prefix == last_prefix):
                        logger.debug(f"[AI_RESPONSE] 重複検出、スキップ: ts={ts}, text_prefix={text_prefix[:30]}...")
                        return

                self._last_ai_response_ts = ts
                self._last_ai_response_text_prefix = text_prefix

            # 🐛 DEBUG: AI_RESPONSE 受信ログ（uuidで追跡）
            import uuid
            resp_id = str(uuid.uuid4())[:8]
            logger.info(
                f'🐛 [DEBUG {resp_id}] _on_ai_response 呼び出し: '
                f'sender={sender}, data keys={list(data.keys() if data else [])}, '
                f'インスタンスID={id(self)}'
            )

            # ✅ v17.6+: AI_RESPONSEのpayloadから実際のキャラ名を取得
            ai_name = (
                data.get("username") or
                data.get("ai_name") or
                (self.ai_display_name.get() if hasattr(self, "ai_display_name") else "ぎゅるる")
            )
            ai_text = data.get("ai_response") or data.get("text") or ""
            platform = (data.get("platform") or "ai").lower()

            # 🐛 DEBUG: 抽出したテキスト
            logger.info(f'🐛 [DEBUG {resp_id}] ai_text="{ai_text[:30]}...", ai_name={ai_name}')

            if not ai_text:
                logger.info(f'🐛 [DEBUG {resp_id}] ai_text が空のため処理スキップ')
                return

            # 宛先ユーザー（元コメントの送り主）
            original_username = data.get("original_username") or ""
            logger.info(f'🐛 [DEBUG {resp_id}] original_username={original_username}')

            # 配信者名の取得（配信者設定タブから）
            streamer_name = "配信者"
            try:
                if hasattr(self, "config_manager") and self.config_manager:
                    streamer_name = self.config_manager.get("streamer.display_name", "配信者")
            except Exception as e:
                logger.debug(f"配信者名取得エラー: {e}")

            # original_usernameが"User"の場合は配信者名に置き換え
            display_target = original_username
            if original_username and original_username.lower() in ("user", "ユーザー"):
                display_target = streamer_name

            # 表示用メッセージを組み立てる
            display_message = ai_text
            if display_target:
                # 1行目に「＠名前」
                # 2行目以降にコメント本文を表示（2行目の頭を少しインデント）
                indent = "　"  # 全角スペース1つでインデント
                ai_lines = ai_text.splitlines() or [ai_text]
                if ai_lines:
                    ai_lines[0] = indent + ai_lines[0]
                display_message = f"＠{display_target}\n" + "\n".join(ai_lines)

            # 🐛 DEBUG: 表示前ログ
            logger.info(f'🐛 [DEBUG {resp_id}] chat_display.add_formatted_message 呼び出し前')

            self.chat_display.add_formatted_message({
                "username": ai_name,
                "message": display_message,
                "platform": "ai",
                "message_type": "ai",
            })

            # 🐛 DEBUG: 表示後ログ
            logger.info(f'🐛 [DEBUG {resp_id}] chat_display.add_formatted_message 呼び出し後')
            logger.info("💬 AI応答表示（宛先: %s）", original_username)

            # カウンター更新
            self.stats['ai_responses'] += 1
            self._update_stats_display()

            # ✅ v17.3.1: Chatタブは表示のみ、VOICE_REQUEST は AIIntegrationManager が発行
            # （VOICE_REQUEST 発行処理は削除 - ルールブック準拠）

        except Exception as e:
            logger.error("❌ _on_ai_response エラー: %s", e)
            self.stats['errors'] += 1
            self._update_stats_display()

    def _on_user_join(self, data, sender=None):
        try:
            username = data.get('username', '匿名')
            is_first_time = data.get('is_first_time', False)
            join_msg = {
                'username': 'システム',
                'message': f"👋 {username}さんが参加しました!" + (" (初回参加)" if is_first_time else ""),
                'message_type': 'system',
                'platform': 'system'
            }
            self.chat_display.add_formatted_message(join_msg)
            if is_first_time and self.voice_read_viewer.get():
                self._send_voice_request(f"初回参加の{username}さん、ようこそ!", "システム")
        except Exception as e:
            logger.error(f"❌ ユーザー参加イベント処理エラー: {e}")

    def _on_onecomme_comment(self, data, sender=None):
        """
        OneCommeからの受信コメント（互換ラッパ）
        v17.3 では _on_onecomme_comment_v173() に委譲する。
        旧バージョン向けのロジックは _on_onecomme_comment_legacy などに退避推奨。
        """
        handler = getattr(self, "_on_onecomme_comment_v173", None)
        if callable(handler):
            return handler(data, sender=sender)

        # v17.2 以前などで v173 実装が無い場合は何もしない
        logger.warning(
            "⚠️ _on_onecomme_comment_v173 が見つからないため、ONECOMME_COMMENT を無視しました"
        )

    def _on_streamer_profile_update(self, payload, sender=None):
        """
        配信者プロフィール更新イベントを受信したときの処理（v17統一イベント）。

        MessageBus からは h(data, sender=sender) という形で呼ばれるので、
        第1引数=payload, 第2引数=sender (キーワード引数) の順で受け取る。
        """
        if payload is None:
            logger.warning("[ChatTab] STREAMER_PROFILE_UPDATE 受信: payload が None です")
            return

        name = payload.get("name", "")
        platform = payload.get("platform", "")
        reason = payload.get("reason", "")

        logger.info(
            "[ChatTab] STREAMER_PROFILE_UPDATE 受信 sender=%s name=%s platform=%s reason=%s",
            sender,
            name,
            platform,
            reason,
        )

        # 将来的にはここでチャット内のプロフィールプレビューなどに反映する想定。

    def _should_tts(self, role: str, platform: str) -> bool:
        """
        役割(role)とプラットフォームから読み上げ対象を判定
        """
        try:
            if role == "ai":
                return bool(getattr(self, "voice_read_ai", None) and self.voice_read_ai.get())
            elif role == "streamer":
                return bool(getattr(self, "voice_read_streamer", None) and self.voice_read_streamer.get())
            elif role == "viewer":
                return bool(getattr(self, "voice_read_viewer", None) and self.voice_read_viewer.get())
            return False
        except Exception as e:
            logger.error(f"❌ _should_tts エラー: {e}")
            return False

    # ===== AI自動返信 =====
    def _should_call_ai(self, text: str):
        """
        Phase 2-2: AI応答条件の判定
        v17.6+: 複数AIキャラに対応

        応答モード（ai.response_mode）に基づいて、AIが応答すべきかを判定する。
        - "always": 常に応答
        - "keyword_only": トリガーキーワードが含まれる場合のみ応答
        - "mention_only": メンション（AIの名前）が含まれる場合のみ応答

        Args:
            text: ユーザーの発言テキスト

        Returns:
            tuple: (bool, str | None) - (応答するか, ヒットしたキャラ名 or None)
        """
        try:
            # 設定を取得
            cfg = getattr(self, "config_manager", None)
            if not cfg:
                logger.warning("[Phase 2-2] config_manager が None のため、常に応答モードで動作")
                # デフォルトキャラを取得
                triggers = self._get_ai_triggers()
                default_char = triggers[0][0] if triggers else "ぎゅるる"
                return (True, default_char)

            response_mode = cfg.get("ai.response_mode", "always")
            logger.info(f"[Phase 2-2] 応答モード: {response_mode}")

            # "always" モード：常に応答
            if response_mode == "always":
                # デフォルトキャラを取得
                triggers = self._get_ai_triggers()
                default_char = triggers[0][0] if triggers else "ぎゅるる"
                return (True, default_char)

            text_lower = text.lower()

            # "keyword_only" モード：トリガーキーワードが含まれる場合のみ
            if response_mode == "keyword_only":
                # v17.6+: 複数キャラのトリガーをチェック
                triggers = self._get_ai_triggers()  # [(キャラ名, トリガーリスト), ...]

                # 各キャラのトリガーをチェック
                for char_name, trigger_list in triggers:
                    if any(keyword.lower() in text_lower for keyword in trigger_list):
                        logger.info(f"[Phase 2-2] キーワード検出: キャラ「{char_name}」")
                        return (True, char_name)

                logger.info(f"[Phase 2-2] トリガーキーワード未検出、AI応答スキップ: '{text}'")
                return (False, None)

            # "mention_only" モード：AIの名前が含まれる場合のみ
            if response_mode == "mention_only":
                # v17.6+: 複数キャラの名前をチェック
                ai_characters = cfg.get("ai_characters", {})

                if ai_characters:
                    for char_name, char_data in ai_characters.items():
                        if char_data.get('archived', False):
                            continue
                        if char_name.lower() in text_lower:
                            logger.debug(f"[Phase 2-2] メンション検出: '{char_name}' in '{text}'")
                            return (True, char_name)
                else:
                    # フォールバック：旧形式
                    ai_name = cfg.get("ai_personality.basic_info.name", "ぎゅるる")
                    if ai_name.lower() in text_lower:
                        logger.debug(f"[Phase 2-2] メンション検出: '{ai_name}' in '{text}'")
                        return (True, ai_name)

                logger.debug(f"[Phase 2-2] メンション未検出、AI応答スキップ: '{text}'")
                return (False, None)

            # 未知のモード：デフォルトで応答
            logger.warning(f"[Phase 2-2] 未知の応答モード: {response_mode}, デフォルトで応答")
            triggers = self._get_ai_triggers()
            default_char = triggers[0][0] if triggers else "ぎゅるる"
            return (True, default_char)

        except Exception as e:
            logger.error(f"[Phase 2-2] _should_call_ai エラー: {e}", exc_info=True)
            # エラー時は応答（安全側に倒す）
            triggers = self._get_ai_triggers()
            default_char = triggers[0][0] if triggers else "ぎゅるる"
            return (True, default_char)

    def _maybe_ai_auto_reply(self, text: str, *, source: str = "manual") -> None:
        """
        ユーザー発言を受けて、必要ならAIに投げる。
        - MessageBus があるとき: AIIntegrationManager に AI_REQUEST を投げるだけ
        - MessageBus が無いとき: 自前で AI を呼び出す（スタンドアロン用）
        """
        text = (text or "").strip()
        if not text:
            return

        # --- AIオン/オフ確認 ---
        if not self.is_ai_enabled():
            return

        # --- Phase 2-2: 応答モード判定 ---
        should_respond, matched_char = self._should_call_ai(text)
        if not should_respond:
            return

        # --- Phase 2-3: 確率判定（UnifiedConfigManager から取得）---
        prob = 1.0
        try:
            cfg = getattr(self, "config_manager", None)
            if cfg:
                # UnifiedConfigManager から応答確率を取得
                prob = float(cfg.get("ai.response_probability", 1.0))
                logger.info(f"[Phase 2-3] 応答確率: {prob}")
            elif hasattr(self, "ai_probability_var"):
                # フォールバック：旧方式の変数から取得
                prob = float(self.ai_probability_var.get())
                logger.info(f"[Phase 2-3] 応答確率（旧方式）: {prob}")
        except Exception as e:
            logger.warning(f"[Phase 2-3] 応答確率の取得エラー: {e}, デフォルト 1.0 を使用")
            prob = 1.0

        if prob < 1.0:
            import random
            r = random.random()
            if r > prob:
                # この発言ではAIは黙る
                logger.info(f"[Phase 2-3] 確率判定でスキップ (prob={prob}, random={r:.2f})")
                return
            else:
                logger.info(f"[Phase 2-3] 確率判定で通過 (prob={prob}, random={r:.2f})")

        # --- Phase 2-4: 重複チェック（同じメッセージの多重発行を防止）---
        import time
        current_time = time.time()
        text_normalized = text.strip().lower()

        # 履歴をクリーンアップ（古いエントリを削除）
        self._ai_request_history = [
            (t, ts) for t, ts in self._ai_request_history
            if current_time - ts < self._ai_request_duplicate_window
        ]

        # 重複チェック
        for hist_text, hist_ts in self._ai_request_history:
            if hist_text == text_normalized:
                time_diff = current_time - hist_ts
                logger.debug(
                    f"[Phase 2-4] 重複メッセージ検出、スキップ: '{text}' "
                    f"(前回から {time_diff:.1f}秒)"
                )
                return

        # 履歴に追加（最大数を超えたら古いものを削除）
        self._ai_request_history.append((text_normalized, current_time))
        if len(self._ai_request_history) > self._ai_request_history_max:
            self._ai_request_history = self._ai_request_history[-self._ai_request_history_max:]

        # --- MessageBus がある場合 → AIIntegrationManager に委譲 ---
        if self.message_bus is not None:
            try:
                payload = {
                    "text": text,
                    "user": "User",       # ここは必要なら後で配信者名に変更
                    "source": source,
                    "tab": "chat",
                    "character_name": matched_char,  # ✅ v17.6+: キーワードにヒットしたキャラ名
                }
                self._do_ai_request(payload, sender="chat_tab_auto")
                logger.debug(f"AI_REQUEST 発行: {payload}")
            except Exception as e:
                logger.warning(f"AI_REQUEST 発行エラー: {e}")
            return

        # --- MessageBus が無い場合のみ、ローカルでAI処理する ---
        worker = threading.Thread(
            target=self._process_ai_response,
            args=(text, source),
            daemon=True,
        )
        worker.start()

    def _text_hits_triggers(self, text: str) -> bool:
        try:
            t = (text or "").lower()
            # ここはAIキャラ設定タブからキーワードを読む実装に紐づけてもOK
            trigger_words = ["ぎゅるる", "bot", "hello", "テスト", "修正", "色"]  # 例
            return any(w in t for w in trigger_words)
        except Exception:
            return False

    # ===== 音声 =====
    def _send_voice_request(self, text: str, username: str = "システム", role: str = "viewer"):
        """
        音声読み上げリクエストを送信

        v17.6.0: ロール別キャラ選択対応
        - role パラメータ追加（デフォルト: 'viewer'）
        - role は 'streamer'/'ai'/'viewer' のいずれか
        """
        try:
            if not text or not text.strip():
                return False
            if VOICE_SINGLETON_AVAILABLE and callable(speak_text):
                try:
                    result = speak_text(text=text.strip()[:500], username=username)
                    if result:
                        self.stats['voice_requests'] += 1
                        logger.info(f"🎤 VoiceManager Singleton音声送信成功: {text[:30]}... (role={role})")
                        return True
                except Exception as e:
                    logger.warning(f"⚠️ VoiceManager Singleton失敗: {e}")
            if self.message_bus and MESSAGEBUS_AVAILABLE:
                try:
                    voice_payload = {
                        'text': text.strip()[:500],
                        'username': username,
                        'source': 'chat_app',
                        'timestamp': datetime.now().isoformat(),
                        'priority': 'normal',
                        'role': role,  # ✅ v17.6.0: ロール情報を追加（speaker_id は role から自動決定）
                    }
                    # ✅ 修正: VOICE_REQUESTを正しく発行（AI応答以外の用途: システムメッセージ等）
                    self.message_bus.publish(EventTypes.VOICE_REQUEST, voice_payload, sender="chat_tab")
                    self.stats['voice_requests'] += 1
                    logger.info(f"🎤 MessageBus音声送信成功: {text[:30]}... (role={role})")
                    return True
                except Exception as e:
                    logger.error(f"❌ MessageBus音声送信エラー: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 音声要求送信エラー: {e}")
            return False

    # ===== AI応答ワーカー（保持） =====
    def _should_ai_respond(self, text: str):
        """
        AI応答するかどうかの判定
        v17.6+: 複数AIキャラに対応

        Args:
            text: 判定対象のテキスト

        Returns:
            tuple: (bool, str | None) - (応答するか, ヒットしたキャラ名 or None)
            - ai_reply_mode == 1（全返答）なら (True, None)
            - ai_reply_mode == 0（キーワード反応）なら、ヒットしたキャラがいれば (True, キャラ名)
            - 上記の上に、確率スライダ（ai_probability）も掛ける
        """
        try:
            matched_char = None

            # 全返答モード
            if self.ai_reply_mode.get() == 1:
                base = True
                # 全返答モードの場合は、デフォルトキャラ（最初のキャラ）を使用
                triggers = self._get_ai_triggers()
                if triggers:
                    matched_char = triggers[0][0]  # 最初のキャラ名
            else:
                # キーワード反応モード
                triggers = self._get_ai_triggers()  # [(キャラ名, トリガーリスト), ...]
                low = (text or "").lower()
                base = False

                # 各キャラのトリガーをチェック
                for char_name, trigger_list in triggers:
                    if any(t.lower() in low for t in trigger_list):
                        base = True
                        matched_char = char_name
                        logger.info(f"✅ キーワード反応: キャラ「{char_name}」のトリガーにヒット")
                        break  # 最初にヒットしたキャラを使用

            # 確率を掛ける
            prob = max(0, min(100, int(self.ai_probability.get()))) / 100.0
            import random
            should_respond = base and (random.random() < prob)

            return (should_respond, matched_char if should_respond else None)

        except Exception as e:
            logger.error("❌ _should_ai_respond 判定エラー: %s", e)
            return (False, None)

    def _process_ai_response(self, text: str, source: str) -> None:
        """
        バスが無い“スタンドアロン時専用”のAI処理。
        _maybe_ai_auto_reply からスレッドで呼び出される。
        """
        try:
            ai_text = self._call_ai(text)
            if not ai_text:
                return

            speaker_name = (
                self.ai_name_var.get()
                if hasattr(self, "ai_name_var")
                else "GyururuAI"
            )

            # ここでは MessageBus を使わず、自分のチャット欄だけ更新
            self._post_message(
                "ai",
                speaker=speaker_name,
                text=ai_text,
                source=f"local-{source}",
            )
        except Exception as e:
            logger.warning(f"_process_ai_response エラー: {e}")

    def _get_ai_triggers(self):
        """
        AIキャラ設定タブから「反応トリガー(キーワード)」を取り出す。
        v17.6+: 複数AIキャラに対応

        Returns:
            list[tuple[str, list[str]]]: [(キャラ名, トリガーリスト), ...]
        """
        try:
            cfg = getattr(self, "config_manager", None)
            if cfg is None:
                raise RuntimeError("ConfigManager not available")

            # v17.6+: 複数AIキャラクターの設定を取得
            ai_characters = cfg.get("ai_characters", {})

            if not ai_characters or not isinstance(ai_characters, dict):
                # フォールバック：旧形式のトリガー
                return [("ぎゅるる", self._get_legacy_triggers(cfg))]

            # 各キャラクターのトリガーを収集
            result = []
            for char_name, char_data in ai_characters.items():
                if not isinstance(char_data, dict):
                    continue

                # アーカイブされたキャラはスキップ
                if char_data.get('archived', False):
                    continue

                # トリガーを取得
                base_settings = char_data.get('base_settings', {})
                triggers = base_settings.get('keywords_triggers', [])

                if not triggers:
                    continue

                # リストに変換（文字列の場合）
                if isinstance(triggers, str):
                    triggers = [t.strip() for t in triggers.split(',') if t.strip()]
                elif isinstance(triggers, (list, tuple)):
                    triggers = [str(t).strip() for t in triggers if str(t).strip()]
                else:
                    continue

                if triggers:
                    result.append((char_name, triggers))

            # キャラが見つからない場合はデフォルト
            if not result:
                return [("ぎゅるる", ["ぎゅるる", "bot", "テスト", "hello", "色"])]

            return result

        except Exception as e:
            logger.error(f"❌ _get_ai_triggers エラー: {e}")
            # 何かあっても必ずデフォルトを返す
            return [("ぎゅるる", ["ぎゅるる", "bot", "テスト", "hello", "色"])]

    def _get_legacy_triggers(self, cfg):
        """旧形式のトリガー取得（後方互換性用）"""
        try:
            candidate_keys = [
                "ai.triggers",
                "ai.keywords",
                "ai.trigger_keywords",
                "character.triggers",
                "character.keywords",
                "ai_unified.triggers",
                "ai_unified.keywords",
            ]
            raw = None
            for k in candidate_keys:
                raw = cfg.get(k, None)
                if raw:
                    break

            # 見つからなければデフォルト
            if not raw:
                return ["ぎゅるる", "bot", "テスト", "hello", "色"]

            # list ならそのまま正規化
            if isinstance(raw, (list, tuple, set)):
                out = [str(x).strip() for x in raw if str(x).strip()]
                return out if out else ["ぎゅるる"]

            # 文字列なら、改行 or カンマで分割
            if isinstance(raw, str):
                if "\n" in raw:
                    parts = [p.strip() for p in raw.splitlines()]
                elif "," in raw:
                    parts = [p.strip() for p in raw.split(",")]
                else:
                    parts = [raw.strip()] if raw.strip() else []
                return [p for p in parts if p]

            # 想定外の型 → デフォルト
            return ["ぎゅるる"]
        except Exception:
            return ["ぎゅるる", "bot", "テスト", "hello", "色"]

    def _send_message(self, event=None):
        """
        手動入力からの送信処理。
        CHAT_MESSAGE のみを発行し、AI_REQUEST は _on_chat_message() → _maybe_ai_auto_reply() の流れで発行される。
        これにより、AI応答の二重発行を防止。
        v17.5.7: streamer.display_name に統一、role="streamer" を追加
        """
        message = self.message_entry.get().strip()
        if not message:
            return

        logger.debug(f"🐛 [DEBUG] _send_message 開始: message={message}, インスタンスID={id(self)}")

        # 入力欄は先にクリア
        self.message_entry.delete(0, tk.END)

        # MessageBus が生きている場合は、CHAT_MESSAGE のみを発行
        if self.message_bus and MESSAGEBUS_AVAILABLE:
            try:
                # v17.5.7: 配信者名は streamer.display_name に統一
                streamer_name = "配信者"
                try:
                    if hasattr(self, "config_manager") and self.config_manager:
                        streamer_name = (
                            self.config_manager.get("streamer.display_name", "配信者") or "配信者"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ streamer.display_name 取得に失敗: {e}")

                chat_data = {
                    "username": streamer_name,  # v17.5.7: "ユーザー" から変更
                    "text": message,
                    "platform": "manual",
                    "timestamp": datetime.now().isoformat(),
                    "role": "streamer",  # v17.5.7: OBS 演出タブ用
                    "manual_input": True,
                }

                logger.debug(f"🐛 [DEBUG] CHAT_MESSAGE publish準備: {chat_data}")

                # CHAT_MESSAGE を発行（チャット表示/読み上げ/AI応答のトリガー）
                # AI_REQUEST は _on_chat_message() → _maybe_ai_auto_reply() で発行される
                self.message_bus.publish(
                    Events.CHAT_MESSAGE,
                    chat_data,
                    sender="chat_app_manual",
                )
                logger.info("📡 CHAT_MESSAGE published from ChatTab (manual)")
                logger.debug("💡 AI_REQUEST は _on_chat_message() → _maybe_ai_auto_reply() で発行されます")

            except Exception as e:
                logger.error(f"メッセージ送信エラー: {e}")

        else:
            # 🔁 フォールバック（MessageBus が無い場合）
            try:
                logger.warning(
                    "⚠️ MessageBus 未接続のため、ローカル仮想応答モードで動作します。"
                )
                fallback_reply = f"[ローカル仮想応答] {message}"
                # ここは ChatHandler が CHAT_APPEND を拾う前提なら、
                # 画面だけでも反応が見えるように system 行として出しておく
                self._append_system_line(fallback_reply)
            except Exception:
                # 最悪 print だけ
                print("[ローカル仮想応答]", message)

    def _on_probability_change(self, *args):
        """
        Phase 2: 応答確率スライダー変更時のデバウンス処理
        UI更新は即座に、保存は2秒後に実行（スライダー移動中の連続保存を防止）
        """
        try:
            prob = int(self.ai_probability.get())

            # --- 既存のタイマーをキャンセル（スライダー移動中は保存しない）---
            if self._response_prob_save_timer:
                try:
                    self.master.after_cancel(self._response_prob_save_timer)
                except Exception:
                    pass  # タイマーが既に実行済みの場合は無視

            # --- ラベルが存在する場合だけ更新（今は基本 None の想定）---
            if hasattr(self, "prob_label") and self.prob_label:
                if prob == 100:
                    color = "#4CAF50"; weight = "bold"
                elif prob >= 80:
                    color = "#8BC34A"; weight = "bold"
                else:
                    color = "#FFC107"; weight = "normal"
                try:
                    self.prob_label.config(text=f"{prob}%", fg=color, font=("Arial", 9, weight))
                except Exception as ui_e:
                    logger.debug(f"prob_label の更新をスキップ: {ui_e}")

            # --- 2秒後に保存をスケジュール（デバウンス）---
            self._response_prob_save_timer = self.master.after(2000, self._save_probability)
            logger.debug(f"⏱️ 応答確率保存を2秒後にスケジュール: {prob}%")

        except Exception as e:
            logger.error(f"❌ 確率変更エラー: {e}")

    def _save_probability(self):
        """
        Phase 2: 応答確率の実際の保存処理（デバウンス後に実行）
        """
        try:
            prob = int(self.ai_probability.get())
            if self.config_manager and CONFIG_MANAGER_AVAILABLE:
                try:
                    self.config_manager.set('ai.response_probability', prob / 100.0)
                    self.config_manager.save()
                    # チャットUIにシステムメッセージを表示
                    self._append_system(f"📊 応答確率を {prob}% に更新しました")
                    logger.info(f"💾 応答確率を保存: {prob}%")
                except Exception as config_error:
                    logger.warning(f"⚠️ ConfigManager保存エラー: {config_error}")
        except Exception as e:
            logger.error(f"❌ 確率保存エラー: {e}")

    def _on_reply_mode_change(self, *args):
        """
        Phase 2: AI応答モード変更時の自動保存
        チャットタブのラジオボタン (0=キーワード, 1=全返答) → 設定に保存
        """
        try:
            mode_int = int(self.ai_reply_mode.get())
            # 0=キーワード, 1=全返答 → "keyword_only", "always"
            mode_str = "keyword_only" if mode_int == 0 else "always"

            if self.config_manager and CONFIG_MANAGER_AVAILABLE:
                try:
                    self.config_manager.set('ai.response_mode', mode_str)
                    self.config_manager.save()
                    mode_label = "キーワード反応" if mode_int == 0 else "全返答"
                    # チャットUIにシステムメッセージを表示
                    self._append_system(f"🤖 応答モードを {mode_label} に設定しました")
                    logger.info(f"💾 応答モードを保存: {mode_label} ({mode_str})")
                except Exception as config_error:
                    logger.warning(f"⚠️ ConfigManager保存エラー: {config_error}")
        except Exception as e:
            logger.error(f"❌ 応答モード変更エラー: {e}")

    def _on_ai_enabled_change(self):
        try:
            enabled = self.ai_enabled.get()
            if self.config_manager and CONFIG_MANAGER_AVAILABLE:
                try:
                    self.config_manager.set('ai.enabled', enabled)
                    self.config_manager.save()
                except Exception as config_error:
                    logger.warning(f"⚠️ ConfigManager保存エラー: {config_error}")
            logger.info(f"🤖 AI応答: {'有効' if enabled else '無効'}")
        except Exception as e:
            logger.error(f"❌ AI有効変更エラー: {e}")

    def _on_voice_setting_change(self, target: str, enabled: bool):
        """
        音声読み上げ設定変更時のハンドラ
        - チャットUIにシステムメッセージを表示
        - UnifiedConfig に設定を保存（v17.5.x 追加）
        """
        try:
            status = "ON" if enabled else "OFF"
            self._append_system(f"🎤 音声読み上げ ({target}): {status}")
            logger.info(f"🎤 音声読み上げ設定変更: {target} -> {status}")

            # ✅ v17.5.x 追加: UnifiedConfig に設定を保存
            if self.config_manager and CONFIG_MANAGER_AVAILABLE:
                try:
                    # target に応じた設定キーを決定
                    config_key = None
                    if target == "配信者":
                        config_key = "voice.read.streamer"
                    elif target == "AIキャラ":
                        config_key = "voice.read.ai"
                    elif target == "視聴者":
                        config_key = "voice.read.viewer"

                    if config_key:
                        self.config_manager.set(config_key, enabled)
                        self.config_manager.save()
                        logger.info(f"💾 音声読み上げ設定を保存: {config_key} = {enabled}")
                except Exception as config_error:
                    logger.warning(f"⚠️ ConfigManager保存エラー: {config_error}")
        except Exception as e:
            logger.error(f"❌ 音声設定変更エラー: {e}")

    def _test_ai_response(self):
        test_message = "こんにちは、ぎゅるる!色分け対応版はどう?VoiceManager Singleton統合版テストです!MessageBus統合版だよ!"
        test_msg = {'username': '🧪 AIテスター', 'message': test_message, 'message_type': 'test', 'platform': 'test'}
        self.chat_display.add_formatted_message(test_msg)
        self._process_ai_response({'text': test_message, 'username': 'AIテスター'})

    def send_test_message(self):
        try:
            if not self.message_bus or not MESSAGEBUS_AVAILABLE:
                timestamp = datetime.now().isoformat()
                test_msg = {
                    'username': '🔧 ローカルテスター',
                    'message': (
                        f'MessageBus未接続のため、ローカルテストを実行しました。{timestamp[-8:]}\n'
                        f'✅ 色分け機能: 対応済み\n'
                        f'✅ VoiceManager Singleton: {"利用可能" if VOICE_SINGLETON_AVAILABLE else "利用不可"}\n'
                        f'✅ ConfigManager: {"利用可能" if CONFIG_MANAGER_AVAILABLE else "利用不可"}'
                    ),
                    'message_type': 'system',
                    'platform': 'test'
                }
                self.chat_display.add_formatted_message(test_msg)
                if self.ai_enabled.get():
                    self._process_ai_response({'text': 'ローカルテスト実行完了', 'username': 'ローカルテスター'})
                return

            timestamp = datetime.now().isoformat()
            test_data = {
                'username': '📡 色分け対応版テスター',
                'text': f'🎨 色分け対応版MessageBusテストです!媒体別色分け機能搭載版 {timestamp[-8:]}',
                'platform': 'test',
                'timestamp': timestamp,
                'test_mode': True,
                'color_support_version': True,
                'message_bus_integrated': True
            }
            self.message_bus.publish(Events.CHAT_MESSAGE, test_data, sender="chat_app_test")
            logger.info("📡 テストメッセージをMessageBus経由で送信")
        except Exception as e:
            logger.error(f"❌ send_test_message エラー: {e}")

    # ===== 付帯処理 =====
    def _publish_tab_ready(self):
        try:
            if self.message_bus and MESSAGEBUS_AVAILABLE:
                payload = {
                    'tab_name': 'AIとチャット',
                    'type': 'chat_tab',
                    'features': ['display', 'ai', 'voice', 'bus', 'color_support', 'v17_integrated'],
                    'timestamp': datetime.now().isoformat(),
                    'version': 'v17.0_color_support_messagebus_integrated'
                }
                self.message_bus.publish(Events.TAB_READY, payload, sender="chat_app")
                logger.info("📡 v17色分け対応版タブ準備完了通知送信")
        except Exception as e:
            logger.warning(f"⚠️ TAB_READY通知エラー: {e}")

    def _update_stats_display(self):
        try:
            self.stats_label.config(
                text=f"受信: {self.stats['received_comments']} | AI応答: {self.stats['ai_responses']} | 音声: {self.stats['voice_requests']} | エラー: {self.stats['errors']}"
            )
        except Exception as e:
            logger.error(f"❌ 統計表示更新エラー: {e}")

    # ========================================
    # 音声制御ハンドラ（依頼書④）
    # ========================================

    def _on_volume_changed(self, _value: str) -> None:
        """音量スライダー変更時のハンドラ"""
        try:
            v = int(float(_value))
            self.shared_volume_var.set(v)

            # 可能なら既存の音声マネージャへ反映（無ければ⑤で統合）
            if hasattr(self, "voice_manager") and self.voice_manager:
                try:
                    self.voice_manager.set_volume(v)
                    logger.info(f"🔊 音量変更: {v}%")
                except Exception as e:
                    logger.debug(f"音量設定エラー（VoiceManager未対応の可能性）: {e}")
        except Exception as e:
            logger.error(f"❌ 音量変更エラー: {e}")

    def _on_mute_toggled(self) -> None:
        """ミュートチェックボックス変更時のハンドラ"""
        try:
            muted = bool(self.shared_mute_var.get())

            if hasattr(self, "voice_manager") and self.voice_manager:
                try:
                    self.voice_manager.set_mute(muted)
                    logger.info(f"🔇 ミュート: {'ON' if muted else 'OFF'}")
                except Exception as e:
                    logger.debug(f"ミュート設定エラー（VoiceManager未対応の可能性）: {e}")
        except Exception as e:
            logger.error(f"❌ ミュート切り替えエラー: {e}")

    def _on_voice_stop(self) -> None:
        """読み上げ停止ボタンのハンドラ"""
        try:
            if hasattr(self, "voice_manager") and self.voice_manager:
                try:
                    self.voice_manager.stop()
                    logger.info("⏹️ 読み上げ停止")
                except Exception as e:
                    logger.debug(f"停止エラー（VoiceManager未対応の可能性）: {e}")
        except Exception as e:
            logger.error(f"❌ 読み上げ停止エラー: {e}")

    def _on_voice_clear_queue(self) -> None:
        """キュークリアボタンのハンドラ"""
        try:
            if hasattr(self, "voice_manager") and self.voice_manager:
                try:
                    self.voice_manager.clear_queue()
                    logger.info("🗑️ 音声キューをクリア")
                except Exception as e:
                    logger.debug(f"キュークリアエラー（VoiceManager未対応の可能性）: {e}")
        except Exception as e:
            logger.error(f"❌ キュークリアエラー: {e}")

    def _copy_selected_text(self):
        try:
            text = self.chat_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.master.clipboard_clear()
            self.master.clipboard_append(text)
        except Exception:
            pass

    def _select_all_text(self):
        self.chat_widget.tag_add(tk.SEL, "1.0", tk.END)
        self.chat_widget.mark_set(tk.INSERT, "1.0")
        self.chat_widget.see(tk.INSERT)

    def _clear_chat(self):
        try:
            self.chat_display.clear_chat()
        except Exception as e:
            logger.error(f"❌ チャットクリアエラー: {e}")

    def _save_chat_log(self):
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
            if file_path:
                self.chat_display.export_chat_log(file_path)
        except Exception as e:
            logger.error(f"❌ ログ保存エラー: {e}")

    def _setup_cleanup(self):
        try:
            if hasattr(self.master, 'protocol'):
                self.master.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

    def _on_close(self):
        try:
            self.running = False
            if hasattr(self.master, 'destroy'):
                self.master.destroy()
        except Exception:
            try:
                self.master.destroy()
            except Exception:
                pass

    def get_frame(self):
        return getattr(self, 'frame', self.master)

# ===== タブ用ファクトリ =====
def create_integrated_ai_chat_tab(parent, message_bus=None, config_manager=None, app_instance=None, shared_volume_var=None, shared_mute_var=None):
    logger.info("📋 create_integrated_ai_chat_tab 呼び出し")
    try:
        app = ChatAppCompleteFixed(
            parent,
            message_bus=message_bus,
            config_manager=config_manager,
            app_instance=app_instance,
            shared_volume_var=shared_volume_var,
            shared_mute_var=shared_mute_var
        )
        setattr(parent, "_chat_app_instance", app)  # GC対策
        logger.info("✅ create_integrated_ai_chat_tab 成功")
        return app
    except Exception as e:
        logger.error(f"❌ create_integrated_ai_chat_tab 失敗: {e}")
        raise

def create_chat_tab(parent, message_bus=None, config_manager=None, app_instance=None, shared_volume_var=None, shared_mute_var=None):
    return create_integrated_ai_chat_tab(parent, message_bus, config_manager, app_instance, shared_volume_var, shared_mute_var)

def create_tab(parent, message_bus=None, config_manager=None, app_instance=None, shared_volume_var=None, shared_mute_var=None):
    return create_integrated_ai_chat_tab(parent, message_bus, config_manager, app_instance, shared_volume_var, shared_mute_var)

ChatApp = ChatAppCompleteFixed
ChatTabApp = ChatAppCompleteFixed

# ===== スタンドアロン起動 =====
if __name__ == "__main__":
    print("=" * 60)
    print("🎨 AIとチャット v17.0 - 完全統合版(修正完了版)")
    print("📋 主要機能:")
    print("  A. 媒体別色分け機能(YouTube赤・Twitch紫・ニコニコオレンジ等)")
    print("  B. 配信者(水色)・Gemini AI(緑)・その他AI(白)")
    print("  C. AI設定タブの内容を確実に反映")
    print("  D. VoiceManager Singleton統合")
    print("  E. MessageBus完全統合")
    print("  F. 応答確率スライダー(チャットタブに配置)")
    print("  G. エラー処理強化・統計機能")
    print("  H. AI自動返信機能復旧 ✅ NEW")
    print("=" * 60)

    root = tk.Tk()
    app = ChatAppCompleteFixed(root)

    if "--test" in sys.argv:
        def _pump():
            try:
                app.send_test_message()
            finally:
                root.after(3000, _pump)
        _pump()

    print("🚀 スタンドアロン起動完了")
    print("💡 使用方法:")
    print("  1. メッセージ入力欄にテキストを入力")
    print("  2. 📡 MessageBusテストボタンでテスト送信")
    print("  3. 🎤 音声テストボタンで音声機能確認")
    print("  4. AI応答確率スライダーで応答率調整")
    print("  5. 🎨 色分け機能で各プラットフォームを色で識別")

    root.mainloop()
