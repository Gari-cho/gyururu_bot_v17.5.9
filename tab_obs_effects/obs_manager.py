# -*- coding: utf-8 -*-
"""
obs_manager.py - いずれのOBS連携差し込み口（現時点では未使用スタブ）
- 将来的に obs-websocket-py 等を使う場合、ここに実装を集約
- 今は存在チェック用のノーオペレーション
"""

from __future__ import annotations
from typing import Optional


class OBSManager:
    """未使用スタブ。将来のための差し込み口。"""

    def __init__(self, host: str = "localhost", port: int = 4455, password: Optional[str] = None) -> None:
        self.host = host
        self.port = port
        self.password = password
        self._connected = False

    def connect(self) -> bool:
        """常にFalse（未実装）。"""
        self._connected = False
        return self._connected

    def is_connected(self) -> bool:
        return self._connected

    def trigger(self, scene_or_event: str, **kwargs) -> None:
        """未実装。"""
        return

    def close(self) -> None:
        self._connected = False
