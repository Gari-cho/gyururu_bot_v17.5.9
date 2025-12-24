# -*- coding: utf-8 -*-
"""
tab_websocket.websocket_core (v17.2 stable-min)
- OneComme WebSocket 導線の最小コア
- UnifiedConfigManager から onecomme.url を取得して Bridge を起動
- MessageBus / Bridge が未実装でも落ちないフォールバック

ログ目安:
  🔗 WebSocket 接続オープン: ws://127.0.0.1:11180/sub
  🌐 Bridge 起動: OneCommeBridge
"""

from __future__ import annotations
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 共有（存在しなくても動くようにフォールバック）
try:
    from shared.message_bus import MessageBus, EventTypes, get_message_bus
except Exception:
    class MessageBus:
        def subscribe(self, *a, **k): pass
        def publish(self, *a, **k): pass
    class EventTypes:
        CHAT_MESSAGE = "CHAT_MESSAGE"
        ONECOMME_COMMENT = "ONECOMME_COMMENT"
        CONFIG_UPDATED = "CONFIG_UPDATED"
        STATUS_LOG = "STATUS_LOG"
        ERROR_ALERT = "ERROR_ALERT"
    def get_message_bus():
        return MessageBus()

# OneComme Bridge（本実装が無ければダミー）
try:
    from .message_bridge import OneCommeBridge as _RealOneCommeBridge  # type: ignore
except Exception:
    _RealOneCommeBridge = None

class _FallbackOneCommeBridge:
    """Bridge が見つからない時の no-op"""
    def __init__(self, message_bus: MessageBus, url: str = ""):
        self.message_bus = message_bus
        self.url = url
        self._running = False
        self._th: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        # ダミースレッド（何もしない）
        def _run():
            while self._running:
                # 実ワークなし
                pass
        self._th = threading.Thread(target=_run, name="FallbackOneCommeBridge", daemon=True)
        self._th.start()
        logger.info("🌐 Bridge 起動: FallbackOneCommeBridge (no-op)")

    def stop(self):
        self._running = False

class WebSocketCore:
    """OneComme 接続の最小コア（Bridge 起動/停止を司る）"""
    def __init__(self, message_bus: Optional[MessageBus] = None, config_manager=None):
        self.message_bus = message_bus or get_message_bus()
        self.config_manager = config_manager
        self.bridge = None  # type: ignore
        self._running = False

    def start(self):
        """設定から URL を読み取り Bridge を起動"""
        try:
            cfg = self.config_manager
            default_url = "ws://127.0.0.1:11180/sub"
            try:
                onecomme_url = cfg.get("onecomme.url", default_url) if cfg else default_url
            except Exception:
                onecomme_url = default_url

            logger.info(f"🔗 WebSocket 接続オープン: {onecomme_url}")

            BridgeClass = _RealOneCommeBridge if _RealOneCommeBridge else _FallbackOneCommeBridge
            # Real Bridge: (message_bus, config_manager, url) で初期化される想定が多いので両対応
            try:
                self.bridge = BridgeClass(self.message_bus, self.config_manager, onecomme_url)  # type: ignore[arg-type]
            except TypeError:
                self.bridge = BridgeClass(self.message_bus, onecomme_url)  # type: ignore

            self.bridge.start()
            logger.info("🌐 Bridge 起動: {}".format(
                getattr(self.bridge, "__class__", type(self.bridge)).__name__
            ))
            self._running = True

        except Exception as e:
            logger.error(f"WebSocketCore 起動失敗: {e}")
            try:
                self.message_bus.publish(EventTypes.ERROR_ALERT, {"message": f"WebSocket 起動失敗: {e}"}, sender="tab_websocket")
            except Exception:
                pass

    def stop(self):
        """Bridge 停止"""
        try:
            if getattr(self.bridge, "stop", None):
                self.bridge.stop()
        except Exception:
            pass
        self._running = False


# 工場関数（必要なら）
def create_websocket_core(message_bus: Optional[MessageBus] = None, config_manager=None) -> WebSocketCore:
    return WebSocketCore(message_bus=message_bus, config_manager=config_manager)
