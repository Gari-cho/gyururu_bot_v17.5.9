# -*- coding: utf-8 -*-
"""
shared/streamer_profile_message_bridge.py (v17.3)
- 配信者プロフィール関連の最小ブリッジ
- 生成時に STREAMER_PROFILE_READY を流すだけの安全版
- 呼び出し側からの引数差異に強く、message_bus/bus どちらでも受ける
"""

from __future__ import annotations
from typing import Optional, Any, Dict

try:
    from shared.message_bus import MessageBus, get_message_bus
    from shared.event_types import Events
except Exception:
    class MessageBus:
        def publish(self, *a, **k): pass
        def subscribe(self, *a, **k): pass
    def get_message_bus():  # type: ignore
        return MessageBus()
    class Events:
        STREAMER_PROFILE_READY = "STREAMER_PROFILE_READY"

class StreamerProfileMessageBridge:
    def __init__(
        self,
        bus: Optional[MessageBus] = None,
        message_bus: Optional[MessageBus] = None,
        config_manager: Any = None,
        **kwargs,
    ) -> None:
        # bus / message_bus のどちらでもOK
        self.bus = bus or message_bus or get_message_bus()
        self.config_manager = config_manager

    def start(self) -> None:
        """最低限、READY を一度流す。"""
        payload: Dict[str, Any] = {
            "profile": "default",
            "display_name": "Streamer",
        }
        try:
            self.bus.publish(Events.STREAMER_PROFILE_READY, payload, sender="streamer_profile_bridge")
        except Exception:
            pass

    # no-op
    def stop(self) -> None:
        pass

# 互換エントリ
def create_bridge(*args, **kwargs) -> StreamerProfileMessageBridge:
    b = StreamerProfileMessageBridge(*args, **kwargs)
    b.start()
    return b
