# -*- coding: utf-8 -*-
"""
設定ヘルパ（v17.2）
- shared.config_resolver を薄くラップし、実装差や名称ゆれを吸収
- GEMINI_API_KEY 等の正規キーを優先、旧GYURURU_* は警告ログのみで許容
"""

from __future__ import annotations
from typing import Any, Dict, Tuple, Optional, List

from .logger import get_logger
from . import event_types  # 型参照のため
from .config_resolver import (
    load_ai_config, save_ai_config,
    get_provider_and_model, get_api_key,
    get_bool, get_float, get_trigger_keywords,
    normalize_provider,
)

logger = get_logger("shared.config_helper")

def current_ai() -> Tuple[str, str, str]:
    """
    現在の AI プロバイダ / モデル / APIキー（空文字可）を返す
    """
    pid, model = get_provider_and_model()
    key = get_api_key()
    return pid, model, key

def ai_enabled() -> bool:
    return get_bool(None, "enabled", False)

def ai_response_probability() -> float:
    return get_float(None, "response_probability", 1.0)

def ai_trigger_keywords() -> List[str]:
    return get_trigger_keywords()

def update_ai_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI設定を読み込み→上書き保存→返却
    """
    cfg = load_ai_config()
    cfg.update(updates or {})
    save_ai_config(cfg)
    logger.info("🛠️ AI設定を保存しました（config_helper）")
    return cfg

__all__ = [
    "current_ai", "ai_enabled", "ai_response_probability", "ai_trigger_keywords",
    "update_ai_config", "normalize_provider",
]
