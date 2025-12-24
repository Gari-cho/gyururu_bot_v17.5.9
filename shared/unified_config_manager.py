# -*- coding: utf-8 -*-
"""
UnifiedConfigManager (Phase C 統合版)
====================================

■ 目的
- 設定ファイルの乱立をやめ、**configs/unified_config.json** に一本化する。
- APIキー等の秘匿情報は **.env のみ** に保存／参照し、JSONには書かない。
- 旧ファイル群を自動でマイグレーション（取り込み）できるようにする。
- ドット記法 get/set を提供して、タブ側は統一的に設定へアクセスできる。

■ ファイルの役割（相対パス・プロジェクトルート基準）
----------------------------------------------------------------
▶ デフォルト初期値:      ./defaults/responses_default.json（存在すれば読む・上書きはしない）
▶ ユーザー保存ファイル:  ./configs/unified_config.json（本ファイルで読み書きする中心ファイル）
▶ 秘匿情報(APIキー等):   ./.env だけに保存（JSONへは絶対に書かない）

■ 旧ファイルからの自動マイグレーション（存在すれば読み込み・統合）
----------------------------------------------------------------
- ./local_config.json
- ./tab_ai_unified/ai_personality_config.json
- ./tab_ai_unified/configs/ai_config.json
- ./tab_ai_unified/configs/ai_personality_config.json
（読み込めたものは unified_config にマージ。元ファイルは安全のため**そのまま残す**＝削除は Phase C-B で行う）

■ 提供インターフェース（主要）
- cfg = UnifiedConfigManager(project_root: Optional[Path])
- cfg.load() / cfg.save()
- cfg.get("a.b.c", default=None)
- cfg.set("a.b.c", value)
- cfg.delete("a.b.c")
- cfg.has("a.b.c") -> bool
- cfg.update(dict_obj)  # トップレベル辞書のマージ
- cfg.migrate_if_needed(dry_run: bool = True) -> dict  # 旧ファイルの検出・読み込み・統合結果を返す
- cfg.get_env("GEMINI_API_KEY", default=None)  # .env / OS環境の取得
- get_config_manager(singleton=True)  # 既存コード互換のアクセサ

※ APIキー（GEMINI_API_KEY など）は set() しても JSON へは保存しません（.env のみ）。

"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ロギング（ルートロガーの設定を継承）
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# .env ロード（python-dotenv が無くても動くフォールバック）
def _load_env_file(env_path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    except Exception as e:
        logger.warning(f"⚠️ .env 読み込みエラー: {e}")
    return values


@dataclass(frozen=True)
class _Paths:
    project_root: Path
    configs_dir: Path
    defaults_dir: Path
    env_file: Path
    unified_config: Path
    # 旧ファイル（移行対象）
    legacy_local_config: Path
    legacy_ai_personality_tabroot: Path
    legacy_ai_config_tabconfigs: Path
    legacy_ai_personality_tabconfigs: Path


def _detect_project_root() -> Path:
    """tab配下/共有配下からでも、確実にプロジェクトルートを推定。"""
    here = Path(__file__).resolve()
    # shared/ 直下にある前提で1階層上がルート
    prj = here.parent.parent
    return prj


def _build_paths(project_root: Optional[Path]) -> _Paths:
    prj = Path(project_root).resolve() if project_root else _detect_project_root()
    return _Paths(
        project_root=prj,
        configs_dir=prj / "configs",
        defaults_dir=prj / "defaults",
        env_file=prj / ".env",
        unified_config=prj / "configs" / "unified_config.json",
        legacy_local_config=prj / "local_config.json",
        legacy_ai_personality_tabroot=prj / "tab_ai_unified" / "ai_personality_config.json",
        legacy_ai_config_tabconfigs=prj / "tab_ai_unified" / "configs" / "ai_config.json",
        legacy_ai_personality_tabconfigs=prj / "tab_ai_unified" / "configs" / "ai_personality_config.json",
    )


def _ensure_dir(p: Path) -> None:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"❌ ディレクトリ作成失敗: {p} -> {e}")


def _deep_get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    cur = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _deep_set(d: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = d
    for k in parts[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[parts[-1]] = value


def _deep_delete(d: Dict[str, Any], path: str) -> bool:
    parts = path.split(".")
    cur = d
    for k in parts[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            return False
        cur = cur[k]
    return cur.pop(parts[-1], None) is not None


def _merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    """辞書を再帰的にマージ。dstに無いキーは追加、辞書は再帰、その他はdstを優先。"""
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge(dst[k], v)
        else:
            dst.setdefault(k, v)
    return dst


class UnifiedConfigManager:
    """
    統一コンフィグマネージャ（Phase C）

    - .env をロードして env 変数を内部にキャッシュ（JSONへは書かない）
    - unified_config.json の読込/保存を提供
    - 旧ファイルを検出・統合（migrate_if_needed）
    - ドット記法での get/set/delete を提供
    """

    RESERVED_ENV_KEYS = {
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "AI_PRIMARY",
        "AI_FALLBACK",
        "AI_RESPONSE_PROB",
        # 追加の鍵があればここに…
    }

    def __init__(self, project_root: Optional[Path] = None, env_path: Optional[Path] = None) -> None:
        self.paths = _build_paths(project_root)
        _ensure_dir(self.paths.configs_dir)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        # .env のロード
        env_file = Path(env_path) if env_path else self.paths.env_file
        self._env_map = _load_env_file(env_file)
        # OS 環境変数で .env を上書き可能
        for k in list(self._env_map.keys()) + list(self.RESERVED_ENV_KEYS):
            if k in os.environ:
                self._env_map[k] = os.environ[k]
        logger.info("⚙️ UnifiedConfigManager 準備完了")

    # -----------------------
    # .env アクセス
    # -----------------------
    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._env_map.get(key, default)

    # -----------------------
    # 読み書き
    # -----------------------
    def load(self) -> None:
        """unified_config.json の読込 + defaults の適用 + 旧ファイル取り込み（非破壊）"""
        with self._lock:
            data: Dict[str, Any] = {}
            # 既存 unified_config.json
            if self.paths.unified_config.exists():
                try:
                    data = json.loads(self.paths.unified_config.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"⚠️ unified_config.json 読み込みエラー: {e}")
                    data = {}

            # defaults の取り込み（存在すれば・不足分のみ）
            defaults_file = self.paths.defaults_dir / "responses_default.json"
            if defaults_file.exists():
                try:
                    defaults = json.loads(defaults_file.read_text(encoding="utf-8"))
                    # ここでは 'ai_personality.responses' の不足キーを埋める想定
                    if isinstance(defaults, dict):
                        _merge(data, {"ai_personality": {"responses": defaults}})
                except Exception as e:
                    logger.warning(f"⚠️ defaults 読み込みエラー: {e}")

            # 旧ファイルの取り込み（dry_run=False で実行）
            try:
                self.migrate_if_needed(dry_run=False, _data_ref=data)
            except Exception as e:
                logger.warning(f"⚠️ 旧設定のマイグレーション中にエラー: {e}")

            # Phase 3: 旧設定から新設定への自動マイグレーション
            self._migrate_phase3_settings(data)

            self._data = data
            logger.info("📖 unified_config 読み込み完了")

    def save(self) -> None:
        """unified_config.json へ保存（envキーは保存しない）"""
        with self._lock:
            # env 由来のキーを JSON に書かない（安全弁）
            filtered = self._strip_env_keys(self._data)
            try:
                self.paths.unified_config.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("💾 unified_config 保存完了")
            except Exception as e:
                logger.error(f"❌ unified_config 保存失敗: {e}")
                raise

    # -----------------------
    # ドット記法 API
    # -----------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return _deep_get(self._data, key, default)

    def set(self, key: str, value: Any) -> None:
        """
        値を設定。**envキー（APIキー等）は JSON へは書かず、内部保持もしない**。
        """
        # env 管理対象は保存しない（= .env から取得するのが正）
        base_key = key.split(".")[-1].upper()
        if base_key in self.RESERVED_ENV_KEYS or key.endswith("api_key") or key.endswith("apikey"):
            logger.info(f"🔒 '{key}' は .env 管理対象のため JSON へは保存しません（内部無視）")
            return

        with self._lock:
            _deep_set(self._data, key, value)

    def delete(self, key: str) -> bool:
        with self._lock:
            return _deep_delete(self._data, key)

    def has(self, key: str) -> bool:
        return self.get(key, default=object()) is not object()

    def update(self, mapping: Dict[str, Any]) -> None:
        with self._lock:
            if not isinstance(mapping, dict):
                return
            _merge(self._data, mapping)

    # -----------------------
    # マイグレーション
    # -----------------------
    def migrate_if_needed(self, dry_run: bool = True, _data_ref: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        旧ファイルを検出して unified_config に統合する。

        - dry_run=True: 結果辞書を返すだけ（self._data へは反映しない）
        - dry_run=False: self._data へも統合（_data_ref があればそちらへ統合）

        return: {"loaded": {path: dict or None}, "merged_into": "unified_config.json"} のような情報
        """
        report: Dict[str, Any] = {"loaded": {}, "merged_into": str(self.paths.unified_config)}
        targets = [
            self.paths.legacy_local_config,
            self.paths.legacy_ai_personality_tabroot,
            self.paths.legacy_ai_config_tabconfigs,
            self.paths.legacy_ai_personality_tabconfigs,
        ]

        merged_count = 0
        merged_into = _data_ref if _data_ref is not None else (self._data if not dry_run else {})

        for p in targets:
            d = None
            if p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"⚠️ 旧設定の読込エラー: {p} -> {e}")
                    d = None
            report["loaded"][str(p)] = d is not None
            if isinstance(d, dict):
                _merge(merged_into, d)
                merged_count += 1

        report["merged_count"] = merged_count
        # 反映
        if not dry_run and _data_ref is None:
            with self._lock:
                _merge(self._data, merged_into)

        if merged_count > 0:
            logger.info(f"🔁 旧設定を {merged_count} 件統合しました（dry_run={dry_run}）")
        return report

    # -----------------------
    # 内部ユーティリティ
    # -----------------------
    def _strip_env_keys(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """
        env 管理対象キーを JSON から除外（安全のため念押し）
        - 末尾 api_key / apikey なども除外
        - RESERVED_ENV_KEYS に含まれるキー（トップ階層）は除外
        """
        def _walk(obj: Any) -> Any:
            if isinstance(obj, dict):
                new = {}
                for k, v in obj.items():
                    upper = k.upper()
                    # キー名で除外判定
                    if upper in self.RESERVED_ENV_KEYS or upper.endswith("API_KEY") or upper.endswith("APIKEY"):
                        continue
                    new[k] = _walk(v)
                return new
            elif isinstance(obj, list):
                return [_walk(x) for x in obj]
            return obj

        return _walk(d)

    def _migrate_phase3_settings(self, data: Dict[str, Any]) -> None:
        """
        Phase 3: 旧設定から新設定への自動マイグレーション

        旧設定:
          ai.provider_primary: str
          ai.provider_fallback: str
          ai.model: str

        新設定:
          ai.primary_provider: str
          ai.fallback_providers: list[str]
          ai.model_settings.gemini: str
          ai.model_settings.local_echo: str
          ai.model_settings.gpt4all: str

        マイグレーションルール:
        1. 新設定がない場合のみ、旧設定から変換
        2. 旧設定は残す（互換性のため）
        3. デフォルト値を設定
        """
        try:
            ai_config = data.setdefault("ai", {})

            # 1. primary_provider のマイグレーション
            if "primary_provider" not in ai_config:
                # 旧設定から変換
                old_primary = ai_config.get("provider_primary") or ai_config.get("provider") or "gemini"
                ai_config["primary_provider"] = old_primary
                logger.info(f"🔁 Phase 3 マイグレーション: primary_provider = {old_primary}")

            # 2. fallback_providers のマイグレーション
            if "fallback_providers" not in ai_config:
                # 旧設定から変換（リスト形式）
                old_fallback = ai_config.get("provider_fallback") or "local-echo"
                ai_config["fallback_providers"] = [old_fallback]
                logger.info(f"🔁 Phase 3 マイグレーション: fallback_providers = {ai_config['fallback_providers']}")

            # 3. model_settings のマイグレーション
            if "model_settings" not in ai_config:
                old_model = ai_config.get("model") or "gemini-2.5-flash"
                ai_config["model_settings"] = {
                    "gemini": old_model,
                    "local_echo": "default",
                    "gpt4all": "default"
                }
                logger.info(f"🔁 Phase 3 マイグレーション: model_settings = {ai_config['model_settings']}")

            # 4. デフォルト値の設定（念のため）
            ai_config.setdefault("primary_provider", "gemini")
            ai_config.setdefault("fallback_providers", ["local-echo"])
            ai_config.setdefault("model_settings", {
                "gemini": "gemini-2.5-flash",
                "local_echo": "default",
                "gpt4all": "default"
            })

        except Exception as e:
            logger.warning(f"⚠️ Phase 3 設定マイグレーションエラー: {e}")

# =============================================================================
# 既存コード互換アクセサ
# =============================================================================

_singleton_instance: Optional[UnifiedConfigManager] = None

def get_config_manager(singleton: bool = True) -> UnifiedConfigManager:
    """
    既存コード互換のアクセサ。
    - singleton=True: シングルトンを返す
    - singleton=False: 毎回新規生成
    """
    global _singleton_instance
    if singleton:
        if _singleton_instance is None:
            _singleton_instance = UnifiedConfigManager()
            _singleton_instance.load()
        return _singleton_instance
    else:
        inst = UnifiedConfigManager()
        inst.load()
        return inst
