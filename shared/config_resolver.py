#この行を消す

# ==========================================================
#  shared/config_resolver.py  (v17.3 互換ユーティリティ完全版)
#  - v17.2/17.3 の差異を吸収する provider/model 解決関数
#  - EnhancedMessageHandler 等が参照する load/save も提供
# ==========================================================

from __future__ import annotations
import os
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


# -------------------------------
# 内部ヘルパ
# -------------------------------
def _cm_get(cm, key: str, default: Any = None) -> Any:
    try:
        return cm.get(key) if cm else default
    except Exception as e:
        logger.debug(f"_cm_get('{key}') で例外: {e}")
        return default


def _env_get(*keys: str, default: Optional[str] = None) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v is not None and str(v).strip() != "":
            return v
    return default


# -------------------------------
# 公開API（互換）
# -------------------------------
def get_provider_and_model(
    config_manager=None,
    default_provider: Optional[str] = None,
    default_model: Optional[str] = None,
) -> Tuple[str, str]:
    """
    v17.3向け互換API。
    優先度:
      1) UnifiedConfigManager('ai.primary' / 'ai.provider', 'ai.model')
      2) .env (AI_PRIMARY / GEMINI_PRIMARY / GEMINI_PROVIDER, AI_MODEL / GEMINI_MODEL)
      3) 引数 default_* / 既定値 ('gemini', 'gemini-2.5-flash')
    """
    provider = (
        _cm_get(config_manager, "ai.primary")
        or _cm_get(config_manager, "ai.provider")
    )
    model = _cm_get(config_manager, "ai.model")

    if not provider:
        provider = _env_get("AI_PRIMARY", "GEMINI_PRIMARY", "GEMINI_PROVIDER", default=default_provider)
    if not provider:
        provider = "gemini"

    if not model:
        model = _env_get("AI_MODEL", "GEMINI_MODEL", default=default_model)
    if not model:
        model = "gemini-2.5-flash"

    return provider, model


def load_ai_config(config_manager=None) -> Dict[str, str]:
    """
    EnhancedMessageHandler 等から呼ばれる想定の互換関数。
    """
    try:
        p, m = get_provider_and_model(config_manager)
        return {"provider": p, "model": m}
    except Exception as e:
        logger.debug(f"load_ai_config 例外: {e}")
        return {"provider": "gemini", "model": "gemini-2.5-flash"}


def save_ai_config(config_manager, data: Dict[str, Any]) -> bool:
    """
    UnifiedConfigManager がある場合は 'ai.primary' / 'ai.model' に保存。
    なければ静かに False を返すだけ（互換目的）。
    """
    try:
        if not config_manager:
            return False
        if "provider" in data and hasattr(config_manager, "set"):
            config_manager.set("ai.primary", data["provider"])
        if "model" in data and hasattr(config_manager, "set"):
            config_manager.set("ai.model", data["model"])
        if hasattr(config_manager, "save"):
            config_manager.save()
        return True
    except Exception as e:
        logger.warning(f"save_ai_config 失敗: {e}")
        return False


def get_api_key(config_manager=None, provider: Optional[str] = None) -> str:
    """
    v17.2/17.3 互換の API キー解決。
    優先度:
      1) UnifiedConfigManager（ai.api_key / gemini.api_key / openai.api_key 等）
      2) .env（AI_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY / CLAUDE_API_KEY ...）
    """
    try:
        # provider 未指定なら現在の設定から取得
        if not provider:
            provider, _ = get_provider_and_model(config_manager)

        # まず UnifiedConfigManager 側
        keys = [
            "ai.api_key",
            f"{provider}.api_key" if provider else None,
        ]
        for k in keys:
            if not k:
                continue
            v = _cm_get(config_manager, k)
            if v:
                return str(v)

        # .env フォールバック
        env_candidates = ["AI_API_KEY"]
        if provider:
            env_candidates.append(f"{provider.upper()}_API_KEY")
        # 代表的な別名
        env_candidates += ["GEMINI_API_KEY", "OPENAI_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_API_KEY"]
        v = _env_get(*env_candidates, default="")
        return v or ""
    except Exception:
        return ""


# === v17.3 互換: Config Resolver 最小実装 ===
from typing import Optional, Tuple
import os

try:
    # 既存の UnifiedConfigManager がある前提
    from .unified_config_manager import UnifiedConfigManager
    _CFGOK = True
except Exception:
    _CFGOK = False
    UnifiedConfigManager = None  # type: ignore

def _get_cfg() -> Optional["UnifiedConfigManager"]:
    if not _CFGOK:
        return None
    try:
        return UnifiedConfigManager.get_instance()
    except Exception:
        try:
            # 念のため lazy init
            return UnifiedConfigManager()
        except Exception:
            return None

def get_bool(key: str, default: bool = False) -> bool:
    """環境変数→UnifiedConfigの順。'1','true','yes' を真扱い。"""
    val = os.getenv(key)
    if val is not None:
        return val.strip().lower() in ("1", "true", "yes", "on")
    cfg = _get_cfg()
    if cfg:
        try:
            v = cfg.get(key, default)
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("1", "true", "yes", "on")
        except Exception:
            pass
    return default

def get_api_key(provider: str) -> Optional[str]:
    """
    APIキーを返す。優先度: ENV → UnifiedConfig
      ENV 例: GEMINI_API_KEY / CLAUDE_API_KEY / OPENAI_API_KEY
      CFG 例: ai.keys.gemini / ai.keys.claude / ai.keys.openai
    """
    env_map = {
        "gemini": "GEMINI_API_KEY",
        "claude": "CLAUDE_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    envk = env_map.get(provider.lower())
    if envk:
        ev = os.getenv(envk)
        if ev:
            return ev.strip()

    cfg = _get_cfg()
    if cfg:
        try:
            return cfg.get(f"ai.keys.{provider.lower()}")
        except Exception:
            return None
    return None

def get_provider_and_model() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    主要プロバイダ / フォールバック / モデル名 を返す。
      CFG:
        ai.primary = "gemini" | "claude" | "openai" ...
        ai.fallback = "claude" | "openai" | None
        ai.model.gemini = "gemini-2.5-flash" など
    ENV があれば ENV 優先:
        AI_PRIMARY / AI_FALLBACK / GEMINI_MODEL / OPENAI_MODEL / CLAUDE_MODEL
    """
    cfg = _get_cfg()
    # ENV 優先
    primary = os.getenv("AI_PRIMARY") or (cfg.get("ai.primary") if cfg else None)
    fallback = os.getenv("AI_FALLBACK") or (cfg.get("ai.fallback") if cfg else None)

    model = None
    if primary:
        pk = primary.lower()
        env_model_map = {
            "gemini": "GEMINI_MODEL",
            "openai": "OPENAI_MODEL",
            "claude": "CLAUDE_MODEL",
        }
        env_mk = env_model_map.get(pk)
        if env_mk and os.getenv(env_mk):
            model = os.getenv(env_mk).strip()
        elif cfg:
            model = cfg.get(f"ai.model.{pk}")

    return (primary, fallback, model)

def get_float(config_or_dict, key: str, default: float = 0.0):
    """
    v17.3 互換の簡易ヘルパ：
      - UnifiedConfigManager: .get(key, default) を優先
      - dict: 辞書走査で "a.b.c" 形式キーに対応
      - 取得できた値は float に変換。失敗時は default
    """
    val = default
    try:
        if hasattr(config_or_dict, "get") and callable(getattr(config_or_dict, "get")):
            # UnifiedConfigManager 互換
            val = config_or_dict.get(key, default)
        elif isinstance(config_or_dict, dict):
            cur = config_or_dict
            for part in key.split("."):
                if isinstance(cur, dict):
                    cur = cur.get(part, default)
                else:
                    cur = default
                    break
            val = cur
        return float(val)
    except Exception:
        return float(default)
