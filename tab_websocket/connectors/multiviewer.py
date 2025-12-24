# -*- coding: utf-8 -*-
"""
MultiViewerConnector - マルチコメントビューワー接続

マルチコメントビューワーからコメントを受信するコネクタです（最小実装）。
JSONフォーマットの詳細が判明次第、実装を拡張します。

現在の状態:
- WebSocket接続ループのみ実装
- メッセージ受信時のログ出力
- JSON解析は基本的なフィールドのみ対応
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


class MultiViewerConnector(BaseCommentConnector):
    """
    マルチコメントビューワーコネクタ（最小実装）

    基本的な受信ループを実装しています。
    JSONフォーマットの詳細が判明次第、パース処理を拡張します。
    """

    def __init__(self, message_bus, logger):
        super().__init__(message_bus, logger)
        self.ws = None
        self._th = None
        self._stopped = False

    def connect(self, url: str) -> bool:
        """
        マルチコメントビューワーに接続

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
        """マルチコメントビューワー接続を切断"""
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

                    # 最小実装: 一般的なフィールドを試行
                    # TODO: マルチコメントビューワーの実際のJSONフォーマットに合わせて調整
                    payload = {
                        "source": "multiviewer",
                        "platform": obj.get("platform", obj.get("service", "unknown")),
                        "user_id": obj.get("userId", obj.get("user_id", "")),
                        "user_name": obj.get("userName", obj.get("user_name", obj.get("name", "Unknown"))),
                        "message": obj.get("comment", obj.get("message", obj.get("text", ""))),
                        "raw": obj,
                        # 後方互換用
                        "text": obj.get("comment", obj.get("message", obj.get("text", ""))),
                        "user": obj.get("userName", obj.get("user_name", obj.get("name", "Unknown"))),
                    }
                except Exception as e:
                    self._log("warning", f"JSON parse error: {e}, treating as plain text")
                    payload = {
                        "source": "multiviewer",
                        "platform": "unknown",
                        "user_id": "",
                        "user_name": "MultiViewer",
                        "message": str(message),
                        "raw": {},
                        # 後方互換用
                        "text": str(message),
                        "user": "MultiViewer",
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
                {"level": level, "msg": f"[MultiViewer] {message}"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass
