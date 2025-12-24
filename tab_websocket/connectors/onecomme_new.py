# -*- coding: utf-8 -*-
"""
OneCommeNewConnector - OneComme 新接続方式

OneComme の新しい接続方式のコネクタです（最小実装）。
具体的な仕様が判明次第、実装を拡張します。

現在の状態:
- 接続/切断のログ出力のみ
- WebSocket接続は未実装（仕様不明のため）
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


class OneCommeNewConnector(BaseCommentConnector):
    """
    OneComme 新接続方式コネクタ（最小実装）

    TODO: 新しい接続方式の仕様が判明次第、実装を追加
    """

    def __init__(self, message_bus, logger):
        super().__init__(message_bus, logger)
        self.ws = None
        self._th = None
        self._stopped = False

    def connect(self, url: str) -> bool:
        """
        OneComme 新方式で接続を開始（最小実装）

        Args:
            url: 接続先URL

        Returns:
            bool: 接続開始に成功した場合True
        """
        self._url = url
        self._log("info", f"OneComme新接続方式（最小実装）: {url}")
        self._log("warning", "新接続方式の詳細仕様が未実装です")

        if not _HAS_WS:
            self._log("error", "websocket-client がインストールされていません")
            self._publish_status("error", error="websocket-client not installed")
            return False

        # TODO: 新接続方式の実装
        # 現在は接続ログのみ出力
        self._publish_status("connected")
        self.connected = True

        # WEBSOCKET_LOG イベント発行
        try:
            self.message_bus.publish(
                "WEBSOCKET_LOG",
                {"level": "info", "msg": "[OneCommeNew] 接続開始（最小実装）"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass

        return True

    def disconnect(self):
        """OneComme 新方式の接続を切断"""
        self._log("info", "切断")
        self.connected = False
        self._publish_status("disconnected")

        # WEBSOCKET_LOG イベント発行
        try:
            self.message_bus.publish(
                "WEBSOCKET_LOG",
                {"level": "info", "msg": "[OneCommeNew] 切断"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass

    def _log(self, level: str, message: str):
        """ログ出力"""
        super()._log(level, message)

        # WEBSOCKET_LOG イベント発行
        try:
            self.message_bus.publish(
                "WEBSOCKET_LOG",
                {"level": level, "msg": f"[OneCommeNew] {message}"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass
