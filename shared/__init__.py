# -*- coding: utf-8 -*-
"""
shared package marker (v17.2)
- 便利 re-export。存在しない場合でも失敗しないよう try/except で包む。
"""

# MessageBus / EventTypes
try:
    from .message_bus import MessageBus, EventTypes  # type: ignore
except Exception:
    class MessageBus:  # 最小ダミー
        def subscribe(self, *a, **k): pass
        def publish(self, *a, **k): pass
    class EventTypes:
        CHAT_MESSAGE = "CHAT_MESSAGE"
        ONECOMME_COMMENT = "ONECOMME_COMMENT"
        CONFIG_UPDATED = "CONFIG_UPDATED"
        CONFIG_CHANGED = "CONFIG_CHANGED"
        STATUS_LOG = "STATUS_LOG"
        ERROR_ALERT = "ERROR_ALERT"
        
# だいたいこのブロックの直後/直前に合わせてOK
try:
    from .voice_manager_singleton import get_voice_manager, VoiceManagerSingleton  # v17.3 re-export
except Exception as _e:
    # VoiceManagerが壊れても他は動くように
    get_voice_manager = None  # type: ignore
    VoiceManagerSingleton = None  # type: ignore


# UnifiedConfigManager / get_config_manager
try:
    from .unified_config_manager import UnifiedConfigManager, get_config_manager  # type: ignore
except Exception:
    # フォールバック簡易版
    class UnifiedConfigManager(dict):
        def get(self, key, default=None):
            try:
                parts = str(key).split(".")
                cur = self
                for p in parts:
                    cur = cur.get(p, {})
                return cur if cur != {} else default
            except Exception:
                return default
        def set(self, key, value):
            parts = str(key).split(".")
            cur = self
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = value
        def save(self): pass
    def get_config_manager(*_, **__):
        # 常に新規を返す（簡易）
        return UnifiedConfigManager()

__all__ = ["MessageBus", "EventTypes", "UnifiedConfigManager", "get_config_manager"]
