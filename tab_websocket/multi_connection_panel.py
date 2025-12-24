# -*- coding: utf-8 -*-
"""
multi_connection_panel.py - v17.5 Multi Comment Bridge UI

複数のコメント取得元（OneComme旧/新、マルチコメントビューワー、任意URL）を
並列で接続できるUIパネルです。

特徴:
- 4つの接続方式を並列で配置
- 各接続方式は独立してON/OFF可能
- 接続失敗時は自動OFF（4秒タイムアウト）
- ログパネルは全接続方式で共有
"""

import tkinter as tk
from tkinter import ttk
import threading
import logging
import time

from .connectors import (
    OneCommeLegacyConnector,
    OneCommeNewConnector,
    MultiViewerConnector,
    ManualConnector,
    BouyomiCompatServerConnector,
    TCPCommentClientConnector,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------
# デフォルトURL定義
# --------------------------------------------------
DEFAULT_URLS = {
    "onecomme_legacy": "ws://127.0.0.1:22280/ws",
    "onecomme_new": "ws://127.0.0.1:11180/sub",
    "multiviewer": "ws://localhost:7000",
    "manual": "ws://localhost:8080",
}


class ConnectorRow(ttk.Frame):
    """
    1つの接続方式を表すUI行

    チェックボックス + URL欄 + コネクタインスタンスで構成されます。
    """

    def __init__(
        self,
        parent,
        label: str,
        connector_id: str,
        connector_class,
        message_bus,
        logger_instance,
        config_manager=None,
        default_url: str = "",
        on_log_callback=None,
        input_mode: str = "url",  # "url" または "port"
    ):
        """
        Args:
            parent: 親ウィジェット
            label: 表示ラベル（例: "OneComme（旧方式）"）
            connector_id: コネクタ識別子（例: "onecomme_legacy"）
            connector_class: コネクタクラス
            message_bus: MessageBusインスタンス
            logger_instance: ロガーインスタンス
            config_manager: UnifiedConfigManager（オプション）
            default_url: デフォルトURL（input_mode="port"の場合はポート番号文字列）
            on_log_callback: ログ出力コールバック
            input_mode: 入力モード（"url" または "port"）
        """
        super().__init__(parent)

        self.label = label
        self.connector_id = connector_id
        self.connector_class = connector_class
        self.bus = message_bus
        self.logger_instance = logger_instance
        self.config_manager = config_manager
        self.on_log = on_log_callback
        self.input_mode = input_mode

        # コネクタインスタンス
        self.connector = None

        # 接続状態
        self.connected = False
        self._timeout_timer = None

        # URL/ポート初期値（Config → デフォルトの順で採用）
        initial_url = default_url
        if self.config_manager is not None:
            try:
                config_key = f"websocket.{connector_id}.url" if input_mode == "url" else f"connections.{connector_id}.port"
                initial_url = str(self.config_manager.get(config_key, default_url))
            except Exception as e:
                logger.warning(f"⚠️ {connector_id} 設定読み込み失敗: {e}")

        self.url_var = tk.StringVar(value=initial_url)
        self.var = tk.BooleanVar(value=False)

        # UI構築
        self._build_ui()

    def _build_ui(self):
        """UI構築"""
        # ラベル（幅を40に拡大してわんコメ対応表記が収まるように）
        ttk.Label(self, text=self.label, width=40).pack(side=tk.LEFT, padx=(0, 6))

        # チェックボックス
        self.checkbox = ttk.Checkbutton(
            self,
            text="接続",
            variable=self.var,
            command=self._on_toggle,
        )
        self.checkbox.pack(side=tk.LEFT, padx=(0, 10))

        # URL/ポート入力欄
        if self.input_mode == "port":
            ttk.Label(self, text="ポート:").pack(side=tk.LEFT)
            self.url_entry = ttk.Entry(self, textvariable=self.url_var, width=10)
            self.url_entry.pack(side=tk.LEFT, padx=(4, 0))
        else:
            ttk.Label(self, text="URL:").pack(side=tk.LEFT)
            self.url_entry = ttk.Entry(self, textvariable=self.url_var, width=40)
            self.url_entry.pack(side=tk.LEFT, padx=(4, 0))

    def _on_toggle(self):
        """チェックボックスのトグルハンドラ"""
        val = self.var.get()
        if val:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        """接続開始"""
        value = (self.url_var.get() or "").strip()
        if not value:
            field_name = "ポート" if self.input_mode == "port" else "URL"
            self._log("warning", f"⚠️ {field_name} が空です")
            self.var.set(False)
            return

        # 設定をConfigManagerに保存
        if self.config_manager is not None:
            try:
                if self.input_mode == "port":
                    config_key = f"connections.{self.connector_id}.port"
                    # ポート番号として保存（数値検証）
                    try:
                        port_num = int(value)
                        self.config_manager.set(config_key, port_num)
                    except ValueError:
                        self._log("warning", f"⚠️ 不正なポート番号: {value}")
                        self.var.set(False)
                        return
                else:
                    config_key = f"websocket.{self.connector_id}.url"
                    self.config_manager.set(config_key, value)

                self.config_manager.save()
                logger.info(f"💾 {self.connector_id} 設定を保存しました: {value}")
            except Exception as e:
                logger.warning(f"⚠️ {self.connector_id} 設定の保存に失敗しました: {e}")

        # コネクタインスタンス作成
        if self.connector is None:
            self.connector = self.connector_class(self.bus, self.logger_instance)

        # 接続開始
        self._log("info", f"🔌 接続要求: {value}")
        self.connected = False

        try:
            # port モードの場合は整数に変換して渡す
            if self.input_mode == "port":
                success = self.connector.connect(int(value))
            else:
                success = self.connector.connect(value)

            if not success:
                self._log("error", "❌ 接続開始に失敗しました")
                self.var.set(False)
                return
        except Exception as e:
            self._log("error", f"❌ 接続エラー: {e}")
            self.var.set(False)
            return

        # タイムアウト監視（3秒） - v17.3 Phase 4
        def _check_timeout():
            time.sleep(3.0)
            if not self.connected:
                self._log("warning", "⚠️ 接続タイムアウト（3秒）→ 自動OFF")
                try:
                    self.var.set(False)
                    if self.connector:
                        self.connector.disconnect()
                except Exception:
                    pass

        self._timeout_timer = threading.Thread(target=_check_timeout, daemon=True)
        self._timeout_timer.start()

    def _disconnect(self):
        """接続切断"""
        if self.connector:
            try:
                self.connector.disconnect()
                self._log("info", "🛑 切断しました")
            except Exception as e:
                self._log("error", f"❌ 切断エラー: {e}")

        self.connected = False

    def on_status_update(self, state: str, connector_name: str):
        """
        WS_STATUS イベントのハンドラ

        Args:
            state: 状態 ("connected", "disconnected", "error")
            connector_name: コネクタクラス名
        """
        # 自分のコネクタかチェック
        if self.connector and connector_name == self.connector.__class__.__name__:
            if state == "connected":
                self.connected = True
                self._log("info", "✅ 接続成功")
                try:
                    self.var.set(True)
                except Exception:
                    pass
            elif state == "disconnected":
                self.connected = False
                self._log("info", "🛑 切断されました")
                try:
                    self.var.set(False)
                except Exception:
                    pass
            elif state == "error":
                self.connected = False
                # エラーメッセージはコネクタ側でログ出力済み
                try:
                    self.var.set(False)
                except Exception:
                    pass

    def _log(self, level: str, message: str):
        """ログ出力"""
        prefix = f"[{self.label}]"
        full_message = f"{prefix} {message}"

        # ロガーに出力
        log_method = getattr(logger, level, None)
        if log_method:
            log_method(full_message)

        # UI ログコールバック
        if self.on_log:
            try:
                self.on_log(full_message)
            except Exception:
                pass


class MultiConnectionPanel(ttk.Frame):
    """
    v17.5 Multi Comment Bridge メインパネル

    4つの接続方式を並列で配置し、それぞれ独立して接続・切断できます。
    """

    def __init__(self, parent, message_bus=None, config_manager=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.bus = message_bus
        self.config_manager = config_manager

        # コネクタ行のリスト
        self.connector_rows = []

        # WS_STATUSイベントのハンドラトークン
        self._subs = []

        # UI構築
        self._build_ui()

        # MessageBus購読
        self._subscribe_bus()

    def _build_ui(self):
        """UI構築"""
        # ヘッダー（見出し）
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=6, pady=(6, 4))
        ttk.Label(
            header,
            text="📡 Multi Comment Bridge",
            font=("", 12, "bold"),
        ).pack(side=tk.LEFT)

        # コネクタ行エリア（ボックスを1文字右にずらす）
        connector_area = ttk.Frame(self)
        connector_area.pack(fill=tk.X, padx=(12, 6), pady=6)

        # v17.5 接続方式の配置（優先度順）
        connectors_config = [
            # 1. 棒読みちゃん互換（わんコメ/OneComme/MCV対応）- TCP サーバ
            {
                "label": "棒読み互換（わんコメ/OneComme/MCV対応）",
                "connector_id": "mcv_bouyomi",
                "connector_class": BouyomiCompatServerConnector,
                "default_url": "50010",  # デフォルトポート
                "input_mode": "port",
            },
            # 2. TCPコメントクライアント（外部サーバー接続）- v17.3 Phase 5 [実装途中]
            {
                "label": "TCPコメント（外部サーバー）[実装途中]",
                "connector_id": "tcp_comment_client",
                "connector_class": TCPCommentClientConnector,
                "default_url": "127.0.0.1:50000",  # デフォルト: host:port
                "input_mode": "url",
            },
            # 3. 任意URL接続 [実装途中]
            {
                "label": "任意URL（自前接続）[実装途中]",
                "connector_id": "manual",
                "connector_class": ManualConnector,
                "default_url": DEFAULT_URLS["manual"],
                "input_mode": "url",
            },
            # 4. OneComme（新方式）[実装途中]
            {
                "label": "OneComme（新方式）[実装途中]",
                "connector_id": "onecomme_new",
                "connector_class": OneCommeNewConnector,
                "default_url": DEFAULT_URLS["onecomme_new"],
                "input_mode": "url",
            },
            # 5. OneComme（旧方式 / Legacy）[実装途中]
            {
                "label": "OneComme（旧方式）[実装途中]",
                "connector_id": "onecomme_legacy",
                "connector_class": OneCommeLegacyConnector,
                "default_url": DEFAULT_URLS["onecomme_legacy"],
                "input_mode": "url",
            },
        ]

        for cfg in connectors_config:
            row = ConnectorRow(
                connector_area,
                label=cfg["label"],
                connector_id=cfg["connector_id"],
                connector_class=cfg["connector_class"],
                message_bus=self.bus,
                logger_instance=logger,
                config_manager=self.config_manager,
                default_url=cfg["default_url"],
                on_log_callback=self._append_log,
                input_mode=cfg.get("input_mode", "url"),
            )
            row.pack(fill=tk.X, pady=2)
            self.connector_rows.append(row)

        # ログ表示欄
        log_frame = ttk.LabelFrame(self, text="接続ログ")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self.log_text = tk.Text(
            log_frame,
            height=12,
            bg="black",
            fg="white",
            wrap="none",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.log_text.insert("end", "=== v17.5 Multi Comment Bridge Log ===\n")

    def _append_log(self, text: str):
        """ログテキストに追記"""
        try:
            self.log_text.insert("end", f"{text}\n")
            self.log_text.see("end")
        except Exception:
            pass

    def _subscribe_bus(self):
        """MessageBusイベント購読"""
        if not self.bus:
            return

        # WS_STATUS イベント購読
        try:
            def _on_status(data, sender=None):
                try:
                    self._on_ws_status(data or {})
                except Exception as e:
                    logger.exception("WS_STATUS処理エラー: %s", e)

            tok = self.bus.subscribe("WS_STATUS", _on_status)
            self._subs.append(tok)
        except Exception:
            logger.exception("WS_STATUS購読エラー")

        # WEBSOCKET_LOG イベント購読（コネクタからのログ）
        try:
            def _on_log(data, sender=None):
                try:
                    payload = data or {}
                    level = payload.get("level", "info")
                    msg = payload.get("msg", "")
                    if msg:
                        self._append_log(msg)
                except Exception as e:
                    logger.exception("WEBSOCKET_LOG処理エラー: %s", e)

            tok = self.bus.subscribe("WEBSOCKET_LOG", _on_log)
            self._subs.append(tok)
        except Exception:
            logger.exception("WEBSOCKET_LOG購読エラー")

    def _on_ws_status(self, data: dict):
        """WS_STATUS イベントハンドラ"""
        try:
            state = data.get("state", "")
            connector_name = data.get("connector", "")

            # 各コネクタ行に通知
            for row in self.connector_rows:
                try:
                    row.on_status_update(state, connector_name)
                except Exception as e:
                    logger.exception(f"コネクタ行のステータス更新エラー: {e}")

        except Exception as e:
            logger.exception(f"WS_STATUSハンドラエラー: {e}")


def create_multi_connection_panel(parent, message_bus=None, config_manager=None, **kwargs):
    """
    WebSocketタブから呼ばれるファクトリ関数

    Args:
        parent: 親ウィジェット
        message_bus: MessageBusインスタンス
        config_manager: UnifiedConfigManager（オプション）

    Returns:
        MultiConnectionPanel インスタンス
    """
    return MultiConnectionPanel(
        parent,
        message_bus=message_bus,
        config_manager=config_manager,
        **kwargs,
    )
