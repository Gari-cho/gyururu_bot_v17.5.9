# -*- coding: utf-8 -*-
"""
gyururu_utils（v17.2 互換レイヤ）
- v16 以前の import を壊さないためのシム。
- すべて shared.logger に委譲します。
- 新規実装では shared.logger を直接 import してください。
"""

from __future__ import annotations
import os
import logging
from typing import Union, Optional
from ..logger import get_logger as _core_get_logger  # 正式実装
# 互換エイリアス
get_logger = _core_get_logger

def get_gui_logger(
    name: str,
    level: Union[str, int] = "INFO",
    enable_file_output: bool = False,
    log_file: Optional[str] = None,
    console_output: bool = True,
) -> logging.Logger:
    """
    v16 の get_gui_logger 互換シグネチャ。
    実体は shared.logger.get_logger に委譲（ファイル出力の強制は行わない）。
    """
    # v17.2 の logger は環境変数 LOG_LEVEL を参照するため、引数 level を尊重したい場合は一時的に上書き
    # ※必要なければ素直に get_logger(name) を使ってください。
    if isinstance(level, str):
        level_name = level.upper()
        os.environ["LOG_LEVEL"] = level_name
    elif isinstance(level, int):
        # 例: logging.DEBUG など
        try:
            os.environ["LOG_LEVEL"] = logging.getLevelName(level)
        except Exception:
            pass

    logger = _core_get_logger(name)

    # コンソール非出力を要求されたケース（あまり使わない想定）
    if not console_output:
        for h in list(logger.handlers):
            if isinstance(h, logging.StreamHandler):
                logger.removeHandler(h)

    # v17.2 標準は回転ファイル出力を備えるため、明示ファイルパス要求は無視（後方互換のため警告しない）
    return logger

def configure_from_env() -> dict:
    """
    v16 互換 API。環境変数から logger 設定を読む体裁だけ整える。
    実際の適用は shared.logger 側が行います。
    """
    return {
        "level": os.getenv("GYURURU_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")),
        "enable_file_output": os.getenv("GYURURU_LOG_FILE", "false").lower() == "true",
        "log_file": os.getenv("GYURURU_LOG_PATH", "logs/gyururu.log"),
        "console_output": os.getenv("GYURURU_LOG_CONSOLE", "true").lower() == "true",
    }

def get_configured_logger(name: str) -> logging.Logger:
    """
    v16 互換 API。環境変数を読みつつ最終的に shared.logger に委譲。
    """
    cfg = configure_from_env()
    # level を LOG_LEVEL に反映（shared.logger は LOG_LEVEL を参照）
    lvl = cfg.get("level")
    if isinstance(lvl, str):
        os.environ["LOG_LEVEL"] = lvl.upper()
    return _core_get_logger(name)
