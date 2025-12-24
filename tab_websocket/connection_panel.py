# -*- coding: utf-8 -*-
"""
connection_panel.py - WebSocket接続UI（v17.3.1 / ログ暴走抑制版 + Bouyomi互換サーバー）

- スライドスイッチ＋接続ログ
- 4秒以内に接続できなければ自動OFF
- 自動再接続は UI 側では行わない（無限ループ防止）
- 棒読みちゃん互換サーバー（MCV対応）
"""
import tkinter as tk
from tkinter import ttk
import threading
import logging
import time
import asyncio

logger = logging.getLogger(__name__)

# Bouyomi互換サーバー
try:
    from . import bouyomi_compat_server
    _HAS_BOUYOMI_SERVER = True
except ImportError:
    logger.warning("⚠️ bouyomi_compat_server モジュールが見つかりません")
    _HAS_BOUYOMI_SERVER = False

# --------------------------------------------------
# 🌐 OneComme 接続URLのデフォルト（最終フォールバック）
#   本当の値は UnifiedConfigManager の
#   "websocket.onecomme.url" に保存・読込する。
# --------------------------------------------------
DEFAULT_ONECOMME_URL = "ws://127.0.0.1:22280/ws"

class ConnectionControlPanel(ttk.Frame):
    def __init__(self, parent, message_bus=None, config_manager=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # --------------------------------------------------
        # 🧩 共有オブジェクト保持
        # --------------------------------------------------
        self.bus = message_bus
        self.config_manager = config_manager

        # 接続状態フラグなど
        self.connected = False
        self._auto_off_timer = None

        # MessageBus 購読管理
        self._subs = []

        # Bouyomi互換サーバー状態
        self.bouyomi_server_running = False
        self._last_status_state = None
        self._last_status_message = None

        # --------------------------------------------------
        # 🌐 OneComme URL 初期値（Config → デフォルトの順で採用）
        # --------------------------------------------------
        initial_url = DEFAULT_ONECOMME_URL
        if self.config_manager is not None:
            try:
                initial_url = self.config_manager.get(
                    "websocket.onecomme.url",
                    DEFAULT_ONECOMME_URL,
                )
            except Exception as e:
                logger.warning(f"⚠️ OneComme URL 読み込み失敗のためデフォルトを使用します: {e}")

        # GUI バインド用変数
        self.url_var = tk.StringVar(value=initial_url)

        # --------------------------------------------------
        # 🎛 UI 構築
        # --------------------------------------------------
        self._build_ui()

        # --------------------------------------------------
        # 📡 MessageBus イベント購読
        # --------------------------------------------------
        self._subscribe_bus()

    def _build_ui(self):
        # 上部: 接続トグル + URL欄
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(frm, text="🛰 OneComme 接続:").pack(side=tk.LEFT)

        self.var = tk.BooleanVar(value=False)
        self.switch = ttk.Checkbutton(
            frm,
            text="接続",
            variable=self.var,
            command=self._on_toggle,
            style="Switch.TCheckbutton",
        )
        self.switch.pack(side=tk.LEFT, padx=(6, 10))

        ttk.Label(frm, text="URL").pack(side=tk.LEFT)

        # --------------------------------------------------
        # 🌐 URL欄（config_manager から読んだ initial_url を使用）
        # --------------------------------------------------
        # ★ __init__ で self.url_var を初期化済みとして扱う
        self.url_entry = ttk.Entry(frm, textvariable=self.url_var, width=36)
        self.url_entry.pack(side=tk.LEFT, padx=(6, 0))

        # UI上は自動再接続チェックを残すが、現時点では「見た目だけ」扱い
        self.auto_reconnect = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frm,
            text="自動再接続",
            variable=self.auto_reconnect
        ).pack(side=tk.LEFT, padx=(10, 0))

        # --------------------------------------------------
        # 🎤 Bouyomi互換サーバー制御
        # --------------------------------------------------
        frm_bouyomi = ttk.Frame(self)
        frm_bouyomi.pack(fill=tk.X, padx=6, pady=(0, 6))

        ttk.Label(frm_bouyomi, text="🎤 Bouyomi互換サーバー:").pack(side=tk.LEFT)

        self.bouyomi_var = tk.BooleanVar(value=False)
        self.bouyomi_switch = ttk.Checkbutton(
            frm_bouyomi,
            text="起動",
            variable=self.bouyomi_var,
            command=self._on_bouyomi_toggle,
            style="Switch.TCheckbutton",
        )
        self.bouyomi_switch.pack(side=tk.LEFT, padx=(6, 10))

        ttk.Label(frm_bouyomi, text="Port:").pack(side=tk.LEFT)

        # ポート番号入力
        self.bouyomi_port_var = tk.StringVar(value="50010")
        if self.config_manager is not None:
            try:
                saved_port = self.config_manager.get("websocket.bouyomi.port", "50010")
                self.bouyomi_port_var.set(str(saved_port))
            except Exception:
                pass

        self.bouyomi_port_entry = ttk.Entry(
            frm_bouyomi,
            textvariable=self.bouyomi_port_var,
            width=8
        )
        self.bouyomi_port_entry.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(frm_bouyomi, text="（MCV → ここに送信）").pack(side=tk.LEFT, padx=(6, 0))

        # ログ表示欄
        self.log_text = tk.Text(self, height=10, bg="black", fg="white", wrap="none")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.log_text.insert("end", "=== WebSocket Log ===\n")


    def _on_toggle(self):
        val = self.var.get()
        if val:
            self._connect_request()
        else:
            self._disconnect_request()

    def _connect_request(self):
        if not self.bus:
            self._append("⚠️ MessageBus 未接続")
            self.var.set(False)
            return

        url = (self.url_var.get() or "").strip()
        if not url:
            self._append("⚠️ URL が空です")
            self.var.set(False)
            return

        # --------------------------------------------------
        # 💾 URLをConfigManagerに保存
        # --------------------------------------------------
        if self.config_manager is not None:
            try:
                self.config_manager.set("websocket.onecomme.url", url)
                self.config_manager.save()
                logger.info(f"💾 OneComme URL を保存しました: {url}")
            except Exception as e:
                logger.warning(f"⚠️ OneComme URL の保存に失敗しました: {e}")

        # 可視化ログ
        try:
            logger.info(f"🔗 WebSocket connect request: url={url}")
        except Exception:
            pass

        self.connected = False
        self._append("🔌 接続要求 → 4秒以内に成功しない場合自動OFF")

        # --------------------------------------------------
        # 📡 WEBSOCKET_CONNECT を発行（url付き）
        # --------------------------------------------------
        self.bus.publish("WEBSOCKET_CONNECT", {"url": url}, sender="connection_panel")

        # --------------------------------------------------
        # 🕒 タイムアウト監視（4秒）
        # --------------------------------------------------
        def _check_connect():
            if not self.connected:
                self._append("⚠️ 接続確認できず → スイッチ自動OFF")
                self.var.set(False)

        try:
            self.after(4000, _check_connect)
        except Exception:
            # 予備（通常は使われない）
            self._auto_off_timer = threading.Thread(
                target=self._fallback_timer,
                daemon=True,
            )
            self._auto_off_timer.start()

    def _fallback_timer(self):
        time.sleep(4)
        if not self.connected:
            self._append("⚠️ 接続確認できず（fallback）→ 自動OFF")
            try:
                self.var.set(False)
            except Exception:
                pass

    def _disconnect_request(self):
        if not self.bus:
            self._append("⚠️ MessageBus 未接続")
            return
        self.bus.publish("WEBSOCKET_DISCONNECT", {}, sender="connection_panel")
        self._append("🛑 切断要求を送信しました")

    def _subscribe_bus(self):
        """MessageBus から WS_STATUS を購読して UI に反映"""
        if not self.bus:
            return

        # WS_STATUS: {"state": "connected"/"disconnected"/"error", ...}
        try:
            def _on_status(data, sender=None):
                try:
                    self._on_ws_status(data or {})
                except Exception as e:
                    logger.exception("WebSocketステータス処理エラー: %s", e)

            tok = self.bus.subscribe("WS_STATUS", _on_status)
            self._subs.append(tok)
        except Exception:
            logger.exception("WS_STATUS購読エラー")

    def _on_ws_status(self, data: dict) -> None:
        """
        WebSocket ステータス通知ハンドラ（安全版）
        - state/status両対応
        - UI属性は存在チェックしてから触る
        - 同じ内容が連打される場合は1回だけ表示（ログ暴走防止）
        - 自動再接続は UI 側では行わない（無限ループ防止）
        """
        try:
            payload = data or {}
            state = payload.get("state") or payload.get("status") or ""
            message = payload.get("message") or payload.get("msg") or ""
            err = payload.get("error") or ""

            combined_msg = err or message or ""

            # ★ 同じ state + message/err が続く場合は UI には出さない
            if state == self._last_status_state and combined_msg == self._last_status_message:
                return
            self._last_status_state = state
            self._last_status_message = combined_msg

            # ログ出力用の安全なヘルパ
            def _safe_append(text: str):
                if hasattr(self, "_append") and callable(getattr(self, "_append")):
                    self._append(text)
                elif hasattr(self, "_append_log") and callable(getattr(self, "_append_log")):
                    self._append_log(text)

            # トグル用の安全セット
            def _safe_set_var(val: bool):
                if hasattr(self, "var"):
                    try:
                        self.var.set(val)
                    except Exception:
                        pass

            # 状態分岐
            if state == "connected":
                self.connected = True
                if combined_msg:
                    _safe_append(f"✅ 接続成功 - {combined_msg}")
                else:
                    _safe_append("✅ 接続成功")
                _safe_set_var(True)

            elif state == "disconnected":
                self.connected = False
                _safe_append("🛑 切断されました")
                _safe_set_var(False)

                # ★ ここでは自動再接続は行わない（無限ループ防止）

            elif state == "error":
                self.connected = False
                if combined_msg:
                    _safe_append(f"❌ 接続エラー: {combined_msg}")
                else:
                    _safe_append("❌ 接続エラー")
                _safe_set_var(False)

                # ★ ここでも自動再接続は行わない（無限ループ防止）

            else:
                # 未知状態はログだけ（状態変化があるときだけ）
                if state or combined_msg:
                    _safe_append(
                        f"[WS] {state or 'UNKNOWN'}"
                        f"{(' - ' + combined_msg) if combined_msg else ''}"
                    )

        except Exception as e:
            # ここで例外を握りつぶして“外には出さない”
            if hasattr(self, "_append") and callable(getattr(self, "_append")):
                self._append(f"[WS_STATUS handler error suppressed] {e}")
            elif hasattr(self, "_append_log") and callable(getattr(self, "_append_log")):
                self._append_log(f"[WS_STATUS handler error suppressed] {e}")

    def _append(self, text: str):
        try:
            self.log_text.insert("end", f"{text}\n")
            self.log_text.see("end")
        except Exception:
            pass

    # --------------------------------------------------
    # 🎤 Bouyomi互換サーバー制御
    # --------------------------------------------------

    def _on_bouyomi_toggle(self):
        """Bouyomi互換サーバーのトグル"""
        val = self.bouyomi_var.get()
        if val:
            self._start_bouyomi_server()
        else:
            self._stop_bouyomi_server()

    def _start_bouyomi_server(self):
        """Bouyomi互換サーバー起動"""
        if not _HAS_BOUYOMI_SERVER:
            self._append("⚠️ Bouyomi互換サーバーモジュールが利用できません")
            self.bouyomi_var.set(False)
            return

        if not self.bus:
            self._append("⚠️ MessageBus 未接続")
            self.bouyomi_var.set(False)
            return

        try:
            # ポート番号取得
            port_str = self.bouyomi_port_var.get().strip()
            if not port_str:
                port_str = "50010"

            try:
                port = int(port_str)
                if port < 1024 or port > 65535:
                    raise ValueError("ポート範囲外")
            except ValueError:
                self._append("⚠️ ポート番号が不正です（1024-65535）")
                self.bouyomi_var.set(False)
                return

            # ポート保存
            if self.config_manager is not None:
                try:
                    self.config_manager.set("websocket.bouyomi.port", port)
                    self.config_manager.save()
                except Exception as e:
                    logger.warning(f"⚠️ Bouyomiポート保存失敗: {e}")

            # サーバー起動（非同期）
            def _async_start():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    server = loop.run_until_complete(
                        bouyomi_compat_server.start_server(
                            self.bus,
                            host="0.0.0.0",
                            port=port
                        )
                    )

                    if server:
                        self.bouyomi_server_running = True
                        self.after(0, lambda: self._append(f"✅ Bouyomi互換サーバー起動: port {port}"))
                    else:
                        self.bouyomi_server_running = False
                        self.after(0, lambda: self._append(f"❌ Bouyomi互換サーバー起動失敗"))
                        self.after(0, lambda: self.bouyomi_var.set(False))

                except Exception as e:
                    logger.error(f"❌ Bouyomiサーバー起動エラー: {e}")
                    self.after(0, lambda: self._append(f"❌ Bouyomiサーバー起動エラー: {e}"))
                    self.after(0, lambda: self.bouyomi_var.set(False))

            th = threading.Thread(target=_async_start, daemon=True)
            th.start()

            self._append(f"🎤 Bouyomi互換サーバー起動中... port {port}")

        except Exception as e:
            logger.error(f"❌ Bouyomiサーバー起動エラー: {e}")
            self._append(f"❌ エラー: {e}")
            self.bouyomi_var.set(False)

    def _stop_bouyomi_server(self):
        """Bouyomi互換サーバー停止"""
        if not _HAS_BOUYOMI_SERVER:
            return

        try:
            # サーバー停止（非同期）
            def _async_stop():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    loop.run_until_complete(bouyomi_compat_server.stop_server())

                    self.bouyomi_server_running = False
                    self.after(0, lambda: self._append("🛑 Bouyomi互換サーバー停止"))

                except Exception as e:
                    logger.error(f"❌ Bouyomiサーバー停止エラー: {e}")
                    self.after(0, lambda: self._append(f"❌ 停止エラー: {e}"))

            th = threading.Thread(target=_async_stop, daemon=True)
            th.start()

            self._append("🛑 Bouyomi互換サーバー停止中...")

        except Exception as e:
            logger.error(f"❌ Bouyomiサーバー停止エラー: {e}")
            self._append(f"❌ エラー: {e}")


def create_connection_panel(parent, message_bus=None, config_manager=None, **kwargs):
    """
    WebSocketタブから呼ばれるファクトリ関数。

    - message_bus: MessageBus インスタンス
    - config_manager: UnifiedConfigManager（なくても動く）
    """
    return ConnectionControlPanel(
        parent,
        message_bus=message_bus,
        config_manager=config_manager,
        **kwargs,
    )

