# -*- coding: utf-8 -*-
"""
📡 WebSocket タブ（v17 互換最新版）
- OneComme 受信ブリッジの起動・停止
- 旧イベント名(WEBSOCKET_CONNECT 等) → 新イベント名(WS_CONNECT 等) の自動マッピング
- 黒背景ログ付きの ConnectionControlPanel を統合
- MessageBus / EventTypes の存在に応じて安全に動作（フォールバックあり）
"""

from __future__ import annotations
import os
import sys
import logging
from datetime import datetime
import tkinter as tk
from tkinter import ttk

# ===== パス調整（プロジェクト直下/同階層フォールバック） =====
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
for p in (CURRENT_DIR, PROJECT_ROOT, os.path.join(PROJECT_ROOT, "shared")):
    if p and p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ===== 共有モジュール（安全インポート） =====
# EventTypes
Events = None
try:
    from shared.event_types import Events as _Events  # v17 正式
    Events = _Events
except Exception:
    try:
        # パッケージ直下配置フォールバック
        from event_types import Events as _Events
        Events = _Events
    except Exception:
        class _CompatEvents:
            # 最後の砦：最低限のキーだけ用意
            WS_CONNECT         = "WS_CONNECT"
            WS_DISCONNECT      = "WS_DISCONNECT"
            WS_STATUS          = "WS_STATUS"
            WEBSOCKET_CONNECT  = "WS_CONNECT"
            WEBSOCKET_DISCONNECT = "WS_DISCONNECT"
            WEBSOCKET_LOG      = "WEBSOCKET_LOG"
            ONECOMME_COMMENT   = "ONECOMME_COMMENT"
            CHAT_MESSAGE       = "CHAT_MESSAGE"
            TAB_READY          = "TAB_READY"
        Events = _CompatEvents()  # type: ignore
        logger.warning("⚠️ event_types を読み込めなかったため簡易互換を使用します")

# MessageBus
MessageBus = None
get_bus = None
try:
    from shared.message_bus import MessageBus as _MB, get_message_bus as _get_bus
    MessageBus = _MB
    get_bus = _get_bus  # ✅ シングルトン取得関数
except Exception as e:
    try:
        from message_bus import MessageBus as _MB, get_message_bus as _get_bus
        MessageBus = _MB
        get_bus = _get_bus
    except Exception:
        MessageBus = None
        get_bus = None
        logger.warning("⚠️ MessageBus が見つかりません（スタンドアロン時は内部バス省略）")

# UI共通ヘルパー
try:
    from shared.ui_helpers import apply_statusbar_style
except Exception:
    # フォールバック：共通関数が見つからない場合は何もしない
    def apply_statusbar_style(widget):
        return "#66DD66", "#000000"

# VoiceManager（ステータス表示用）
VOICE_SINGLETON_AVAILABLE = False
try:
    from shared.voice_manager_singleton import get_voice_manager
    VOICE_SINGLETON_AVAILABLE = True
except Exception:
    pass

# ConfigManager（ステータス表示用）
CONFIG_MANAGER_AVAILABLE = False
try:
    from shared.unified_config_manager import UnifiedConfigManager
    CONFIG_MANAGER_AVAILABLE = True
except Exception:
    pass

# UI（接続パネル）- v17.5 Multi Comment Bridge
create_connection_panel = None
create_multi_connection_panel = None
try:
    # v17.5 マルチコネクタパネル（優先）
    from .multi_connection_panel import create_multi_connection_panel
    create_connection_panel = create_multi_connection_panel  # 互換性のため
except Exception:
    try:
        # 旧版フォールバック
        from .connection_panel import create_connection_panel
    except Exception:
        try:
            # 直下配置
            from connection_panel import create_connection_panel  # type: ignore
        except Exception:
            create_connection_panel = None
            logger.warning("⚠️ connection_panel が見つかりません（UI最小化動作）")

# Bridge 初期化
init_bridge = None
_stop_bridge = None  # 停止用（存在すれば呼ぶ）
try:
    from .message_bridge import init_bridge as _init_bridge
    init_bridge = _init_bridge
    # 停止APIがある場合だけ取り出す（なくても動く）
    try:
        from .message_bridge import stop_bridge as _stop
        _stop_bridge = _stop
    except Exception:
        pass
except Exception:
    try:
        from message_bridge import init_bridge as _init_bridge  # type: ignore
        init_bridge = _init_bridge
        try:
            from message_bridge import stop_bridge as _stop  # type: ignore
            _stop_bridge = _stop
        except Exception:
            pass
    except Exception:
        init_bridge = None
        logger.warning("⚠️ message_bridge が見つかりません（接続は無効）")

# ===== 旧→新 イベント名の互換マッピング =====
def _ensure_event_aliases():
    """
    connection_panel が WEBSOCKET_CONNECT/WEBSOCKET_DISCONNECT/WEBSOCKET_LOG を
   参照しても落ちないよう、v17の WS_* へ自動で別名を割り当てる。
    """
    try:
        # 右辺キーは v17 公式（存在しなければ文字列にしてしまう）
        ws_connect  = getattr(Events, "WS_CONNECT", "WS_CONNECT")
        ws_disconnect = getattr(Events, "WS_DISCONNECT", "WS_DISCONNECT")
        # ログ用は明確なキーがないので専用トピックを文字列で用意
        ws_log = getattr(Events, "WEBSOCKET_LOG", "WEBSOCKET_LOG")

        if not hasattr(Events, "WEBSOCKET_CONNECT"):
            setattr(Events, "WEBSOCKET_CONNECT", ws_connect)
        if not hasattr(Events, "WEBSOCKET_DISCONNECT"):
            setattr(Events, "WEBSOCKET_DISCONNECT", ws_disconnect)
        if not hasattr(Events, "WEBSOCKET_LOG"):
            setattr(Events, "WEBSOCKET_LOG", ws_log)

    except Exception as e:
        logger.error(f"❌ イベント互換マッピング失敗: {e}")

_ensure_event_aliases()

def _event(name: str, legacy: str | None = None):
    """
    イベント名を安全に解決するヘルパー。
    - Events に name があれば（Enumでも）それを返す
    - なければ legacy 名があればまずそれを Events から探す
    - どちらも無ければ name（文字列）を返す
    """
    try:
        val = getattr(Events, name)
        return val
    except Exception:
        pass
    if legacy:
        try:
            val = getattr(Events, legacy)
            return val
        except Exception:
            # 旧名が Events に無ければ旧名そのもの（文字列キー）にフォールバック
            return legacy
    # 最終フォールバックは新名の文字列キー
    return name


# ===== タブ本体 =====
class WebSocketTab(ttk.Frame):
    """
    WebSocket タブ（OneComme ブリッジの起動/停止制御 & ログ表示）
    - ConnectionControlPanel を組み込み
    - BUS の WS_CONNECT / WS_DISCONNECT を購読し、Bridge を起動/停止
    """

    def __init__(self, parent, message_bus=None, config_manager=None, app_instance=None, **kwargs):
        super().__init__(parent)
        # 「空白で表示されない」問題回避：必ず pack / grid どちらかで張り付け
        self.pack(fill=tk.BOTH, expand=True)

        self.bus = message_bus or (get_bus() if get_bus else None)
        self.config = config_manager  # UnifiedConfigManager 相当
        self.app_instance = app_instance

        self._bridge = None
        self._subs = []  # 解除用トークンや (event, callback) の記録

        # カウンター変数
        self.comment_count = 0
        self.ai_response_count = 0
        self.voice_request_count = 0
        self.error_count = 0

        self._build_ui()
        self._subscribe_events()
        self._notify_tab_ready()

    # --- UI ---
    def _build_ui(self):
        # 1. 接続状態パネル（上）
        self._create_connection_status_panel(self)

        # 2. Multi Comment Bridge（中）
        if create_connection_panel and self.bus:
            self.conn_panel = create_connection_panel(
                self,
                message_bus=self.bus,
                config_manager=self.config,
            )
            self.conn_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        else:
            # 最小フォールバックUI
            fallback = ttk.LabelFrame(self, text="📡 Multi Comment Bridge")
            fallback.pack(fill=tk.X, padx=10, pady=6)
            ttk.Label(fallback, text="接続UIを読み込めませんでした。").pack(padx=10, pady=10)

        # 3. 状態バー（下）
        self.status_var = tk.StringVar(value="⏳ 準備中…")

    def _create_connection_status_panel(self, parent):
        """
        接続状態パネル（Chatタブから移動）
        - 1段目：MessageBus/VoiceManager/ConfigManager/AIキャラ の4つのステータス枠（左寄せ）
        - 2段目：カウンター + テストボタン（左寄せ）
        """
        status_frame = ttk.LabelFrame(parent, text="📡 接続状態", padding="10")
        status_frame.pack(fill=tk.X, padx=10, pady=(10, 10))

        # 1段目：4つのステータス枠（左寄せ）
        status_row = ttk.Frame(status_frame)
        status_row.pack(fill=tk.X, pady=(0, 8), anchor="w")

        # MessageBus ステータス
        messagebus_status = "✅ 接続済み" if self.bus else "❌ 未接続"

        mb_frame = tk.Frame(status_row, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1)
        mb_frame.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(mb_frame, text="MessageBus: ", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.messagebus_status_label = tk.Label(mb_frame, text=messagebus_status, fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"))
        self.messagebus_status_label.pack(side=tk.LEFT, padx=(0, 5))

        # VoiceManager ステータス
        voice_status = "✅ 利用可能" if VOICE_SINGLETON_AVAILABLE else "❌ 未初期化"

        vm_frame = tk.Frame(status_row, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1)
        vm_frame.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(vm_frame, text="VoiceManager: ", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.voice_status_label = tk.Label(vm_frame, text=voice_status, fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"))
        self.voice_status_label.pack(side=tk.LEFT, padx=(0, 5))

        # ConfigManager ステータス
        config_status = "✅ 利用可能" if CONFIG_MANAGER_AVAILABLE else "❌ 未初期化"

        cm_frame = tk.Frame(status_row, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1)
        cm_frame.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(cm_frame, text="ConfigManager: ", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.config_status_label = tk.Label(cm_frame, text=config_status, fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"))
        self.config_status_label.pack(side=tk.LEFT, padx=(0, 5))

        # AIキャラ ステータス
        ai_char_frame = tk.Frame(status_row, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1)
        ai_char_frame.pack(side=tk.LEFT)
        tk.Label(ai_char_frame, text="AIキャラ: ", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.ai_character_label = tk.Label(ai_char_frame, text="確認中...", fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"))
        self.ai_character_label.pack(side=tk.LEFT, padx=(0, 5))

        # 2段目：カウント表示のみ（左寄せ）
        counter_row = ttk.Frame(status_frame)
        counter_row.pack(fill=tk.X, anchor="w", pady=(4, 0))

        # カウント表示（左端）
        self.stats_label = tk.Label(counter_row, text="受信: 0 | AI応答: 0 | 音声: 0 | エラー: 0", fg="#FFD700", bg="#2b2b2b", font=("Arial", 9))
        self.stats_label.pack(side=tk.LEFT)

    def send_test_message(self):
        """MessageBusテストメッセージ送信"""
        if not self.bus:
            logger.warning("⚠️ MessageBus未接続")
            return
        try:
            self.bus.publish("TEST_MESSAGE", {"text": "テストメッセージ", "source": "websocket_tab"}, sender="websocket_tab")
            logger.info("📡 テストメッセージ送信完了")
        except Exception as e:
            logger.error(f"❌ テストメッセージ送信エラー: {e}")

    def _test_voice_singleton(self):
        """音声テスト"""
        if not VOICE_SINGLETON_AVAILABLE:
            logger.warning("⚠️ VoiceManager未初期化")
            return
        try:
            from shared.voice_manager_singleton import speak_text
            speak_text("音声テスト成功", username="System")
            logger.info("🎤 音声テスト実行")
        except Exception as e:
            logger.error(f"❌ 音声テストエラー: {e}")

    # --- Bus 購読 ---
    def _subscribe_events(self):
        if not self.bus:
            self._set_status("❌ MessageBus 未接続")
            return

        def sub(ev, cb):
            try:
                token = self.bus.subscribe(ev, cb)
                self._subs.append(token if token is not None else (ev, cb))
                logger.debug(f"📝 subscribe: {ev}")
            except Exception as e:
                logger.error(f"❌ subscribe 失敗: {ev} -> {e}")

        # 新旧どちらのキーでも必ず拾えるように、安全に解決して購読
        ev_connect    = _event("WS_CONNECT",    "WEBSOCKET_CONNECT")
        ev_disconnect = _event("WS_DISCONNECT", "WEBSOCKET_DISCONNECT")

        sub(ev_connect, self._on_ws_connect)
        sub(ev_disconnect, self._on_ws_disconnect)

        # AI_STATUS_UPDATE を購読（AIキャラ状態ラベル更新用）
        if hasattr(Events, "AI_STATUS_UPDATE"):
            sub(Events.AI_STATUS_UPDATE, self._on_ai_status_update)

        # カウンター更新用イベント購読
        if hasattr(Events, "ONECOMME_COMMENT"):
            sub(Events.ONECOMME_COMMENT, self._on_comment_received)
        if hasattr(Events, "CHAT_MESSAGE"):
            sub(Events.CHAT_MESSAGE, self._on_comment_received)
        if hasattr(Events, "AI_RESPONSE"):
            sub(Events.AI_RESPONSE, self._on_ai_response)
        if hasattr(Events, "VOICE_REQUEST"):
            sub(Events.VOICE_REQUEST, self._on_voice_request)

        # ✅ v17.5: 二重購読を削除（normalize_event_keyがEnum処理を行うため不要）
        # 以前は互換性のため文字列キーでも購読していましたが、
        # これがログ暴走の原因となるため削除しました

        self._set_status("🔗 イベント購読完了")

    # --- TAB_READY 通知 ---
    def _notify_tab_ready(self):
        try:
            if self.bus and hasattr(Events, "TAB_READY"):
                data = {"tab": "websocket", "ts": datetime.now().isoformat()}
                self.bus.publish(Events.TAB_READY, data, sender="tab_websocket")
        except Exception:
            pass

    # --- 状態バー更新 ---
    def _set_status(self, text: str):
        try:
            self.status_var.set(text)
        except Exception:
            pass

    # --- 接続要求 ---
    def _on_ws_connect(self, data, sender=None):
        """
        data: {"url": "ws://.."} を期待
        """
        url = None
        try:
            if isinstance(data, dict):
                url = data.get("url")
        except Exception:
            pass

        # UnifiedConfigManager からの既定値（無ければローカル既定にフォールバック）
        if not url:
            try:
                if self.config and hasattr(self.config, "get"):
                    url = self.config.get("websocket.onecomme.url", "")
            except Exception:
                pass

        if not url:
            # ★ 最終フォールバック（OneComme v8 の標準ポート）
            url = "ws://127.0.0.1:22280/ws"

        try:
            logging.getLogger("tab_websocket").info(
                f"🔗 WebSocket connect request: url={url}"
            )
        except Exception:
            pass

        if not url:
            self._set_status("⚠️ URL 不明のため接続できません")
            return

        if not init_bridge:
            self._set_status("❌ Bridge 初期化関数が見つかりません")
            return

        try:
            self._bridge = init_bridge(self.bus, url)
            self._set_status(f"✅ 接続開始: {url}")
        except Exception as e:
            logger.error(f"❌ Bridge 初期化エラー: {e}")
            self._set_status(f"❌ 接続エラー: {e}")

    # --- 切断要求 ---
    def _on_ws_disconnect(self, data=None, sender=None):
        try:
            if _stop_bridge:
                _stop_bridge()
                self._set_status("🛑 切断要求 → 停止完了")
            else:
                self._set_status("🛑 切断要求 → stop_bridge 未実装")
        except Exception as e:
            logger.error(f"❌ 切断処理エラー: {e}")
            self._set_status(f"❌ 切断エラー: {e}")

    # --- AI_STATUS_UPDATE 受信 ---
    def _on_ai_status_update(self, data, sender=None):
        """
        AIキャラ接続状態ラベルを更新

        v17.5.4 (Task C): AI_STATUS_UPDATEペイロードの正式な接続判定ロジックを追加
        - payload に "connected" フィールドは含まれていないので、
          is_fallback / connector_available / has_api_key から判定する
        """
        try:
            if not isinstance(data, dict):
                return

            provider = data.get("provider", "unknown")
            model = data.get("model", "unknown")

            # v17.5.4: 正式な接続判定ロジック（Chat タブと同じ）
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
            else:
                connected = False

            logger.info(f"🔍 [Task C - WebSocket] AI状態: provider={provider}, model={model}, connected={connected}")

            if hasattr(self, "ai_character_label") and self.ai_character_label:
                if connected and provider not in ['fallback', 'local-echo', 'echo']:
                    # プロバイダー名を整形
                    provider_display = {
                        'gemini': 'Gemini',
                        'openai': 'OpenAI',
                        'anthropic': 'Claude',
                    }.get(provider.lower(), provider.capitalize())

                    # "Gemini / gemini-2.5-flash" のような形式で表示
                    ai_char_text = f"{provider_display} / {model}"
                    ai_char_color = "#90EE90"  # 明るい緑
                else:
                    ai_char_text = "未接続"
                    ai_char_color = "#FF4444"  # 赤

                self.ai_character_label.config(text=ai_char_text, fg=ai_char_color)
                logger.info(f"✅ [Task C - WebSocket] AIキャラ表示更新: {ai_char_text}")

        except Exception as e:
            logger.error(f"❌ AI_STATUS_UPDATE 処理エラー: {e}", exc_info=True)

    # --- カウンター更新ハンドラ ---
    def _on_comment_received(self, data, sender=None):
        """コメント受信時のカウント更新"""
        try:
            self.comment_count += 1
            self._update_stats_display()
        except Exception as e:
            logger.error(f"❌ コメントカウント更新エラー: {e}")

    def _on_ai_response(self, data, sender=None):
        """AI応答時のカウント更新"""
        try:
            self.ai_response_count += 1
            self._update_stats_display()
        except Exception as e:
            logger.error(f"❌ AI応答カウント更新エラー: {e}")

    def _on_voice_request(self, data, sender=None):
        """音声リクエスト時のカウント更新"""
        try:
            self.voice_request_count += 1
            self._update_stats_display()
        except Exception as e:
            logger.error(f"❌ 音声リクエストカウント更新エラー: {e}")

    def _update_stats_display(self):
        """統計表示を更新"""
        try:
            self.stats_label.config(
                text=f"受信: {self.comment_count} | AI応答: {self.ai_response_count} | 音声: {self.voice_request_count} | エラー: {self.error_count}"
            )
        except Exception as e:
            logger.error(f"❌ 統計表示更新エラー: {e}")

    # --- クリーンアップ（メイン終了時/タブ破棄時に呼び出し想定） ---
    def cleanup(self):
        try:
            # 購読解除
            if self.bus and hasattr(self.bus, "unsubscribe"):
                for token in list(self._subs):
                    try:
                        self.bus.unsubscribe(token)  # token 型/ (ev,cb) どちらも対応する実装を想定
                    except TypeError:
                        # (ev, cb) 形式だった場合
                            try:
                                ev, cb = token
                                self.bus.unsubscribe(ev, cb)
                            except Exception:
                                pass
                    except Exception:
                        pass
            self._subs.clear()

            # ブリッジ停止
            if _stop_bridge:
                try:
                    _stop_bridge()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"❌ WebSocketTab.cleanup エラー: {e}")

# ===== 生成関数（メインから呼ばれる想定） =====
def create_websocket_tab(parent, message_bus=None, config_manager=None, app_instance=None, **kwargs) -> WebSocketTab:
    """
    WebSocket タブ生成（v17 互換最新版）
    - parent: Tk/ttk コンテナ
    - message_bus: 共有 MessageBus（未指定ならシングルトン）
    - config_manager / app_instance / **kwargs は受け取るだけ（将来拡張向け）
    """
    logger.info("🔧 create_websocket_tab: 生成開始")
    bus = message_bus or (get_bus() if get_bus else None)
    tab = WebSocketTab(
        parent,
        message_bus=bus,
        config_manager=config_manager,
        app_instance=app_instance,
        **kwargs,
    )
    logger.info("✅ create_websocket_tab: 生成完了")
    return tab

# ===== スタンドアロン起動（単体テスト） =====
if __name__ == "__main__":
    root = tk.Tk()
    root.title("📡 WebSocket Tab (v17 compat)")
    root.geometry("1000x720")

    # 簡易バス
    if get_bus:
        bus = get_bus()  # ✅ シングルトン取得
    else:
        class _MiniBus:
            def __init__(self):
                self._subs = {}

            def subscribe(self, ev, cb):
                key = getattr(ev, "name", ev) if hasattr(ev, "name") else ev
                self._subs.setdefault(key, []).append(cb)
                print(f"[mini-bus] subscribe: {key}")
                return (key, cb)

            def unsubscribe(self, token_or_ev, cb=None):
                if isinstance(token_or_ev, tuple) and len(token_or_ev) == 2 and cb is None:
                    key, cb = token_or_ev
                else:
                    key = token_or_ev
                arr = self._subs.get(key, [])
                if cb in arr:
                    arr.remove(cb)

            def publish(self, ev, data=None, sender=None):
                key = getattr(ev, "name", ev) if hasattr(ev, "name") else ev
                print(f"[mini-bus] publish: {key} from {sender} data={data}")
                for cb in self._subs.get(key, []):
                    try:
                        cb(data, sender)
                    except Exception as e:
                        print("callback error:", e)

        bus = _MiniBus()

    tab = create_websocket_tab(root, message_bus=bus)

    # テストボタン（擬似接続/切断）
    testbar = ttk.Frame(root)
    testbar.pack(fill=tk.X, padx=10, pady=6)
    ttk.Button(
        testbar,
        text="🔌 擬似接続",
        command=lambda: bus.publish(
            Events.WS_CONNECT,
            {"url": "ws://127.0.0.1:11180/sub"},
            sender="selftest",
        ),
    ).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(
        testbar,
        text="🛑 擬似切断",
        command=lambda: bus.publish(
            Events.WS_DISCONNECT,
            {},
            sender="selftest",
        ),
    ).pack(side=tk.LEFT)

    root.mainloop()
