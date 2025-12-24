# ==========================================================
# 📢 VoiceManager Singleton (v16.6 完全改修＋v17.3補正版)
# ==========================================================
# 目的:
#   VOICEVOX／棒読みちゃん／OS TTS／Fallback の自動切替・監視・音声再生制御を統一。
#   MessageBus と UnifiedConfigManager に統合対応。
#
# 更新履歴:
#   - 2025-11-10  v17.3対応: __init__構造修正（インデント破損修復）
#   - 2025-11-10  VOICEVOX指数バックオフ＋静音化追加
#   - 2025-11-10  TTSフォールバック安定化
#   - 2025-11-15  v17.3.1: 公開APIブロックの重複削除・clear_queue/stop_all 追加
# ==========================================================

import threading
import queue
import time
import logging

# shared.tts_fallback からのインポートは後で使う（名前衝突回避のため _fallback_speak にリネーム）
try:
    from shared.tts_fallback import speak_text as _fallback_speak
except ImportError:
    def _fallback_speak(text):
        """フォールバック: ログ出力のみ"""
        logging.getLogger(__name__).info(f"[Fallback] {text}")

# MessageBus インポート（VOICE_REQUEST イベント購読用）
try:
    from shared.message_bus import get_message_bus
    from shared.event_types import Events
    _HAS_MESSAGE_BUS = True
except ImportError:
    _HAS_MESSAGE_BUS = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ MessageBus未利用 - イベント購読なしで起動")


logger = logging.getLogger("shared.voice_manager_singleton")

# ==== モジュール内シングルトン参照 ====
_VOICE_MANAGER_SINGLETON = None


# ==========================================================
# 🔧 VoiceManager Singleton クラス
# ==========================================================
class VoiceManagerSingleton:
    """シングルトン音声管理クラス（v16.6完全改修＋v17.3統合対応）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
        v17.3 互換：__new__ は任意の *args, **kwargs を受け取り無視してもよい。
        例: VoiceManagerSingleton(config_manager=...) でも例外にしない。
        """
        global _VOICE_MANAGER_SINGLETON
        if _VOICE_MANAGER_SINGLETON is None:
            _VOICE_MANAGER_SINGLETON = super().__new__(cls)
            # インスタンス実体の最小初期化
            _VOICE_MANAGER_SINGLETON._initialized = False
        return _VOICE_MANAGER_SINGLETON

    # ------------------------------------------------------
    # 🏗️ 初期化
    # ------------------------------------------------------
    def __init__(self, config_manager=None, message_bus=None, *args, **kwargs):
        """
        v17.3 互換：config_manager と message_bus を引数で受け取れるように修正。
        多重初期化を防止しつつ、既存の初期化ロジックを維持。
        """
        if getattr(self, "_initialized", False):
            return

        # ===== MessageBus 参照取得 =====
        # 引数で渡された message_bus を優先、なければ get_message_bus() を試行
        if message_bus is not None:
            self.message_bus = message_bus
            logger.debug(f"🔧 [DEBUG] VoiceManager: 外部から渡されたMessageBusを使用 (ID: {id(message_bus)})")
        else:
            self.message_bus = None
            logger.debug("🔧 [DEBUG] VoiceManager: message_busが未指定 - 後でget_message_bus()から取得します")

        # ===== 設定管理参照取得 =====
        # 引数で渡された config_manager を優先、なければ get_config_manager() を試行
        if config_manager is not None:
            self.config_manager = config_manager
        else:
            self.config_manager = None
            try:
                from shared.unified_config_manager import get_config_manager
                self.config_manager = get_config_manager()
            except ImportError:
                logger.warning("⚠️ UnifiedConfigManager未利用 - デフォルト設定で起動")

        # ===== OS標準TTS初期化 =====
        self._os_tts = self._init_os_tts()

        # ===== 基本状態 =====
        self.voice_queue = queue.Queue()
        self.is_speaking = False
        self.available = True
        self.volume = 1.0
        self.speed = 1.0
        self.current_engine = "os_tts" if self._os_tts else "fallback"

        # ===== VOICEVOX プローブ制御（指数バックオフ＋ログ静音化）=====
        self._vvx_backoff_sec = float(self._get_config("voice.voicevox.backoff_start_sec", 2.0))
        self._vvx_backoff_max = float(self._get_config("voice.voicevox.backoff_max_sec", 10.0))
        self._vvx_next_probe_ts = 0.0
        self._vvx_log_throttle_sec = float(self._get_config("voice.voicevox.log_throttle_sec", 5.0))
        self._vvx_last_log_ts = 0.0

        # ===== 統計 =====
        self.stats = {
            "total_requests": 0,
            "successful_plays": 0,
            "failed_plays": 0,
            "queue_peak": 0,
            "engine_switches": 0,
            "voicevox_fails": 0,
            "bouyomi_fails": 0,
            "os_tts_uses": 0,
            "command_detections": 0,
            "queue_overflows": 0,
            "health_checks": 0,
            "auto_recoveries": 0,
        }

        # ===== エンジン情報 =====
        self.engines = {
            "voicevox": {
                "available": False,
                "url": self._get_config("voice.voicevox.api_url", "http://localhost:50021"),
                "default_speaker": self._get_config("voice.voicevox.default_speaker", 3),
                "last_check": 0,
                "consecutive_failures": 0,
            },
            "bouyomi": {
                "available": False,
                "path": None,
                "host": self._get_config("voice.bouyomi.host", "127.0.0.1"),
                "port": self._get_config("voice.bouyomi.port", 50080),
                "last_check": 0,
                "consecutive_failures": 0,
            },
            "os_tts": {
                "available": bool(self._os_tts),
                "description": "OS標準音声合成",
                "engine": self._os_tts,
            },
            "fallback": {
                "available": True,
                "description": "ログ出力のみ",
            },
        }

        # ===== スレッド・設定 =====
        self.worker_thread = None
        self.running = False
        self.command_prefix = self._get_config("voice.command_prefix", "/b")
        self.command_patterns = self._build_command_patterns()
        self.health_check_interval = self._get_config("voice.voicevox.healthcheck_interval_sec", 5)
        self.auto_failover = self._get_config("voice.voicevox.auto_failover", True)
        self.max_queue_size = self._get_config("voice.queue_size", 10)

        # ===== MessageBus 購読管理 =====
        self._subscriptions = []

        self._initialized = True

        # ===== エンジン検出 & ワーカー起動 =====
        self._detect_engines()
        self._start_worker()

        # ===== MessageBus イベント購読 =====
        self._subscribe_to_events()

        logger.info("✅ VoiceManager Singleton v16.6完全改修版 初期化完了")

    # ------------------------------------------------------
    # ⚙️ 設定取得ヘルパ
    # ------------------------------------------------------
    def _get_config(self, key, default=None):
        if not self.config_manager:
            return default
        try:
            return self.config_manager.get(key, default)
        except Exception:
            return default

    # ------------------------------------------------------
    # 🔊 OS TTS 初期化
    # ------------------------------------------------------
    def _init_os_tts(self):
        """OS標準TTS（SAPI経由）の利用可否を確認"""
        try:
            # shared.tts_fallback の SAPI ベース実装を使用
            from shared.tts_fallback import is_available
            if is_available():
                logger.info("🔊 OS標準TTS初期化成功（SAPI）")
                return True  # SAPI が利用可能
            else:
                logger.warning("⚠️ OS標準TTS初期化失敗: SAPI利用不可")
                return None
        except Exception as e:
            logger.warning(f"⚠️ OS標準TTS初期化失敗: {e}")
            return None

    # ------------------------------------------------------
    # 🧩 コマンドパターン構築
    # ------------------------------------------------------
    def _build_command_patterns(self):
        try:
            prefix = self.command_prefix
            return {
                "speed": f"{prefix}speed",
                "volume": f"{prefix}vol",
                "engine": f"{prefix}engine",
            }
        except Exception:
            return {}

    # ------------------------------------------------------
    # 📡 MessageBus イベント購読
    # ------------------------------------------------------
    def _subscribe_to_events(self):
        """MessageBus の VOICE_REQUEST イベントを購読"""
        if not _HAS_MESSAGE_BUS:
            logger.warning("⚠️ MessageBus未利用 - VOICE_REQUEST購読スキップ")
            return

        try:
            logger.debug("🔧 [DEBUG] VoiceManager: VOICE_REQUEST購読開始...")

            # self.message_bus があればそれを使用、なければ get_message_bus() から取得
            if self.message_bus is not None:
                bus = self.message_bus
                logger.debug(f"🔧 [DEBUG] VoiceManager: 保持しているMessageBusを使用 (ID: {id(bus)})")
            else:
                bus = get_message_bus()  # フォールバック
                self.message_bus = bus  # 後で使えるように保存
                logger.debug(f"🔧 [DEBUG] VoiceManager: get_message_bus()から取得 (ID: {id(bus)})")

            logger.debug(f"🔧 [DEBUG] VoiceManager: イベント名='{Events.VOICE_REQUEST}'")
            logger.debug(f"🔧 [DEBUG] VoiceManager: ハンドラ関数={self._on_voice_request.__name__}")

            token = bus.subscribe(Events.VOICE_REQUEST, self._on_voice_request)
            logger.info(f"📡 VoiceManager: VOICE_REQUEST イベント購読完了 (token: {token})")
        except Exception as e:
            logger.error(f"❌ MessageBus購読エラー: {e}", exc_info=True)

    def _on_voice_request(self, event_data, sender=None):
        """VOICE_REQUEST イベントハンドラ

        期待されるペイロード:
        {
            "text": "読み上げテキスト",
            "username": "発言者名（オプション）",
            "speaker": "話者名（オプション）",
            "speaker_id": "VOICEVOX話者ID（オプション）",
            "role": "ロール（'streamer'/'ai'/'viewer'）（オプション、v17.6.0追加）",
            ...
        }

        v17.6.0: ロール別キャラ選択対応
        - role が指定されている場合、config から対応する speaker_id を取得
        - role 優先度: 明示的な speaker_id > role による自動選択 > デフォルト
        """
        logger.debug(f"🎯 [DEBUG] VoiceManager._on_voice_request() が呼ばれました！sender={sender}")
        logger.debug(f"🎯 [DEBUG] VoiceManager: event_data型={type(event_data)}")
        logger.debug(f"🎯 [DEBUG] VoiceManager: event_data={event_data}")
        try:
            if not isinstance(event_data, dict):
                logger.warning(f"⚠️ VOICE_REQUEST: 無効なペイロード形式: {type(event_data)}")
                return

            text = event_data.get("text", "")
            if not text:
                logger.warning("⚠️ VOICE_REQUEST: テキストが空です")
                return

            username = event_data.get("username", event_data.get("speaker", "System"))

            # ✅ v17.6.0 拡張: ロール別エンジン＆キャラ選択対応
            # 優先度: 明示的な speaker_id/engine > role による自動選択 > フォールバック順序 > デフォルト
            speaker_id = event_data.get("speaker_id")
            engine = event_data.get("engine")  # 明示的なエンジン指定（オプション）
            role = event_data.get("role")  # 'streamer', 'ai', 'viewer'

            # role が指定されている場合、config から engine と speaker_id を取得
            # ロール別設定が無い場合は、この段階ではスキップしてフォールバック順序に任せる
            if role and self.config_manager:
                try:
                    # エンジンが明示的に指定されていない場合、role から取得
                    if engine is None:
                        engine_key = f"voice.role.{role}.engine"
                        role_engine = self.config_manager.get(engine_key)
                        if role_engine:
                            engine = role_engine
                            logger.info(f"🎭 ロール '{role}' からエンジンを取得: {engine}")

                    # speaker_id が明示的に指定されていない場合、role から取得
                    if speaker_id is None:
                        speaker_key = f"voice.role.{role}.speaker_id"
                        role_speaker_id = self.config_manager.get(speaker_key)
                        if role_speaker_id is not None:
                            speaker_id = role_speaker_id
                            logger.info(f"🎭 ロール '{role}' から speaker_id を取得: {speaker_id}")
                        else:
                            logger.debug(f"ℹ️ ロール '{role}' の speaker_id が設定されていません（フォールバックに委譲）")
                except Exception as e:
                    logger.warning(f"⚠️ ロール '{role}' の設定取得エラー: {e}")

            # フォールバック順序設定を使用（roleベース設定がない場合の保険）
            # voice.fallback.engine1 → engine2 → os_tts の順で利用可能なエンジンを選択
            if engine is None and self.config_manager:
                try:
                    fallback_engine1 = self.config_manager.get("voice.fallback.engine1", "voicevox")
                    fallback_char1_id = self.config_manager.get("voice.fallback.char1_id")

                    # engine1が利用可能か確認（"system" → "os_tts" マッピング）
                    engine1_check = "os_tts" if fallback_engine1 == "system" else fallback_engine1
                    engine1_available = self.engines.get(engine1_check, {}).get("available", False)
                    if engine1_available:
                        engine = fallback_engine1
                        if speaker_id is None:
                            speaker_id = fallback_char1_id
                        logger.info(f"🔄 フォールバック順序: エンジン① '{engine}' を使用 (speaker_id={speaker_id})")
                    else:
                        # engine1が不可ならengine2を試行
                        fallback_engine2 = self.config_manager.get("voice.fallback.engine2", "system")
                        fallback_char2_id = self.config_manager.get("voice.fallback.char2_id")

                        # ✅ "system" を "os_tts" にマッピング（互換性のため）
                        engine2_check = "os_tts" if fallback_engine2 == "system" else fallback_engine2
                        engine2_available = self.engines.get(engine2_check, {}).get("available", False)
                        if engine2_available:
                            engine = fallback_engine2
                            if speaker_id is None:
                                speaker_id = fallback_char2_id
                            logger.info(f"🔄 フォールバック順序: エンジン② '{engine}' を使用 (speaker_id={speaker_id})")
                        else:
                            # engine2も不可ならWindows（os_tts）を最終フォールバックとして使用
                            if self.engines.get("os_tts", {}).get("available", False):
                                engine = "system"
                                logger.info("🔄 フォールバック順序: Windows音声（最終フォールバック）を使用")
                            else:
                                # OS TTSも利用不可なら fallback（ログのみ）
                                engine = "fallback"
                                logger.warning("⚠️ すべての音声エンジンが利用不可 - ログ出力のみ")
                except Exception as e:
                    logger.warning(f"⚠️ フォールバック順序取得エラー: {e}")

            # デフォルト値設定
            if engine is None:
                engine = "voicevox"  # デフォルトはVOICEVOX

            logger.info(f"📢 VOICE_REQUEST受信: {username} - {text[:50]}... (role={role}, engine={engine}, speaker_id={speaker_id})")
            logger.debug(f"🔧 [DEBUG] speak()呼び出し開始...")
            self.speak(text=text, speaker_name=username, engine=engine, speaker_id=speaker_id)
            logger.debug(f"✅ speak()呼び出し完了")

        except Exception as e:
            logger.error(f"❌ VOICE_REQUEST処理エラー: {e}", exc_info=True)

    # ------------------------------------------------------
    # 🔍 エンジン検出（完全防御版）
    # ------------------------------------------------------
    def _detect_engines(self):
        """VOICEVOX・棒読みちゃんをプローブして状態更新

        重要: このメソッドは絶対に例外を外に投げない。
        どんなエラーが起きても、アプリ本体の起動を妨げない。
        """
        try:
            import requests
        except ImportError:
            logger.warning("⚠️ requests モジュールが利用できません")
            return  # requests がない場合は静かに終了

        now = time.time()

        # VOICEVOX検出（完全防御）
        try:
            vvx = self.engines["voicevox"]
            if now >= self._vvx_next_probe_ts:
                try:
                    r = requests.get(f"{vvx['url']}/speakers", timeout=2)
                    if r.status_code == 200:
                        vvx["available"] = True
                        vvx["consecutive_failures"] = 0
                        self._vvx_backoff_sec = 2.0
                        logger.info("📱 VOICEVOX 検出成功")
                    else:
                        vvx["available"] = False
                except Exception as e:
                    vvx["available"] = False
                    vvx["consecutive_failures"] += 1
                    self._vvx_backoff_sec = min(self._vvx_backoff_sec * 2, self._vvx_backoff_max)
                    self._vvx_next_probe_ts = now + self._vvx_backoff_sec
                    if now - self._vvx_last_log_ts >= self._vvx_log_throttle_sec:
                        logger.info(f"📱 VOICEVOX 未検出: {e}")
                        self._vvx_last_log_ts = now
        except Exception as e:
            logger.debug(f"VOICEVOX検出処理でエラー（無視して続行）: {e}")
            # 絶対に例外を外に投げない

        # 棒読みちゃん検出（完全防御）
        try:
            bouyomi = self.engines["bouyomi"]
            try:
                url = f"http://{bouyomi['host']}:{bouyomi['port']}/GetVersion"
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    bouyomi["available"] = True
                    logger.info("📱 棒読みちゃん 検出成功")
                else:
                    bouyomi["available"] = False
            except Exception:
                bouyomi["available"] = False
        except Exception as e:
            logger.debug(f"棒読みちゃん検出処理でエラー（無視して続行）: {e}")
            # 絶対に例外を外に投げない

    # ------------------------------------------------------
    # 🧠 音声再生要求
    # ------------------------------------------------------
    def speak(self, text, speaker_name="", engine=None, speaker_id=None):
        """テキストを指定エンジンで再生キューへ追加

        Args:
            text: 読み上げテキスト
            speaker_name: 話者名
            engine: 音声エンジン ('voicevox', 'bouyomi', 'system')
            speaker_id: VOICEVOX話者IDまたは棒読みちゃん音声ID
        """
        try:
            if self.voice_queue.qsize() >= self.max_queue_size:
                self.stats["queue_overflows"] += 1
                logger.warning("⚠️ 音声キュー満杯")
                return False

            # キューに辞書形式で追加
            request = {
                "name": speaker_name,
                "text": text,
                "engine": engine or "voicevox",  # デフォルトはVOICEVOX
                "speaker_id": speaker_id
            }
            self.voice_queue.put(request)
            self.stats["total_requests"] += 1
            self.stats["queue_peak"] = max(self.stats["queue_peak"], self.voice_queue.qsize())
            return True
        except Exception as e:
            logger.error(f"❌ 音声キューエラー: {e}")
            return False

    # ------------------------------------------------------
    # 🎛️ ワーカー起動
    # ------------------------------------------------------
    def _start_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("🔄 VoiceManager ワーカースレッド開始")

    # ------------------------------------------------------
    # 🎧 ワーカー処理ループ
    # ------------------------------------------------------
    def _worker_loop(self):
        """音声再生ループ（エンジン指定に基づく再生）"""
        while self.running:
            try:
                if self.voice_queue.empty():
                    time.sleep(0.1)
                    continue

                # キューから辞書を取得（後方互換性のためタプルも対応）
                request = self.voice_queue.get()

                # 後方互換性：タプルの場合は辞書に変換
                if isinstance(request, tuple):
                    name, text = request
                    request = {"name": name, "text": text, "engine": "voicevox", "speaker_id": None}

                name = request.get("name", "")
                text = request.get("text", "")
                engine = request.get("engine", "voicevox")
                speaker_id = request.get("speaker_id")

                success = False

                # エンジンに応じた処理
                if engine == "voicevox":
                    # VOICEVOX指定時
                    if self.engines["voicevox"]["available"]:
                        # speaker_idが指定されている場合は一時的に設定
                        old_speaker = None
                        if speaker_id is not None:
                            old_speaker = self.engines["voicevox"]["default_speaker"]
                            self.engines["voicevox"]["default_speaker"] = int(speaker_id)
                            logger.debug(f"🎭 一時的にVOICEVOX話者ID設定: {speaker_id}")

                        success = self._play_voicevox(text)

                        # speaker_idを元に戻す
                        if old_speaker is not None:
                            self.engines["voicevox"]["default_speaker"] = old_speaker

                        if not success and self.engines["os_tts"]["available"]:
                            logger.info("🔄 VOICEVOX失敗 → OS TTSにフォールバック")
                            success = self._play_os_tts(name, text)
                    elif self.engines["os_tts"]["available"]:
                        success = self._play_os_tts(name, text)

                elif engine == "bouyomi":
                    # 棒読みちゃん指定時
                    if self.engines["bouyomi"]["available"]:
                        success = self._play_bouyomi(text, voice_id=speaker_id)
                        if not success and self.engines["os_tts"]["available"]:
                            logger.info("🔄 棒読みちゃん失敗 → OS TTSにフォールバック")
                            success = self._play_os_tts(name, text)
                    elif self.engines["os_tts"]["available"]:
                        success = self._play_os_tts(name, text)

                elif engine == "system":
                    # Windows音声（OS TTS）指定時
                    if self.engines["os_tts"]["available"]:
                        success = self._play_os_tts(name, text)

                else:
                    # 未知のエンジン → デフォルト動作
                    logger.warning(f"⚠️ 未知のエンジン指定: {engine}、VOICEVOXで試行")
                    if self.engines["voicevox"]["available"]:
                        success = self._play_voicevox(text)
                    elif self.engines["os_tts"]["available"]:
                        success = self._play_os_tts(name, text)

                # すべて失敗した場合はログ出力のみ
                if not success:
                    success = self._play_fallback(name, text)

                if success:
                    self.stats["successful_plays"] += 1
                else:
                    self.stats["failed_plays"] += 1

            except Exception as e:
                logger.error(f"❌ 音声再生エラー: {e}")
                time.sleep(0.5)

    # ------------------------------------------------------
    # 🔊 各エンジン再生処理
    # ------------------------------------------------------
    def _play_os_tts(self, name, text):
        """OS標準TTS（SAPI経由）で音声再生"""
        try:
            if not self._os_tts:
                return False

            logger.info(f"🎤 音声再生開始 [os_tts]: {name} - {text[:30]}...")

            # ✅ shared.tts_fallback の SAPI ベース実装を使用
            from shared.tts_fallback import speak_text as sapi_speak

            # 音量と速度を取得（デフォルト値を使用）
            volume = self.volume  # 0.0 ~ 1.0
            rate = self.speed     # 1.0 = 標準速度

            # SAPI で音声再生
            success = sapi_speak(text, voice=None, rate=rate, volume=volume)

            if success:
                logger.info(f"🔊 OS TTS音声再生: {name} - {text[:30]}...")
                self.stats["os_tts_uses"] += 1
                return True
            else:
                logger.warning(f"⚠️ OS TTS音声再生失敗: SAPI実行エラー")
                return False

        except Exception as e:
            logger.error(f"❌ OS TTS音声再生に失敗しました: {e}")
            return False

    def _play_voicevox(self, text):
        """VOICEVOX で音声合成して再生する。

        優先順位:
        1. simpleaudio が使えれば simpleaudio で再生
        2. simpleaudio が無ければ winsound（Windows 標準）で再生
        """
        try:
            import requests
            import json

            vvx = self.engines["voicevox"]
            speaker = vvx["default_speaker"]
            url = vvx["url"]
            volume = vvx.get("volume", 1.0)  # デフォルトは 1.0

            # ① audio_query
            r1 = requests.post(
                f"{url}/audio_query",
                params={"text": text, "speaker": speaker},
                timeout=5,
            )
            r1.raise_for_status()

            # ② audio_query の結果に音量を適用
            query_data = r1.json()
            query_data["volumeScale"] = volume
            logger.debug(f"🔊 VOICEVOX volumeScale={volume} を適用")

            # ③ synthesis
            r2 = requests.post(
                f"{url}/synthesis",
                params={"speaker": speaker},
                json=query_data,  # data ではなく json で送る
                timeout=10,
            )
            if r2.status_code != 200:
                logger.warning(f"⚠️ VOICEVOX再生失敗: status={r2.status_code}")
                return False

            audio_data = r2.content

            # まずは simpleaudio を試す
            try:
                import simpleaudio
                import io
                import wave

                with wave.open(io.BytesIO(audio_data), "rb") as wf:
                    raw = wf.readframes(wf.getnframes())
                    simpleaudio.play_buffer(
                        raw,
                        wf.getnchannels(),
                        wf.getsampwidth(),
                        wf.getframerate(),
                    )
                logger.info(f"🎤 VOICEVOX音声再生(simpleaudio): {text[:30]}...")
                return True

            except Exception as e_simple:
                # simpleaudio が無い／失敗した場合は winsound にフォールバック
                try:
                    import winsound

                    # audio_data は WAV バイナリなので、そのまま SND_MEMORY で再生可能
                    winsound.PlaySound(
                        audio_data,
                        winsound.SND_MEMORY | winsound.SND_NODEFAULT,
                    )
                    logger.info(f"🎤 VOICEVOX音声再生(winsound): {text[:30]}...")
                    return True

                except Exception as e_win:
                    logger.warning(
                        f"⚠️ VOICEVOX再生エラー(simpleaudio/winsound両方失敗): "
                        f"{e_simple} / {e_win}"
                    )
                    self.stats["voicevox_fails"] += 1
                    return False

        except Exception as e:
            logger.warning(f"⚠️ VOICEVOX再生エラー: {e}")
            self.stats["voicevox_fails"] += 1
            return False

    def _play_bouyomi(self, text, voice_id=None):
        """棒読みちゃん HTTP API で音声再生する

        Args:
            text: 読み上げテキスト
            voice_id: 音声種類ID (0:女性1, 1:女性2, 2:男性1, 3:男性2, 4:中性, 5:ロボット, 6:機械1, 7:機械2)
        """
        try:
            import requests
            import urllib.parse

            bouyomi = self.engines["bouyomi"]
            host = bouyomi["host"]
            port = bouyomi["port"]

            # voice_id が指定されていない場合はデフォルト(0:女性1)
            if voice_id is None:
                voice_id = 0

            # 棒読みちゃんHTTP API: http://host:port/Talk?text=...&voice=...
            url = f"http://{host}:{port}/Talk"
            params = {
                "text": text,
                "voice": int(voice_id)
            }

            logger.info(f"🎤 棒読みちゃん音声再生開始: voice={voice_id}, text={text[:30]}...")
            r = requests.get(url, params=params, timeout=5)
            r.raise_for_status()

            logger.info(f"🔊 棒読みちゃん音声再生成功: {text[:30]}...")
            self.stats["bouyomi_uses"] = self.stats.get("bouyomi_uses", 0) + 1
            return True

        except Exception as e:
            logger.warning(f"⚠️ 棒読みちゃん再生エラー: {e}")
            self.stats["bouyomi_fails"] += 1
            return False

    def _play_fallback(self, name, text):
        try:
            logger.info(f"🪶 Fallback出力: {name}: {text}")
            _fallback_speak(f"{name}、{text}")
            return True
        except Exception as e:
            logger.error(f"❌ Fallback再生エラー: {e}")
            return False

    # ------------------------------------------------------
    # 📊 ステータス取得
    # ------------------------------------------------------
    def get_status(self):
        """外部（タブ等）からのステータス要求用"""
        try:
            return {
                "available": self.available,
                "current_engine": self.current_engine,
                "queue_size": self.voice_queue.qsize(),
                "os_tts": self.engines["os_tts"]["available"],
                "voicevox": self.engines["voicevox"]["available"],
            }
        except Exception as e:
            logger.error(f"❌ ステータス取得エラー: {e}")
            return {"available": False, "error": str(e)}

    # ------------------------------------------------------
    # ⏹️ 終了系・キュー制御
    # ------------------------------------------------------
    def clear_queue(self):
        """音声キューを全削除（v16系との後方互換用）"""
        try:
            while not self.voice_queue.empty():
                self.voice_queue.get_nowait()
            logger.info("🧹 VoiceManager キュークリア完了")
        except Exception as e:
            logger.error(f"❌ キュークリアエラー: {e}")

    def stop_all(self):
        """キューをクリアしてワーカーを停止（旧バージョン互換メソッド）"""
        try:
            self.clear_queue()
        except Exception:
            pass
        self.stop()

    def stop(self):
        """ワーカースレッドのみ停止（v17.3標準）"""
        try:
            self.running = False
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2)

            # MessageBus 購読解除
            # 注: MessageBus には unsubscribe メソッドがないため、
            # 購読は自動的にガベージコレクションされます
            if _HAS_MESSAGE_BUS and self._subscriptions:
                self._subscriptions.clear()
                logger.info("📡 VoiceManager: MessageBus購読リストクリア完了")

            logger.info("🛑 VoiceManager停止完了")
        except Exception as e:
            logger.error(f"❌ VoiceManager停止エラー: {e}")

    # ------------------------------------------------------
    # 🎤 speak_textメソッド（v17.3互換インタフェース）
    # ------------------------------------------------------
    def speak_text(self, text: str, username: str = "System", **kwargs):
        """
        v17.5.x 拡張版:
        - speaker_id, volume が渡された場合は self.speak() に渡す
        - speaker_id は一時指定として扱い、default_speaker を変更・保存しない
        - volume は VoiceManager 内部の volume 設定として保存
        """
        speaker_id = kwargs.get("speaker_id", None)
        volume = kwargs.get("volume", None)

        # volume の処理（VoiceManager全体の音量として保存）
        if volume is not None:
            try:
                volume_float = float(volume)
                # 0.0 ~ 2.0 の範囲にクランプ
                volume_float = max(0.0, min(2.0, volume_float))

                vvx = self.engines.get("voicevox")
                if vvx is not None:
                    old_volume = vvx.get("volume", None)
                    vvx["volume"] = volume_float
                    logger.debug(f"🔊 VOICEVOX volume を {old_volume} → {volume_float} に更新")

                    # 設定マネージャがあれば永続化
                    if self.config_manager is not None:
                        try:
                            self.config_manager.set("voice.voicevox.volume", volume_float)
                            self.config_manager.save()
                            logger.debug("💾 voice.voicevox.volume を保存しました")
                        except Exception as e_cfg:
                            logger.warning(f"⚠️ volume 保存に失敗: {e_cfg}")
            except (TypeError, ValueError):
                logger.warning(f"⚠️ 無効な volume 指定: {volume}")

        # speaker_id は一時指定として speak() に渡すだけ（default_speaker を変更しない）
        try:
            return self.speak(text, speaker_name=username, speaker_id=speaker_id)
        except Exception as e:
            logger.error(f"❌ speak_textエラー: {e}")
            return False

    # ------------------------------------------------------
    # 📊 statusメソッド（v17.3互換インタフェース）
    # ------------------------------------------------------
    def status(self):
        """
        v17.3互換: ステータスを返す（get_status のエイリアス）
        """
        return self.get_status()


# ==========================================================
# ====== v17.3 公開API（正本・重複禁止） ====================
# ==========================================================

def get_voice_manager(config_manager=None, message_bus=None):
    """
    v17.3 標準アクセサ:
      - 既存コードは: from shared.voice_manager_singleton import get_voice_manager
      - 初回だけ Singleton を生成し以後は同一個体を返す
      - message_bus を渡すことで、MessageBusインスタンスを統一できる
    """
    global _VOICE_MANAGER_SINGLETON
    if _VOICE_MANAGER_SINGLETON is None:
        _VOICE_MANAGER_SINGLETON = VoiceManagerSingleton(
            config_manager=config_manager,
            message_bus=message_bus
        )
    return _VOICE_MANAGER_SINGLETON


def speak_text(text: str, username: str = "System", **kwargs):
    """v17.3互換: VoiceManager.speak_text をモジュール関数として提供"""
    vm = get_voice_manager()
    return vm.speak_text(text=text, username=username, **kwargs)


def get_voice_status() -> dict:
    """v17.3互換: ステータス取得"""
    vm = get_voice_manager()
    return vm.status()


def stop_voice_manager():
    """v17.3互換: ワーカー停止（旧 stop_all 互換も維持）"""
    vm = get_voice_manager()
    try:
        # 旧stop_allが呼ばれても大丈夫なように
        if hasattr(vm, "stop_all"):
            return vm.stop_all()
        return vm.stop()
    except Exception:
        return vm.stop()


def clear_voice_queue():
    """キューのみクリア（必要ならタブ側から呼び出し）"""
    vm = get_voice_manager()
    try:
        return vm.clear_queue()
    except Exception:
        return None


# 公開シンボル
__all__ = [
    "VoiceManagerSingleton",
    "get_voice_manager",
    "speak_text",
    "get_voice_status",
    "stop_voice_manager",
    "clear_voice_queue",
]
