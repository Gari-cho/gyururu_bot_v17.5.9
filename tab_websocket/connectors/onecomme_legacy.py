# -*- coding: utf-8 -*-
"""
OneCommeLegacyConnector - OneComme 旧WebSocket方式

message_bridge.py から移植した、従来のOneComme WebSocket接続コネクタです。
ws://127.0.0.1:22280/ws または ws://127.0.0.1:11180/sub に接続します。

特徴:
- 自動再接続（指数バックオフ: 1.0s → 10.0s）
- websocket-client ライブラリ使用
- スレッドセーフ設計
"""

import threading
import json
import time
from .base import BaseCommentConnector

try:
    import websocket  # pip install websocket-client
    _HAS_WS = True
except Exception:
    _HAS_WS = False


class OneCommeLegacyConnector(BaseCommentConnector):
    """
    OneComme 旧WebSocket方式コネクタ

    message_bridge.py の _Bridge クラスを BaseCommentConnector に適合させた実装です。
    """

    def __init__(self, message_bus, logger):
        super().__init__(message_bus, logger)
        self.ws = None
        self._th = None
        self._stopped = False
        self._connected_once = False
        self._reconnect = False
        self._backoff = 1.0
        self._backoff_max = 10.0

    def connect(self, url: str) -> bool:
        """
        OneComme WebSocket接続を開始

        Args:
            url: 接続先URL (例: ws://127.0.0.1:22280/ws)

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
            time.sleep(0.5)  # 停止待ち

        # 接続開始
        self._stopped = False
        self._reconnect = True
        self._backoff = 1.0
        self._start_real()
        return True

    def disconnect(self):
        """OneComme WebSocket接続を切断"""
        self._stopped = True
        self._reconnect = False
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

    def _start_real(self):
        """WebSocket接続の実際の処理（スレッドで実行）"""

        def _on_open(ws):
            self._log("info", f"connected: {self._url}")
            self._publish_status("connected")
            self.connected = True
            self._connected_once = True
            # 接続できたらバックオフをリセット
            self._backoff = 1.0

        def _on_message(ws, message):
            try:
                # 生payloadログ（トラブル時の可視化）
                try:
                    self._log("debug", f"recv-raw: {str(message)[:200]}")
                except Exception:
                    pass

                payload = None
                if isinstance(message, (bytes, bytearray)):
                    try:
                        message = message.decode("utf-8", "ignore")
                    except Exception:
                        message = str(message)

                try:
                    obj = json.loads(message)

                    # v17.5 拡張payload形式
                    payload = {
                        "source": "onecomme_legacy",
                        "platform": obj.get("platform", "unknown"),
                        "user_id": obj.get("user_id", ""),
                        "user_name": obj.get("user") or obj.get("name") or obj.get("author") or "OneComme",
                        "message": obj.get("text") or obj.get("message") or obj.get("body") or "",
                        "raw": obj,
                        # 後方互換用
                        "text": obj.get("text") or obj.get("message") or obj.get("body") or "",
                        "user": obj.get("user") or obj.get("name") or obj.get("author") or "OneComme",
                    }
                except Exception:
                    payload = {
                        "source": "onecomme_legacy",
                        "platform": "unknown",
                        "user_id": "",
                        "user_name": "OneComme",
                        "message": str(message),
                        "raw": {},
                        # 後方互換用
                        "text": str(message),
                        "user": "OneComme",
                    }

                try:
                    self._log("info", f"recv-parsed: text='{(payload.get('message') or '')[:80]}' user='{payload.get('user_name','')}'")
                except Exception:
                    pass

                if payload and (payload.get("message") or "").strip():
                    self._publish_comment(payload)
                else:
                    self._log("debug", "recv(no-text): skip")
            except Exception as e:
                self._log("error", f"parse-error: {e}")

        def _on_error(ws, error):
            self._log("error", f"{error}")
            self._publish_status("error", error=str(error))
            self.connected = False

        def _on_close(ws, status_code, msg):
            self._log("info", f"disconnected: code={status_code} msg={msg}")
            self._publish_status("disconnected")
            self.connected = False

        def _runner():
            while not self._stopped:
                try:
                    self.ws = websocket.WebSocketApp(
                        self._url,
                        on_open=_on_open,
                        on_message=_on_message,
                        on_error=_on_error,
                        on_close=_on_close,
                    )
                    # KeepAlive設定（サーバ実装に依存）
                    self.ws.run_forever(ping_interval=20, ping_timeout=10)
                except Exception as e:
                    self._log("error", f"run_forever error: {e}")
                    self._publish_status("error", error=str(e))

                # 停止指示があればループ抜け
                if self._stopped or not self._reconnect:
                    break

                # 再接続バックオフ
                sleep_sec = min(self._backoff, self._backoff_max)
                self._log("info", f"reconnect in {sleep_sec:.1f}s")
                time.sleep(sleep_sec)
                self._backoff = min(self._backoff * 2, self._backoff_max)

        self._th = threading.Thread(target=_runner, daemon=True)
        self._th.start()

    def _log(self, level: str, message: str):
        """
        ログ出力（BaseCommentConnector をオーバーライド）

        WEBSOCKET_LOG イベントも発行して、connection_panel のログに表示します。
        """
        # 親クラスのログ出力
        super()._log(level, message)

        # WEBSOCKET_LOG イベント発行（connection_panel が購読）
        try:
            self.message_bus.publish(
                "WEBSOCKET_LOG",
                {"level": level, "msg": f"[OneCommeLegacy] {message}"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass
