# shared/env_loader.py
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

_LOADED = False

def ensure_env_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    # このファイルから見てプロジェクトルートを推定（shared/ の親＝プロジェクト直下）
    project_root = Path(__file__).resolve().parents[1]
    dotenv_path = project_root / ".env"
    # override=False で既存の環境変数を壊さない
    load_dotenv(dotenv_path=dotenv_path, override=False)
    _LOADED = True
