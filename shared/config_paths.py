# -*- coding: utf-8 -*-
"""
shared/config_paths.py (v17.3)
- 設定ファイルの標準パスを一元管理
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

# プロジェクトルート推定（shared/ の親を起点に）
THIS = Path(__file__).resolve()
PROJECT_ROOT = THIS.parent.parent

CONFIG_DIR = PROJECT_ROOT / "configs"
DEFAULTS_DIR = CONFIG_DIR / "defaults"
PROFILES_DIR = CONFIG_DIR / "profiles"
USER_CONFIG_DIR = PROJECT_ROOT / "configs_user"

def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)

# 代表的な解決関数
def personality_path(profile: str = "default") -> Path:
    return PROFILES_DIR / profile / "ai_personality_config.json"

def ai_config_default_path() -> Path:
    return DEFAULTS_DIR / "ai_config_default.json"

def ai_user_config_path() -> Path:
    return USER_CONFIG_DIR / "ai_config_user.json"

# 初期化（存在しなくてもOK、フォルダだけは作る）
ensure_dirs(CONFIG_DIR, DEFAULTS_DIR, PROFILES_DIR, USER_CONFIG_DIR)
