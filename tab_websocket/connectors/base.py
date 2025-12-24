# -*- coding: utf-8 -*-
"""
BaseCommentConnector - コメント接続コネクタの基底クラス

v17.5 "Multi Comment Bridge" で導入された、複数のコメント取得元を
統一的に扱うための基底クラスです。

各コネクタ（OneComme旧/新、マルチコメントビューワー、任意URL）は
このクラスを継承し、connect/disconnect メソッドを実装します。
"""

from typing import Optional, Callable
from abc import ABC, abstractmethod


class BaseCommentConnector(ABC):
    """
    コメント接続コネクタの基底クラス

    全てのコメント取得元コネクタはこのクラスを継承し、
    統一的なインターフェースで接続・切断・状態管理を行います。
    """

    def __init__(self, message_bus, logger):
        """
        Args:
            message_bus: MessageBusインスタンス（イベント発行用）
            logger: ロガーインスタンス（ログ出力用）
        """
        self.message_bus = message_bus
        self.logger = logger
        self.connected = False
        self._url = ""

    @abstractmethod
    def connect(self, url: str) -> bool:
        """
        WebSocket接続を開始

        Args:
            url: 接続先URL

        Returns:
            bool: 接続開始に成功した場合True（接続確立ではない）
        """
        raise NotImplementedError("connect() must be implemented by subclass")

    @abstractmethod
    def disconnect(self):
        """WebSocket接続を切断"""
        raise NotImplementedError("disconnect() must be implemented by subclass")

    def is_connected(self) -> bool:
        """
        接続状態を取得

        Returns:
            bool: 接続中の場合True
        """
        return self.connected

    def get_url(self) -> str:
        """
        現在の接続URL を取得

        Returns:
            str: 接続URL
        """
        return self._url

    def _publish_comment(self, payload: dict):
        """
        ONECOMME_COMMENT イベントとして統一出力

        Args:
            payload: コメントペイロード
                必須フィールド:
                - source: str (例: "onecomme_legacy", "multiviewer")
                - platform: str (例: "youtube", "twitch", "niconico", "unknown")
                - user_name: str
                - message: str
                - raw: dict (元のJSONデータ)

                オプションフィールド:
                - user_id: str
                - text: str (後方互換用)
                - user: str (後方互換用)
        """
        # 後方互換性のため、message → text, user_name → user も設定
        if "message" in payload and "text" not in payload:
            payload["text"] = payload["message"]
        if "user_name" in payload and "user" not in payload:
            payload["user"] = payload["user_name"]

        self.message_bus.publish(
            "ONECOMME_COMMENT",
            payload,
            sender=self.__class__.__name__,
        )

    def _publish_status(self, state: str, error: Optional[str] = None):
        """
        WS_STATUS イベントを発行

        Args:
            state: 状態 ("connected", "disconnected", "error")
            error: エラーメッセージ（stateが"error"の場合のみ）
        """
        payload = {
            "state": state,
            "url": self._url,
            "connector": self.__class__.__name__,
        }
        if error:
            payload["error"] = error

        self.message_bus.publish(
            "WS_STATUS",
            payload,
            sender=self.__class__.__name__,
        )

    def _log(self, level: str, message: str):
        """
        ログ出力

        Args:
            level: ログレベル ("info", "warning", "error", "debug")
            message: ログメッセージ
        """
        log_method = getattr(self.logger, level, None)
        if log_method:
            log_method(f"[{self.__class__.__name__}] {message}")
