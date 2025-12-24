# -*- coding: utf-8 -*-
"""
Enhanced Message Handler（v17.2 → v17.3.1 互換版）
- WebSocket/Chat → AI → Voice の最短導線を司る常駐ハンドラ
- 依存: MessageBus / UnifiedConfigManager / 任意の ai_connector
- 安全第一：AI非搭載でも落ちず、必要イベントのみ発火

⚠️ v17.3.1 変更点：
  - AI_REQUEST 購読を無効化（AIIntegrationManager に一本化）
  - AI_RESPONSE 発行を無効化（二重応答防止）
  - ONECOMME_COMMENT / CHAT_MESSAGE の購読は維持（互換性のため）
"""

from __future__ import annotations
from typing import Any, Optional, Callable, Dict
import random
import threading

from .logger import get_logger
from .message_bus import MessageBus
from .event_types import Events, ET
from .config_helper import ai_enabled, ai_response_probability, ai_trigger_keywords

logger = get_logger("shared.enhanced_handler")

class _EnhancedHandler:
    def __init__(self, message_bus: MessageBus, config_manager: Any, ai_connector: Any):
        self.bus = message_bus
        self.config = config_manager
        self.ai = ai_connector
        self._subs = []
        self._lock = threading.RLock()

        # 購読：外部コメント → チャット → AI
        self._subscribe(Events.ONECOMME_COMMENT, self._on_onecomme_comment)
        self._subscribe(Events.CHAT_MESSAGE, self._on_chat_message)

        # ❌ v17.3.1: AI_REQUEST 購読を無効化（AIIntegrationManager に一本化）
        # AIIntegrationManager が AI_REQUEST を処理するため、ここでの購読は不要
        # （二重応答の原因となるため無効化）
        # self._subscribe(Events.AI_REQUEST, self._on_ai_request)

        logger.info("✅ EnhancedMessageHandler: 購読を開始しました（v17.3.1: AI_REQUEST無効）")

    # ---- バス工具
    def _subscribe(self, ev: Any, cb: Callable):
        self.bus.subscribe(ev, cb)

    def cleanup(self):
        # 今回の実装では MessageBus に unsubscribe API あり
        try:
            for e, cb in self._subs:
                self.bus.unsubscribe(e, cb)
        except Exception:
            pass

    # ---- 受信ハンドラ
    def _on_onecomme_comment(self, data: Dict[str, Any], sender=None):
        try:
            if not data:
                return
            text = (data.get("text") or "").strip()
            user = data.get("user") or data.get("username") or "unknown"
            if not text:
                return

            # 表示イベント（UI向け）
            self.bus.publish(Events.CHAT_MESSAGE, {
                "platform": "youtube",
                "service": "onecomme",
                "username": user,
                "user_id": data.get("user_id"),
                "text": text,
                "timestamp": data.get("timestamp"),
                "meta": data.get("meta", {}),
            })

            # AIトリガ判定
            self._maybe_request_ai(text=text, username=user, raw=data)

        except Exception as e:
            logger.error(f"❌ ONECOMME_COMMENT処理エラー: {e}")

    def _on_chat_message(self, payload: Dict[str, Any], sender=None):
        try:
            # GUIの手動入力などもここに到達する想定
            text = (payload or {}).get("text", "").strip()
            user = (payload or {}).get("username", "UI")
            if not text:
                return
            self._maybe_request_ai(text=text, username=user, raw=payload)
        except Exception as e:
            logger.warning(f"⚠️ CHAT_MESSAGE処理警告: {e}")

    # ❌ v17.3.1: AI_REQUEST 処理を無効化（AIIntegrationManager に一本化）
    # def _on_ai_request(self, payload: Dict[str, Any], sender=None):
    #     try:
    #         text = (payload or {}).get("text", "").strip()
    #         username = (payload or {}).get("username", "system")
    #         if not text:
    #             return
    #         self._generate_and_emit(text=text, username=username, raw=payload)
    #     except Exception as e:
    #         logger.error(f"❌ AI_REQUEST処理エラー: {e}")

    # ---- AI判定・実行
    def _maybe_request_ai(self, *, text: str, username: str, raw: Dict[str, Any]):
        if not ai_enabled():
            return
        # キーワード
        kws = [k.lower() for k in ai_trigger_keywords()]
        lower = text.lower()
        if kws and not any(k in lower for k in kws):
            return
        # 確率
        prob = ai_response_probability()
        if prob < 1.0 and random.random() > prob:
            return
        self._generate_and_emit(text=text, username=username, raw=raw)

    def _generate_and_emit(self, *, text: str, username: str, raw: Dict[str, Any]):
        try:
            # AI応答
            reply = ""
            if hasattr(self.ai, "reply"):
                reply = self.ai.reply(text) or ""
            elif hasattr(self.ai, "generate"):
                reply = self.ai.generate(text) or ""
            elif hasattr(self.ai, "ask"):
                reply = self.ai.ask(text) or ""
            else:
                reply = ""

            reply = str(reply).strip()
            if not reply:
                return

            # ✅ v17.5: AI_RESPONSE 発行を再有効化
            # ChatタブにAI応答を表示するため、AI_RESPONSEを発行
            # 注: AIIntegrationManagerとの二重応答を避けるため、
            #     どちらか一方のみが動作するように設計する必要があります
            self.bus.publish(Events.AI_RESPONSE, {
                "text": reply,
                "raw": {"prompt": text, "username": username}
            })

            # 音声へ
            self.bus.publish(Events.VOICE_REQUEST, {
                "text": reply,
                "username": "AI",
                "priority": 50,
            })

        except Exception as e:
            logger.error(f"❌ AI応答生成エラー: {e}")
            self.bus.publish(Events.AI_ERROR, {"message": str(e), "detail": {"source": "enhanced_handler"}})

def create_enhanced_message_handler(*, message_bus: MessageBus, config_manager: Any, ai_connector: Any):
    """
    外部から呼ぶファクトリ。戻り値は cleanup() を持つインスタンス。
    """
    return _EnhancedHandler(message_bus, config_manager, ai_connector)
