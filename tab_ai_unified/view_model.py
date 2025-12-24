#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧠 view_model.py — AI技術設定 ViewModel（v17.2）
- response_probability を保持・保存
- config_resolver.py があれば最優先で利用、無ければ UnifiedConfigManager にフォールバック
"""

from __future__ import annotations
from typing import Optional

# ロギング
try:
    from shared.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

# UnifiedConfig（任意）
CFG_OK = False
try:
    from shared.unified_config_manager import get_config_manager
    CFG_OK = True
except Exception as e:
    logger.info(f"ℹ️ UnifiedConfig未使用: {e}")

class AITechnicalViewModel:
    def __init__(self, config_manager=None) -> None:
        # config_resolver優先（存在すれば）
        self.use_config_resolver = False
        self.config_resolver = None
        try:
            import importlib
            self.config_resolver = importlib.import_module("config_resolver")
            if hasattr(self.config_resolver, "load_ai_config") and hasattr(self.config_resolver, "save_ai_config"):
                self.use_config_resolver = True
                logger.info("✅ config_resolver 使用")
        except Exception as e:
            logger.info(f"ℹ️ config_resolver なし: {e}")

        # UnifiedConfig
        self.cfg = config_manager or (get_config_manager() if CFG_OK else None)

        # 初期値
        ai_cfg = {}
        if self.use_config_resolver:
            try:
                ai_cfg = self.config_resolver.load_ai_config() or {}
            except Exception as e:
                logger.warning(f"config_resolver読み込み警告: {e}")

        if not ai_cfg and self.cfg:
            try:
                ai_cfg = {
                    "response_probability": float(self.cfg.get("ai.response_probability", 0.8)),
                    "provider": self.cfg.get("ai.provider", "gemini"),
                }
            except Exception as e:
                logger.warning(f"UnifiedConfig読み込み警告: {e}")

        self.response_prob: float = float(ai_cfg.get("response_probability", 0.8))
        self.provider: str = ai_cfg.get("provider", "gemini")

    # 操作系
    def set_response_prob(self, v: float) -> None:
        self.response_prob = max(0.0, min(1.0, float(v)))

    def save(self) -> None:
        """
        優先度:
          1) config_resolver (load_ai_config / save_ai_config)
          2) UnifiedConfigManager（set/save）
        """
        try:
            if self.use_config_resolver:
                cur = self.config_resolver.load_ai_config() or {}
                cur["response_probability"] = self.response_prob
                self.config_resolver.save_ai_config(cur)
                logger.info("💾 config_resolverで保存")
                return

            if self.cfg:
                # get_config_manager系（set→save）
                if hasattr(self.cfg, "set"):
                    self.cfg.set("ai.response_probability", float(self.response_prob))
                if hasattr(self.cfg, "save"):
                    self.cfg.save()
                logger.info("💾 UnifiedConfigで保存")
                return

            raise RuntimeError("保存先がありません")

        except Exception as e:
            logger.error(f"❌ 保存エラー: {e}")
            raise
