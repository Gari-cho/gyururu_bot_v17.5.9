# -*- coding: utf-8 -*-
"""
shared/message_bus.py (v17.3 minimal-stable)
- 単純な Pub/Sub バス。スレッドセーフは簡易。
- get_message_bus() で Singleton を取得して共用。
"""

from __future__ import annotations
import threading
import logging
from typing import Callable, Dict, List, Any, Optional

# ロガー設定
logger = logging.getLogger(__name__)

try:
    from shared.event_types import normalize_event_key
except Exception:
    def normalize_event_key(x):  # type: ignore
        return str(x)

class MessageBus:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subs: Dict[str, List[Callable[..., Any]]] = {}

    # --- subscribe/publish ---
    def subscribe(self, event_key: str, handler: Callable[[Any, Optional[str]], Any]) -> None:
        ek = normalize_event_key(event_key)
        logger.debug(f"🔧 [MessageBus:{id(self)}] subscribe: '{event_key}' → '{ek}' | handler={handler.__name__}")
        with self._lock:
            self._subs.setdefault(ek, []).append(handler)
            handler_count = len(self._subs[ek])
        logger.debug(f"📋 [MessageBus:{id(self)}] '{ek}' のハンドラ数: {handler_count}")

    def publish(self, event_key: str, data: Any = None, *, sender: Optional[str] = None) -> None:
        ek = normalize_event_key(event_key)
        logger.debug(f"📤 [MessageBus:{id(self)}] publish: '{event_key}' → '{ek}' | sender={sender}")
        with self._lock:
            handlers = list(self._subs.get(ek, []))
        logger.debug(f"📋 [MessageBus:{id(self)}] '{ek}' のハンドラ数: {len(handlers)}")
        if len(handlers) == 0:
            # Phase 2-5: 購読者なしは頻繁に発生する可能性があるため DEBUG に
            logger.debug(f"⚠️ [MessageBus:{id(self)}] '{ek}' に購読者がいません！")
            logger.debug(f"🔍 [MessageBus:{id(self)}] 全登録イベント: {list(self._subs.keys())}")
        for h in handlers:
            try:
                logger.debug(f"🎯 [MessageBus:{id(self)}] ハンドラ呼び出し: {h.__name__}")
                # handler(data, sender=?)
                if h.__code__.co_argcount >= 2:
                    h(data, sender=sender)
                else:
                    h(data)  # type: ignore
                logger.debug(f"✅ [MessageBus:{id(self)}] ハンドラ完了: {h.__name__}")
            except Exception:
                # どのハンドラで落ちても Bus 自体は止めない
                import traceback
                logger.error(f"❌ [MessageBus:{id(self)}] ハンドラエラー: {h.__name__}")
                traceback.print_exc()

# --- Singleton ---
_GLOBAL_BUS: Optional[MessageBus] = None
_LOCK = threading.Lock()

def get_message_bus() -> MessageBus:
    global _GLOBAL_BUS
    if _GLOBAL_BUS is None:
        with _LOCK:
            if _GLOBAL_BUS is None:
                _GLOBAL_BUS = MessageBus()
                logger.info(f"🏗️ MessageBusシングルトン生成: ID={id(_GLOBAL_BUS)}")
    logger.debug(f"🔍 get_message_bus() 呼び出し: ID={id(_GLOBAL_BUS)}")
    return _GLOBAL_BUS

# エイリアス
Bus = MessageBus
