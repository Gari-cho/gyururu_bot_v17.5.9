#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================
🧩 Gyururu Bot File Metadata
==========================================================
作成日時: 2025-11-10
対応バージョン: v17.3
ディレクトリ / ファイル名: ./ai_integration_manager.py
ファイルの役割:
  - 「AIの導線」統合マネージャ（OneComme/Chat → AI → Chat/Voice）
  - v17.3 の最小回路: AI_REQUEST/ONECOMME_COMMENT/CHAT_MESSAGE を入力として受け、
    AI_RESPONSE/CHAT_APPEND を出力（必要に応じ VOICE_REQUEST も発行）

主な機能:
  - MessageBus シングルトンへの自動接続（フォールバックバス内蔵）
  - UnifiedConfigManager から AI 設定を自動読込
  - Gemini / Local-Echo の 2 系統コネクタを管理
  - ONECOMME_COMMENT / CHAT_MESSAGE から AI_REQUEST への橋渡し
  - AI_RESPONSE / CHAT_APPEND / VOICE_REQUEST の送出

注意事項:
  - v17.3.1 では「導線が生きている」ことを最優先とし、
    API キーが無い場合でも Local-Echo で必ず応答を返す。
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# .env 読込ヘルパ（単独実行時の保険）
# ---------------------------------------------------------
def _load_env_if_exists():
    """
    v17.3 標準: .env があれば読み込む（エラーは握りつぶす）
    """
    try:
        from pathlib import Path
        env_path = Path(".env")
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path, override=True)
                logger.info(f"🌍 .env 読込完了: {env_path}")
            except Exception:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
                logger.info(f"🌍 .env（簡易）読込完了: {env_path}")
        else:
            logger.warning("⚠️ .env が見つかりません（環境変数のみ使用）")
    except Exception as e:
        logger.warning(f"⚠️ .env 読込失敗: {e}")

_load_env_if_exists()

# ---------------------------------------------------------
# フォールバック用ミニ MessageBus
# ---------------------------------------------------------
class _MiniBus:
    """
    shared.message_bus が見つからないとき用の簡易実装。
    """
    def __init__(self):
        self._subs: Dict[str, list[Callable[[dict, Optional[str]], None]]] = {}

    def _key(self, ev) -> str:
        if isinstance(ev, str):
            return ev
        return str(ev)

    def publish(self, ev, data=None, sender=None):
        k = self._key(ev)
        if k not in self._subs:
            return
        for cb in list(self._subs[k]):
            try:
                cb(data or {}, sender)
            except Exception:
                logger.exception(f"MiniBus handler error: {cb}")

    def is_alive(self) -> bool:
        # v17.3: バス生死の監視で利用
        try:
            _ = bool(self._subs)
        except Exception:
            return False
        return True

    def subscribe(self, ev, cb):
        k = self._key(ev)
        self._subs.setdefault(k, []).append(cb)
        # トークン代わりに (event, cb) を返す
        return (k, cb)

    def unsubscribe(self, token_or_event, cb=None):
        try:
            if isinstance(token_or_event, tuple) and cb is None:
                k, fn = token_or_event
                if k in self._subs and fn in self._subs[k]:
                    self._subs[k].remove(fn)
            else:
                k = self._key(token_or_event)
                if k in self._subs and cb in self._subs[k]:
                    self._subs[k].remove(cb)
        except Exception:
            pass

def _get_bus():
    """
    shared.message_bus があればそれを使用。無ければ _MiniBus を返す。
    """
    try:
        # v17.3 推奨: シングルトン取得関数を利用
        from shared.message_bus import get_message_bus
        return get_message_bus()
    except Exception:
        try:
            # 直下配置フォールバック
            from message_bus import get_message_bus as _get_bus_fallback
            return _get_bus_fallback()
        except Exception:
            logger.warning("⚠️ MessageBus が見つからないため _MiniBus を使用します")
            return _MiniBus()

# ---------------------------------------------------------
# UnifiedConfigManager 互換ヘルパ
# ---------------------------------------------------------
class _DummyConfig(dict):
    """
    ConfigManager が見つからないときの簡易辞書。
    get/set だけ対応すれば十分。
    """
    def get(self, key, default=None):
        return super().get(key, default)

    def set(self, key, value):
        self[key] = value

def _get_config():
    """
    v17.3.1: ConfigManager は UnifiedConfigManager / get_config_manager() に統一。
    - まず unified_config_manager.py から get_config_manager を取得
    - 失敗した場合は UnifiedConfigManager() を直接生成
    - どちらもダメな場合は {} を返す（エラーはログに残す）
    """
    try:
        # プロジェクト直下パターン
        from unified_config_manager import get_config_manager, UnifiedConfigManager  # type: ignore
    except Exception:
        try:
            # shared配下にあるパターン
            from shared.unified_config_manager import get_config_manager, UnifiedConfigManager  # type: ignore
        except Exception as e:
            logger.error(f"❌ UnifiedConfigManager モジュールのインポートに失敗しました: {e}")
            return {}

    # get_config_manager() 優先
    try:
        cfg = get_config_manager()
        if cfg is not None:
            return cfg
    except Exception as e:
        logger.error(f"❌ get_config_manager() 呼び出しに失敗しました: {e}")

    # フォールバック: 直接インスタンス生成
    try:
        return UnifiedConfigManager()
    except Exception as e:
        logger.error(f"❌ UnifiedConfigManager() 生成にも失敗しました: {e}")
        return {}

# ---------------------------------------------------------
# イベント種別（shared.event_types との連携）
# ---------------------------------------------------------
try:
    from shared.event_types import Events as _Events
    Events = _Events
except Exception:
    class _CompatEvents:
        APP_STARTED       = "APP_STARTED"
        AI_REQUEST        = "AI_REQUEST"
        ONECOMME_COMMENT  = "ONECOMME_COMMENT"
        CHAT_MESSAGE      = "CHAT_MESSAGE"
        AI_RESPONSE       = "AI_RESPONSE"
        CHAT_APPEND       = "CHAT_APPEND"
        VOICE_REQUEST     = "VOICE_REQUEST"
        STATUS_UPDATE     = "STATUS_UPDATE"
        AI_ERROR          = "AI_ERROR"
        # v17.3.1 追加イベント（フォールバック用）
        AI_STATUS_REQUEST = "AI_STATUS_REQUEST"
        AI_STATUS_UPDATE  = "AI_STATUS_UPDATE"
        AI_TEST_REQUEST   = "AI_TEST_REQUEST"
        CONFIG_UPDATE     = "CONFIG_UPDATE"
    Events = _CompatEvents()  # type: ignore

def _ev(name: str) -> str:
    return getattr(Events, name, name)

# ---------------------------------------------------------
# エラーメッセージのサニタイズ
# ---------------------------------------------------------
def _sanitize_error_message(error_msg: str) -> str:
    """
    API エラーメッセージから機密情報（API キー、トークンなど）を除去。
    """
    import re
    msg = str(error_msg)

    # API キーのパターン（様々な形式に対応）
    # Example: "API_KEY=AIza..." → "API_KEY=***"
    msg = re.sub(r'(api[_-]?key\s*[=:]\s*)["\']?[\w\-]{20,}["\']?', r'\1***', msg, flags=re.IGNORECASE)

    # Bearer トークン
    msg = re.sub(r'(bearer\s+)[\w\-\.]+', r'\1***', msg, flags=re.IGNORECASE)

    # Authorization ヘッダー
    msg = re.sub(r'(authorization\s*:\s*)[^\s,}]+', r'\1***', msg, flags=re.IGNORECASE)

    # 長い英数字文字列（40文字以上の連続した英数字はキーの可能性）
    msg = re.sub(r'\b[A-Za-z0-9_\-]{40,}\b', '***', msg)

    return msg

# ---------------------------------------------------------
# AI コネクタ（オフライン安全実装）
# ---------------------------------------------------------
@dataclass
class AIConnectorResult:
    text: str
    provider: str
    model: Optional[str] = None
    latency_ms: Optional[int] = None

class BaseConnector:
    name: str = "base"

    def generate_reply(self, prompt: str, user: str = "User") -> AIConnectorResult:
        raise NotImplementedError

class LocalEchoConnector(BaseConnector):
    """
    オフラインでも必ず動作するローカル向け簡易コネクタ。
    """
    name = "local-echo"

    def generate_reply(self, prompt: str, user: str = "User") -> AIConnectorResult:
        t0 = time.time()
        # 簡易ルール：空なら何もしない、短文は相槌、質問っぽいなら短回答
        text = prompt.strip()
        if not text:
            out = "（…）"
        elif text.endswith("？") or text.endswith("?"):
            out = "いい質問だね。ざっくり言うと――" + text.rstrip("？?") + "への答えは、状況次第だよ。"
        elif len(text) <= 12:
            out = f"うんうん、{text}。"
        else:
            out = f"{user}さん、{text}については把握したよ。要点を短く返すね。"
        return AIConnectorResult(text=out, provider=self.name, model=None,
                                 latency_ms=int((time.time() - t0) * 1000))

class GeminiConnector(BaseConnector):
    """
    GEMINI_API_KEY が存在するときだけ有効化。

    v17.5.1: is_mock フラグ追加
    - is_mock=True: モック実装（仮想応答のみ）→ フォールバック扱い
    - is_mock=False: 実際のAPI実装 → 統合済みAI扱い

    v17.5.2: 本物の Gemini API 実装
    - google.generativeai ライブラリを使用
    - ライブラリがない場合は自動的にモックにフォールバック
    """
    name = "gemini"

    def __init__(self, api_key: Optional[str], model: Optional[str] = None, is_mock: bool = False, timeout_seconds: int = 15):
        self.api_key = (api_key or "").strip()
        self.model = (model or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()
        self.enabled = bool(self.api_key)
        self.timeout_seconds = timeout_seconds

        # ✅ v17.5.2: google.generativeai ライブラリの利用可能性をチェック
        self._genai_available = False
        self._genai_model = None

        if self.enabled and not is_mock:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._genai_model = genai.GenerativeModel(self.model)
                self._genai_available = True
                logger.info(f"✅ Gemini API 初期化成功: model={self.model}")
            except ImportError:
                logger.warning("⚠️ google-generativeai ライブラリが見つかりません。モック実装で動作します。")
                logger.warning("   インストール: pip install google-generativeai")
                self._genai_available = False
            except Exception as e:
                logger.warning(f"⚠️ Gemini API 初期化失敗: {e}。モック実装で動作します。")
                self._genai_available = False

        # is_mock フラグを実態に合わせて更新
        self.is_mock = is_mock or not self._genai_available

    def generate_reply(self, prompt: str, user: str = "User") -> AIConnectorResult:
        t0 = time.time()

        if not self.enabled:
            # 無効時はローカル・エコー風の保険
            out = f"[Gemini無効] {user}さん、{prompt}（※APIキー未設定のためローカル応答）"
            return AIConnectorResult(text=out, provider=self.name, model=self.model,
                                     latency_ms=int((time.time() - t0) * 1000))

        # ✅ v17.5.2: 本物の Gemini API 呼び出し
        if self._genai_available and self._genai_model:
            try:
                # Gemini API を使った実際の応答生成（タイムアウト設定あり）
                response = self._genai_model.generate_content(
                    prompt,
                    request_options={"timeout": self.timeout_seconds}
                )
                result_text = response.text
                latency = int((time.time() - t0) * 1000)

                logger.info(f"✅ Gemini API 応答成功: latency={latency}ms, text={result_text[:50]}...")

                return AIConnectorResult(
                    text=result_text,
                    provider=self.name,
                    model=self.model,
                    latency_ms=latency
                )
            except Exception as e:
                # API呼び出しエラー時は例外を投げてフォールバックに任せる
                # エラーメッセージをサニタイズして機密情報を除去
                safe_msg = _sanitize_error_message(str(e))
                logger.error(f"❌ Gemini API 呼び出しエラー: {safe_msg}")
                raise RuntimeError(f"Gemini API error: {safe_msg}")

        # モック実装（ライブラリがない場合や明示的にis_mock=Trueの場合）
        out = f"[Gemini仮想応答] {user}さん、「{prompt}」についてざっくり補足するね。"
        return AIConnectorResult(text=out, provider=self.name, model=self.model,
                                 latency_ms=int((time.time() - t0) * 1000))


# =========================================================
# AIIntegrationManager v17.3.1 統合版
# =========================================================
class AIIntegrationManager:
    """
    OneComme/Chat → AI → Chat/Voice への導線を担当する統合マネージャ。
    - 入口: AI_REQUEST / ONECOMME_COMMENT / CHAT_MESSAGE
    - 出口: AI_RESPONSE / CHAT_APPEND / （任意）VOICE_REQUEST
    - 追加: AI_STATUS_REQUEST / AI_TEST_REQUEST に応答して AI_STATUS_UPDATE を返す
    """

    def __init__(self, message_bus=None, config_manager=None):
        import os

        logger.debug(f"🐛 [DEBUG] AIIntegrationManager.__init__ 開始: インスタンスID={id(self)}")

        # --- 基本依存の取得 ---
        self.bus = message_bus or _get_bus()
        self.config = config_manager or _get_config()
        self._subs: list = []
        self._started = False

        # --- 環境/設定の読込 ---
        # ・primary/fallback は設定 > 環境変数の順で採用
        primary = (self.config.get('ai.primary', None) or os.getenv('AI_PRIMARY', 'gemini')).strip().lower()
        fallback = (self.config.get('ai.fallback', None) or os.getenv('AI_FALLBACK', 'local-echo')).strip().lower()
        self.provider_primary = primary
        self.provider_fallback = fallback

        # モデル・APIキー・タイムアウト設定
        gemini_api = (os.getenv('GEMINI_API_KEY', '') or '').strip()
        model = (os.getenv('GEMINI_MODEL', '') or '').strip() or self.config.get('ai.model', 'gemini-2.5-flash')
        self.model_name = model

        # Gemini API タイムアウト設定（デフォルト15秒）
        timeout_seconds = 15
        if self.config:
            try:
                timeout_seconds = int(self.config.get("ai.gemini.timeout", 15))
            except Exception:
                timeout_seconds = 15

        # --- コネクタの用意（サポート外はローカルEchoに吸収） ---
        supported = {'gemini', 'local-echo', 'echo'}
        if self.provider_primary not in supported:
            self.provider_primary = 'gemini'
        if self.provider_fallback not in supported:
            self.provider_fallback = 'local-echo'

        # Primary
        self.connector_primary = None
        if self.provider_primary == 'gemini':
            self.connector_primary = GeminiConnector(gemini_api, model=model, timeout_seconds=timeout_seconds)

            # google-generativeai 未インストール時の UI 通知
            if self.connector_primary.is_mock and gemini_api:
                try:
                    import google.generativeai
                except ImportError:
                    error_msg = "⚠️ google-generativeai ライブラリが見つかりません。\nインストール: pip install google-generativeai"
                    logger.warning(error_msg)
                    if self.bus:
                        try:
                            self.bus.publish(_ev('AI_ERROR'), {
                                'message': 'google-generativeai ライブラリが未インストールです',
                                'detail': 'pip install google-generativeai でインストールしてください',
                                'severity': 'warning'
                            }, sender='ai_integration')
                        except Exception:
                            pass

        # Fallback（必ず存在させる）
        self.connector_fallback = LocalEchoConnector()

        # 有効なプロバイダを決定（primary優先）
        # ✅ v17.5.2: is_mock=True の場合はフォールバック扱い
        self.active_provider = None
        if (
            self.connector_primary
            and getattr(self.connector_primary, 'enabled', False)
            and not getattr(self.connector_primary, 'is_mock', False)
        ):
            self.active_provider = self.provider_primary
        else:
            self.active_provider = 'local-echo'

        self.connected = bool(self.active_provider)

        logger.info(
            f"🤖 AIIntegrationManager 準備完了: primary={self.provider_primary}, "
            f"fallback={self.provider_fallback}, active={self.active_provider}, model={self.model_name}"
        )

    # ---------- ライフサイクル ----------
    def start(self):
        if self._started:
            return
        self._subscribe_bus()
        self._started = True
        self._status('AIIntegrationManager started')

    def stop(self):
        if not self._started:
            return
        self.cleanup()
        self._started = False
        self._status('AIIntegrationManager stopped')

    def cleanup(self):
        try:
            if hasattr(self.bus, 'unsubscribe'):
                for token in list(self._subs):
                    try:
                        # token が (ev, cb) 形式 or トークン形式どちらにも対応
                        if isinstance(token, tuple) and len(token) == 2:
                            ev, cb = token
                            self.bus.unsubscribe(ev, cb)
                        else:
                            self.bus.unsubscribe(token)
                    except Exception:
                        pass
            self._subs.clear()
        except Exception as e:
            logger.debug(f'cleanup error: {e}')

    # ---------- Bus購読 ----------
    def _subscribe_bus(self):
        logger.debug(f"🐛 [DEBUG] AIIntegrationManager._subscribe_bus 開始: インスタンスID={id(self)}")

        def sub(ev_name: str, fn):
            try:
                ev = _ev(ev_name)
                token = self.bus.subscribe(ev, fn)
                self._subs.append(token if token is not None else (ev, fn))
                logger.info(f'📡 subscribe: {ev_name}')
            except Exception as e:
                logger.warning(f'⚠️ subscribe 失敗: {ev_name}: {e}')

        # v17.3.1 最小回路の入口をすべて購読
        # ❌ v17.3.1: AI_REQUEST 以外の直接購読を削除（tab_chat で AI_REQUEST に一本化）
        sub('AI_REQUEST',        self._on_ai_request)
        # sub('ONECOMME_COMMENT',  self._on_incoming_text)  # ← tab_chat が AI_REQUEST に変換
        # sub('CHAT_MESSAGE',      self._on_incoming_text)  # ← tab_chat が AI_REQUEST に変換
        # メイン起動合図（統合度を上げるフック）
        sub('APP_STARTED',       self._on_app_started)
        # 接続状態照会/テスト
        sub('AI_STATUS_REQUEST', self._on_ai_status_request)
        sub('AI_TEST_REQUEST',   self._on_ai_test_request)

    # ---------- ステータス送信ヘルパ ----------
    def _send_status_update(self, reason: str = 'manual'):
        """
        AI_STATUS_UPDATE を Bus に発行する。

        v17.5: 実際の動作モード（フォールバック判定）を追加
        - is_fallback: 実際にフォールバックモードで動作しているか
        - provider/model: フォールバックの場合は 'fallback' / 'local-echo' に変更

        v17.5.1: is_mock チェック追加
        - primary connector が is_mock=True の場合、is_fallback=True として扱う
        - これにより仮想応答のみの間は「フォールバック」として正しく表示される
        """
        try:
            import os
            provider = self.active_provider or self.provider_primary or 'gemini'
            model = self.model_name or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
            primary = self.connector_primary
            fallback = self.connector_fallback

            has_api_key = bool(getattr(primary, 'enabled', False) or os.getenv('GEMINI_API_KEY', '').strip())
            connector_available = bool(
                (primary and getattr(primary, 'enabled', False))
                or fallback
            )

            # ✅ v17.5: 実際にフォールバックモードかどうかを判定
            is_fallback = (self.active_provider in ['local-echo', 'echo', 'fallback', None])

            # ✅ v17.5.1: primary connector が is_mock=True の場合もフォールバック扱い
            if primary and getattr(primary, 'is_mock', False):
                is_fallback = True

            # ✅ v17.5: フォールバックの場合は provider/model も実態に合わせる
            if is_fallback:
                provider = 'fallback'
                model = 'local-echo'

            payload = {
                'provider': provider,
                'model': model,
                'has_api_key': has_api_key,
                'connector_available': connector_available,
                'is_fallback': is_fallback,  # ✅ v17.5: 実態フラグ追加
                'reason': reason,
            }

            ev = _ev('AI_STATUS_UPDATE')
            self.bus.publish(ev, payload, sender='AIIntegrationManager')
            logger.info(f'📡 AI_STATUS_UPDATE 送信: provider={provider}, model={model}, has_api_key={has_api_key}, '
                       f'connector_available={connector_available}, is_fallback={is_fallback}, reason={reason}')

        except Exception as e:
            logger.warning(f'⚠️ AI_STATUS_UPDATE 送信失敗: {e}')

    # ---------- 受信ハンドラ ----------
    def _on_app_started(self, data: Optional[dict], sender=None):
        """
        APP_STARTED イベントを受信したら、初回の AI_STATUS_UPDATE を自動発行する。
        これにより、各タブが個別に AI_STATUS_REQUEST を発行する必要がなくなる。
        """
        self._status('APP_STARTED 受信（AIIntegration 有効）')
        # Phase 1.3.1: 初回 AI状態通知を自動発行
        logger.info("📡 APP_STARTED 受信 → AI_STATUS_UPDATE を自動発行します")
        self._send_status_update(reason='app_started')

    def _on_ai_status_request(self, data: Optional[dict], sender=None):
        logger.info(f'[AI_STATUS_REQUEST] sender={sender}, data={data}')
        self._send_status_update(reason='status_request')

    def _on_ai_test_request(self, data: Optional[dict], sender=None):
        """
        AI接続テスト要求（AI_TEST_REQUEST）を処理する。
        実際の接続再初期化は行わず、現在の状態を AI_STATUS_UPDATE として返す簡易仕様。
        """
        logger.info(f'[AI_TEST_REQUEST] sender={sender}, data={data}')
        # 必要ならここで簡単な自己診断を追加してもよいが、
        # まずは現在状態をそのまま通知する。
        self._send_status_update(reason='test')

    def _on_ai_request(self, data: Optional[dict], sender: Optional[str] = None):
        """
        AI_REQUEST を受信して AI_RESPONSE / VOICE_REQUEST を発行する中核ロジック。

        v17.5.2: キャラ設定を使ってプロンプトを構築
        v17.5.3: UIフリーズ防止のため、AI生成処理を別スレッドで実行

        期待される data 形式例:
            {
                "text": "...",
                "username": "ユーザー名",
                "user": "ユーザー名（旧仕様）",
                "provider": "gemini" など,
                "model": "gemini-2.5-flash" など,
                "system_prompt": "...",  # v17.5.2: キャラ設定
                "personality": "...",
                "ai_name": "...",
                "age": "...",
                "speaking_style": "...",
                "background": "..."
            }
        """
        try:
            payload = data or {}

            # テキストとユーザー名を抽出
            text = payload.get("text") or ""
            user = payload.get("username") or payload.get("user") or "ユーザー"

            if not text:
                logger.info("🛈 AI_REQUEST: text が空のためスキップします")
                return

            # ✅ v17.5.2: キャラ設定を取得
            system_prompt = payload.get("system_prompt", "")
            personality = payload.get("personality", "")
            ai_name = payload.get("ai_name", "ぎゅるる")
            age = payload.get("age", "")
            speaking_style = payload.get("speaking_style", "")
            background = payload.get("background", "")
            response_length_limit = payload.get("response_length_limit", 200)

            # プロバイダとモデルを決定
            provider = (
                payload.get("provider")
                or self.active_provider
                or self.provider_primary
                or "gemini"
            )
            model = payload.get("model") or self.model_name or "gemini-2.5-flash"

            # ✅ 宛先ユーザー名（元コメントの送り主）を抽出
            original_username = (
                payload.get("original_username")
                or payload.get("username")
                or payload.get("user")
                or user
            )

            # デバッグログ
            logger.info(
                "🐛 [DEBUG] AI_REQUEST 受信: sender=%s, provider=%s, model=%s, "
                "user=%s, text=%s..., ai_name=%s, response_limit=%s文字",
                sender,
                provider,
                model,
                user,
                text[:30],
                ai_name,
                response_length_limit,
            )

            # ✅ v17.5.3: UIフリーズ防止のため、AI生成処理を別スレッドで実行
            import threading
            worker = threading.Thread(
                target=self._process_ai_request_async,
                args=(text, user, system_prompt, personality, ai_name, age, speaking_style, background, response_length_limit, provider, model, original_username),
                daemon=True,
            )
            worker.start()
            logger.info("🧵 AI生成処理を別スレッドで開始しました")

        except Exception as e:
            logger.exception(f"AI_REQUEST processing error: {e}")
            self._error(f"AI_REQUEST error: {e}")

    def _process_ai_request_async(
        self,
        text: str,
        user: str,
        system_prompt: str,
        personality: str,
        ai_name: str,
        age: str,
        speaking_style: str,
        background: str,
        response_length_limit: int,
        provider: str,
        model: str,
        original_username: str = "",
    ):
        """
        AI生成処理を非同期で実行する内部メソッド（別スレッドで実行される）。

        v17.5.3: UIフリーズ防止のため、_on_ai_request() から分離
        """
        try:
            # ✅ v17.5.2: キャラ設定を使ってプロンプトを構築
            full_prompt = self._build_prompt_with_character(
                text=text,
                user=user,
                system_prompt=system_prompt,
                personality=personality,
                ai_name=ai_name,
                age=age,
                speaking_style=speaking_style,
                background=background,
                response_length_limit=response_length_limit
            )

            logger.debug(f"🧩 構築したプロンプト: {full_prompt[:200]}...")

            # 実際のAI生成（フォールバック付きロジックに一元化）
            result = self._generate_with_fallback(
                full_prompt,
                user=user,
                provider=provider,
                model=model,
            )

            # AI_RESPONSE / VOICE_REQUEST の publish はここに一元化
            # ✅ original_username は関数パラメータとして既に受け取っている
            # ✅ v17.6+: ai_name も渡して、チャット表示でキャラ名を正しく表示
            self._emit_ai_result(
                result,
                user=user,
                original_username=original_username,
                ai_name=ai_name,
            )

        except Exception as e:
            logger.exception(f"非同期AI処理エラー: {e}")
            self._error(f"AI処理エラー: {e}")


    # ❌ v17.3.1: ONECOMME_COMMENT / CHAT_MESSAGE の直接購読を廃止したため、このメソッドは未使用
    # def _on_incoming_text(self, data: Optional[dict], sender=None):
    #     """
    #     ONECOMME_COMMENT / CHAT_MESSAGE からの入力を統一処理。
    #     条件次第で AI_REQUEST にブリッジする余地を残す。
    #     """
    #     try:
    #         if not isinstance(data, dict):
    #             return
    #         text = (data.get('text') or '').strip()
    #         if not text:
    #             return
    #         # 将来的に「ぎゅるる呼びかけ」検出などをここに実装する想定。
    #     except Exception:
    #         return

    # ---------- 内部生成ロジック ----------
    def _build_prompt_with_character(
        self,
        text: str,
        user: str,
        system_prompt: str = "",
        personality: str = "",
        ai_name: str = "ぎゅるる",
        age: str = "",
        speaking_style: str = "",
        background: str = "",
        response_length_limit: int = 200
    ) -> str:
        """
        キャラ設定を反映したプロンプトを構築する。

        v17.5.2: AIキャラ設定タブの性格をAI応答に反映させる
        v17 Refactor: 応答文字数制限を完全実装

        データの流れ:
        1. tab_chat/app.py の _do_ai_request() が UnifiedConfigManager から設定を取得
           - ai_personality.basic_info.name / personality / age / speaking_style / background
           - ai.response_length_limit
        2. AI_REQUEST イベントの payload に全設定を埋め込む
        3. このメソッドで受け取った設定をプロンプトに構築
        4. Gemini / フォールバックAI に送信

        Args:
            text: ユーザーの入力テキスト
            user: ユーザー名
            system_prompt: システムプロンプト（キャラ設定の基本）
            personality: 性格設定
            ai_name: AIの名前
            age: 年齢
            speaking_style: 口調
            background: 背景・設定
            response_length_limit: 応答文字数制限（目安、AIモデルに指示として送る）

        Returns:
            構築されたプロンプト（Geminiに送信する最終形）
        """
        parts = []

        # システムプロンプト（最優先・既に完全なプロンプトの場合がある）
        # v17.5.3: system_promptが存在する場合は、それをベースとして最小限の追加のみ
        if system_prompt:
            parts.append(system_prompt)
            # system_promptに既に設定が含まれているため、重複を避ける
            # ユーザー入力のみを追加
            parts.append(f"\n{user}さんからのメッセージ: {text}")
            return "\n".join(parts)

        # ❌ 以下は system_prompt がない場合のフォールバック（通常は使用されない）
        # v17.5.3: system_prompt が常に tab_ai_unified から供給されるため、
        # この部分はほぼ実行されません

        # 基本情報（最小限）
        if ai_name:
            parts.append(f"あなたは{ai_name}です。")

        # 性格と口調（簡潔に）
        character_info = []
        if personality:
            character_info.append(f"性格: {personality}")
        if speaking_style:
            character_info.append(f"口調: {speaking_style}")
        if character_info:
            parts.append("、".join(character_info))

        # ユーザーの入力
        parts.append(f"\n{user}さんからのメッセージ: {text}")

        # 指示（簡潔に）
        parts.append(f"\n上記の設定で、自然に応答してください。")

        # ✅ v17.5.2: 応答文字数制限の指示
        if response_length_limit and response_length_limit > 0:
            parts.append(f"応答は{response_length_limit}文字程度で簡潔にまとめてください。")

        return "\n".join(parts)

    def _generate_with_fallback(self, prompt: str, user: str, provider: str, model: str) -> AIConnectorResult:
        """
        Phase 3: フォールバック順序に基づいてAI応答を生成する

        UnifiedConfigManager から primary_provider と fallback_providers を読み込み、
        順番に試行する。全て失敗したら固定メッセージを返す。

        試行順序:
        1. primary_provider (設定から取得)
        2. fallback_providers (設定のリストから順番に)
        3. 最後の手段: local-echo（固定メッセージ）

        Args:
            prompt: AI に送信するプロンプト
            user: ユーザー名
            provider: リクエストで指定されたプロバイダ（優先）
            model: リクエストで指定されたモデル

        Returns:
            AIConnectorResult: AI応答結果
        """
        # Phase 3: UnifiedConfigManager から設定を取得
        primary = None
        fallbacks = []

        if self.config and hasattr(self.config, 'get'):
            # 新設定を優先（Phase 3）
            primary = self.config.get('ai.primary_provider', None)
            fallbacks = self.config.get('ai.fallback_providers', None)

            # 旧設定へのフォールバック（互換性）
            if not primary:
                primary = self.config.get('ai.provider_primary', None) or self.config.get('ai.provider', None)
            if not fallbacks:
                old_fallback = self.config.get('ai.provider_fallback', None)
                fallbacks = [old_fallback] if old_fallback else []

        # デフォルト値
        if not primary:
            primary = self.provider_primary or 'gemini'
        if not fallbacks or not isinstance(fallbacks, list):
            fallbacks = ['local-echo']

        # 試行順序を構築
        # 1) リクエストで指定されたプロバイダがあれば最優先
        # 2) primary_provider
        # 3) fallback_providers（リストの順番通り）
        providers_to_try = []
        if provider and provider not in providers_to_try:
            providers_to_try.append(provider)
        if primary and primary not in providers_to_try:
            providers_to_try.append(primary)
        for fb in fallbacks:
            if fb and fb not in providers_to_try:
                providers_to_try.append(fb)

        # 安全策: local-echo が含まれていない場合は最後に追加
        if 'local-echo' not in providers_to_try:
            providers_to_try.append('local-echo')

        logger.info(f"🔄 Phase 3 フォールバック順序: {providers_to_try}")

        # 各プロバイダを順番に試行
        last_err = None
        for idx, p in enumerate(providers_to_try):
            try:
                logger.info(f"🔄 [{idx+1}/{len(providers_to_try)}] プロバイダ '{p}' を試行中...")

                # プロバイダごとの処理
                if p == 'gemini':
                    # Geminiコネクタのチェック
                    if not self.connector_primary:
                        raise RuntimeError('Gemini connector not initialized')
                    if not getattr(self.connector_primary, 'enabled', False):
                        raise RuntimeError('Gemini disabled (API key missing)')

                    # APIキーの確認
                    import os
                    api_key = os.getenv('GEMINI_API_KEY', '').strip()
                    if not api_key:
                        raise RuntimeError('GEMINI_API_KEY not set')

                    # Gemini API 呼び出し
                    result = self.connector_primary.generate_reply(prompt, user=user)
                    logger.info(f"✅ プロバイダ '{p}' で応答成功")
                    return result

                elif p in ('local-echo', 'echo', 'fallback'):
                    # ローカルエコー（必ず成功する）
                    if not self.connector_fallback:
                        raise RuntimeError('Local-echo connector not initialized')
                    result = self.connector_fallback.generate_reply(prompt, user=user)
                    logger.info(f"✅ プロバイダ '{p}' で応答成功（フォールバック）")
                    return result

                elif p == 'gpt4all':
                    # GPT4All（将来実装）
                    raise RuntimeError('GPT4All not implemented yet')

                else:
                    # 未知のプロバイダ
                    raise RuntimeError(f'Unknown provider: {p}')

            except Exception as e:
                last_err = e
                logger.warning(f"⚠️ プロバイダ '{p}' で失敗: {e}")
                continue

        # 全て失敗した場合の最終フォールバック（固定メッセージ）
        logger.error(f'❌ 全てのプロバイダで失敗しました。最終フォールバックを使用します。最後のエラー: {last_err}')

        # 緊急用の固定メッセージを返す
        emergency_text = f"申し訳ありません、現在AIサービスに接続できません。しばらくしてから再度お試しください。（エラー: {last_err}）"
        return AIConnectorResult(
            text=emergency_text,
            provider='emergency-fallback',
            model='none',
            latency_ms=0
        )

    @staticmethod
    def _extract_speakable_part(text: str) -> str:
        """
        AI応答から読み上げ用テキストを抽出する。

        プロフィール全体ではなく、実際に会話で発言している部分だけを抽出する。

        ルール:
        1. "---" があれば、最後の "---" 以降を読み上げ対象とする
        2. それもなければ、空行で区切って最後のブロックを使う
        3. 最低限、"## プロフィール" などの見出しは除外する

        Args:
            text: AI応答の全文

        Returns:
            読み上げに適したテキスト
        """
        if not text or not text.strip():
            return ""

        # 1) "---" があれば、最後の区切り以降を使う
        if "---" in text:
            parts = text.split("---")
            candidate = parts[-1].strip()
            if candidate:
                logger.debug(f"🔧 [speakable] '---'区切りで抽出: {candidate[:50]}...")
                return candidate

        # 2) 空行で区切って最後のブロックを使う
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        if blocks:
            # 見出し（## で始まる行）を含むブロックはスキップ
            for block in reversed(blocks):
                if not block.startswith("##") and not block.startswith("#"):
                    logger.debug(f"🔧 [speakable] 空行区切りで抽出: {block[:50]}...")
                    return block

        # 3) フォールバック：そのまま（ただしログに警告）
        logger.warning(f"⚠️ [speakable] 抽出失敗、全文を使用: {text[:50]}...")
        return text.strip()

    def _emit_ai_result(
        self,
        result: AIConnectorResult,
        user: str,
        original_username: Optional[str] = None,
        ai_name: str = "ぎゅるる",
    ):
        """
        AI生成結果を AI_RESPONSE と VOICE_REQUEST として発行する。

        v17.5.4: 読み上げ用テキスト抽出機能追加
        - full_text: プロフィール＋会話文全体（AI_RESPONSE用）
        - speakable_text: 読み上げに適した部分のみ（VOICE_REQUEST用）
        v17.6+: ai_name パラメータ追加（キャラ別表示対応）
        """
        full_text = result.text
        speakable_text = self._extract_speakable_part(full_text)

        # 宛先ユーザー名（None の場合は user を採用）
        if not original_username:
            original_username = user

        logger.info(f"🔧 [DEBUG] _emit_ai_result() 開始")
        logger.info(f"🔧 [DEBUG]   full_text: {full_text[:80]}...")
        logger.info(f"🔧 [DEBUG]   speakable_text: {speakable_text[:80]}...")
        logger.info(f"🔧 [DEBUG]   user={user}, provider={result.provider}")
        logger.info(f"🔧 [DEBUG]   original_username={original_username}")
        logger.info(f"🔧 [DEBUG]   ai_name={ai_name}")

        # AI_RESPONSE には全文を渡す（チャット表示用）
        payload = {
            "text": full_text,
            "user": user,
            "original_username": original_username,  # ✅ ここで載せる
            "ai_name": ai_name,  # ✅ v17.6+: 実際に応答したキャラ名
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "ts": time.time(),
        }
        logger.info(f"📢 AI_RESPONSE発行準備完了: text={full_text[:50]}..., user={user}")
        self._pub('AI_RESPONSE', payload)
        logger.info(f"✅ AI_RESPONSE発行完了")

        # ✅ v17.3.1: VOICE_REQUEST は AIIntegrationManager が唯一の発行元（ルールブック準拠）
        # v17.5.4: 読み上げ用テキストのみを使用
        # v17.6.0: ロール別キャラ選択対応 - AI応答には role='ai' を追加
        # ✅ v17.6.1: voice.read.ai 設定チェック追加
        try:
            # ✅ v17.6.1追加: voice.read.ai 設定をチェック
            voice_read_ai_enabled = True  # デフォルト: 有効
            if self.config and hasattr(self.config, 'get'):
                voice_read_ai_enabled = bool(self.config.get('voice.read.ai', True))

            if voice_read_ai_enabled:  # ✅ v17.6.1追加: 条件判定
                voice_payload = {
                    'text': speakable_text,  # ← 読み上げ用テキストのみ
                    'username': user,
                    'source': 'ai_response',
                    'priority': 50,
                    'role': 'ai',  # ✅ v17.6.0: AIキャラのロールを指定
                }
                logger.info(f"🎤 VOICE_REQUEST発行準備: text={speakable_text[:80]}..., username={user}, role=ai")
                logger.info(f"🔧 [DEBUG] AIIntegrationManager: MessageBusインスタンス ID={id(self.bus)}")
                self._pub('VOICE_REQUEST', voice_payload)
                logger.info(f'✅ VOICE_REQUEST発行完了（AIIntegrationManager）')
            else:  # ✅ v17.6.1追加
                logger.info(f'ℹ️ voice.read.ai が無効のため VOICE_REQUEST をスキップします')
        except Exception as e:
            logger.error(f'❌ VOICE_REQUEST 発行エラー: {e}', exc_info=True)

    # ---------- Busユーティリティ ----------
    def _pub(self, ev_name: str, data: Optional[dict] = None):
        try:
            ev = _ev(ev_name)
            logger.debug(f"📤 [DEBUG] publish開始: event={ev_name}, data_keys={list((data or {}).keys())}")
            self.bus.publish(ev, data or {}, sender='ai_integration')
            logger.debug(f"📤 [DEBUG] publish完了: event={ev_name}")
        except Exception as e:
            logger.error(f'❌ publish error: {ev_name}: {e}', exc_info=True)

    def _status(self, msg: str):
        logger.info(msg)
        try:
            self.bus.publish(_ev('STATUS_UPDATE'), {'kind': 'ai', 'message': msg}, sender='ai_integration')
        except Exception:
            pass

    def _error(self, msg: str):
        # エラーメッセージをサニタイズして機密情報を除去
        safe_msg = _sanitize_error_message(msg)
        logger.error(safe_msg)
        try:
            self.bus.publish(_ev('AI_ERROR'), {'message': safe_msg, 'ts': time.time()}, sender='ai_integration')
        except Exception:
            pass


# === Backward-compat wrapper (bus/config キー吸収) ===
try:
    _AIIM_Original = AIIntegrationManager
    class AIIntegrationManager(_AIIM_Original):  # type: ignore
        def __init__(self, *args, **kwargs):
            if 'message_bus' not in kwargs and 'bus' in kwargs:
                kwargs['message_bus'] = kwargs.pop('bus')
            if 'config_manager' not in kwargs and 'config' in kwargs:
                kwargs['config_manager'] = kwargs.pop('config')
            super().__init__(*args, **kwargs)
except Exception:
    pass


# ---------------------------------------------------------
# スタンドアロン実行（簡易テスト）
# ---------------------------------------------------------
if __name__ == "__main__":
    mgr = AIIntegrationManager()
    mgr.start()
    mgr.bus.publish("AI_REQUEST", {"text": "テストです。導線チェック！", "user": "Tester"})
    time.sleep(0.3)
    logger.info("✅ selftest 完了（ログを確認してください）")
