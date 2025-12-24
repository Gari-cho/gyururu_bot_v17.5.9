# -*- coding: utf-8 -*-
"""
gyururu_utils.shared_logger（v17.2 互換レイヤ）
- v16 の shared_logger を置き換えるシム。
- すべて shared.logger に委譲します。
"""

from __future__ import annotations
import os
import logging
from typing import Union, Optional
from ..logger import get_logger as _core_get_logger

def get_gui_logger(
    name: str,
    level: Union[str, int] = "INFO",
    enable_file_output: bool = False,
    log_file: Optional[str] = None,
    console_output: bool = True,
) -> logging.Logger:
    # __init__.py 側と同等の動作で統一
    if isinstance(level, str):
        os.environ["LOG_LEVEL"] = level.upper()
    elif isinstance(level, int):
        try:
            os.environ["LOG_LEVEL"] = logging.getLevelName(level)
        except Exception:
            pass
    logger = _core_get_logger(name)
    if not console_output:
        for h in list(logger.handlers):
            if isinstance(h, logging.StreamHandler):
                logger.removeHandler(h)
    return logger

def get_logger(name: str, **kwargs) -> logging.Logger:
    """
    v16 互換シグネチャ（kwargs は無視 or 上位で処理）。
    """
    if "level" in kwargs:
        lvl = kwargs["level"]
        if isinstance(lvl, str):
            os.environ["LOG_LEVEL"] = lvl.upper()
        elif isinstance(lvl, int):
            try:
                os.environ["LOG_LEVEL"] = logging.getLevelName(lvl)
            except Exception:
                pass
    return _core_get_logger(name)

def configure_from_env() -> dict:
    return {
        "level": os.getenv("GYURURU_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")),
        "enable_file_output": os.getenv("GYURURU_LOG_FILE", "false").lower() == "true",
        "log_file": os.getenv("GYURURU_LOG_PATH", "logs/gyururu.log"),
        "console_output": os.getenv("GYURURU_LOG_CONSOLE", "true").lower() == "true",
    }

def get_configured_logger(name: str) -> logging.Logger:
    cfg = configure_from_env()
    lvl = cfg.get("level")
    if isinstance(lvl, str):
        os.environ["LOG_LEVEL"] = lvl.upper()
    return _core_get_logger(name)

# レガシー自己テスト
if __name__ == "__main__":
    log = get_gui_logger("gyururu_legacy_test", level="DEBUG")
    log.debug("legacy get_gui_logger OK")
    log.info("legacy shim works via shared.logger")
