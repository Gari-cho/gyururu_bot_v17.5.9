# -*- coding: utf-8 -*-
"""
ManualConnector - 任意URL接続

ユーザーが指定した任意のWebSocket URLに接続し、
コメントを受信するコネクタです。

特徴:
- 任意のWebSocket URLに接続可能
- 受信JSONフォーマットを柔軟に解析
- 不明なフォーマットでも基本的な処理を試行
"""

import threading
import json
import time
from .base import BaseCommentConnector

try:
    import websocket
    _HAS_WS = True
except Exception:
    _HAS_WS = False


class ManualConnector(BaseCommentConnector):
    """
    任意URL接続コネクタ

    ユーザーが指定したWebSocket URLに接続し、
    受信メッセージを柔軟に解析してコメントとして処理します。
    """

    def __init__(self, message_bus, logger):
        super().__init__(message_bus, logger)
        self.ws = None
        self._th = None
        self._stopped = False

    def connect(self, url: str) -> bool:
        """
        任意のWebSocket URLに接続

        Args:
            url: 接続先URL

        Returns:
            bool: 接続開始に成功した場合True
        """
        self._url = url

        if not _HAS_WS:
            self._log("error", "websocket-client がインストールされていません")
            self._publish_status("error", error="websocket-client not installed")
            return False

        # 既存の接続があれば停止
        if self._th and self._th.is_alive():
            self.disconnect()
            time.sleep(0.5)

        # 接続開始
        self._stopped = False
        self._start_connection()
        return True

    def disconnect(self):
        """任意URL接続を切断"""
        self._stopped = True
        self.connected = False

        try:
            if self.ws and _HAS_WS:
                self.ws.close()
        except Exception:
            pass

        try:
            self._publish_status("disconnected")
        except Exception:
            pass

    def _start_connection(self):
        """WebSocket接続開始（スレッドで実行）"""

        def _on_open(ws):
            self._log("info", f"connected: {self._url}")
            self._publish_status("connected")
            self.connected = True

        def _on_message(ws, message):
            try:
                # 受信メッセージをログ出力
                self._log("debug", f"recv-raw: {str(message)[:200]}")

                payload = None
                if isinstance(message, (bytes, bytearray)):
                    try:
                        message = message.decode("utf-8", "ignore")
                    except Exception:
                        message = str(message)

                try:
                    obj = json.loads(message)

                    # 柔軟なフィールド検出
                    # よくあるフィールド名を複数試行
                    message_text = (
                        obj.get("message") or
                        obj.get("text") or
                        obj.get("comment") or
                        obj.get("body") or
                        obj.get("content") or
                        ""
                    )

                    user_name = (
                        obj.get("user") or
                        obj.get("name") or
                        obj.get("userName") or
                        obj.get("user_name") or
                        obj.get("author") or
                        obj.get("displayName") or
                        "Unknown"
                    )

                    user_id = (
                        obj.get("userId") or
                        obj.get("user_id") or
                        obj.get("id") or
                        ""
                    )

                    platform = (
                        obj.get("platform") or
                        obj.get("service") or
                        obj.get("source") or
                        "unknown"
                    )

                    payload = {
                        "source": "manual",
                        "platform": platform,
                        "user_id": user_id,
                        "user_name": user_name,
                        "message": message_text,
                        "raw": obj,
                        # 後方互換用
                        "text": message_text,
                        "user": user_name,
                    }
                except Exception as e:
                    self._log("warning", f"JSON parse error: {e}, treating as plain text")
                    payload = {
                        "source": "manual",
                        "platform": "unknown",
                        "user_id": "",
                        "user_name": "Manual",
                        "message": str(message),
                        "raw": {},
                        # 後方互換用
                        "text": str(message),
                        "user": "Manual",
                    }

                self._log("info", f"recv-parsed: text='{(payload.get('message') or '')[:80]}' user='{payload.get('user_name','')}'")

                if payload and (payload.get("message") or "").strip():
                    self._publish_comment(payload)
                else:
                    self._log("debug", "recv(no-text): skip")

            except Exception as e:
                self._log("error", f"message handler error: {e}")

        def _on_error(ws, error):
            self._log("error", f"{error}")
            self._publish_status("error", error=str(error))
            self.connected = False

        def _on_close(ws, status_code, msg):
            self._log("info", f"disconnected: code={status_code} msg={msg}")
            self._publish_status("disconnected")
            self.connected = False

        def _runner():
            try:
                self.ws = websocket.WebSocketApp(
                    self._url,
                    on_open=_on_open,
                    on_message=_on_message,
                    on_error=_on_error,
                    on_close=_on_close,
                )
                self.ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                self._log("error", f"run_forever error: {e}")
                self._publish_status("error", error=str(e))

        self._th = threading.Thread(target=_runner, daemon=True)
        self._th.start()

    def _log(self, level: str, message: str):
        """ログ出力"""
        super()._log(level, message)

        # WEBSOCKET_LOG イベント発行
        try:
            self.message_bus.publish(
                "WEBSOCKET_LOG",
                {"level": level, "msg": f"[Manual] {message}"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass
