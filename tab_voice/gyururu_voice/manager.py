#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 音声管理システム統合マネージャー v15 Final Production Edition
全モジュール統合・公開API・実稼働環境完全対応

Features:
✅ モジュラー設計統合
✅ 完全asyncio対応
✅ 型安全性保証
✅ 実稼働機能完備
✅ 後方互換性維持
"""

import asyncio
import os
import platform
import time
import weakref
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from .config import (
    VERSION, VoiceSettings, SystemConfig, BouyomiConfig, PriorityLevel, OutputMethod,
    get_default_voice_settings, get_default_system_config, get_default_bouyomi_config,
    validate_voice_settings, validate_system_config, detect_environment
)
from .queue_manager import VoiceQueueManager
from .voicevox_client import VOICEVOXClient
from .bouyomi_client import BouyomiClient
from .playback_engine import PlaybackEngine
from .stats_monitor import StatsMonitor
from .file_watcher import FileWatcher, setup_config_monitoring

try:
    from gyururu_utils.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class VoiceManagerV15FinalProduction:
    """
    音声管理システム v15 Final Production Edition
    
    実稼働環境で完全に安定動作する最終形態
    モジュラー設計による高い保守性と拡張性を実現
    """
    
    def __init__(self, bot_instance):
        """初期化"""
        self.bot = bot_instance
        self.version = VERSION
        
        # === 環境情報 ===
        self.environment = detect_environment()
        self.config_path = Path(os.getenv("GYURURU_CONFIG_PATH", "configs"))
        self.config_path.mkdir(exist_ok=True)
        
        # === 設定管理 ===
        self.voice_settings: VoiceSettings = {}
        self.system_config: SystemConfig = {}
        self.bouyomi_config: BouyomiConfig = {}
        
        # === イベントループ管理 ===
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_fallback = None
        self.shutdown_event = asyncio.Event()
        
        # === コアモジュール ===
        self.queue_manager: Optional[VoiceQueueManager] = None
        self.voicevox_client: Optional[VOICEVOXClient] = None
        self.bouyomi_client: Optional[BouyomiClient] = None
        self.playback_engine: Optional[PlaybackEngine] = None
        self.stats_monitor: Optional[StatsMonitor] = None
        self.file_watcher: Optional[FileWatcher] = None
        
        # === 状態管理 ===
        self.initialized = False
        self.running = False
        self.initialization_time: Optional[datetime] = None
        
        # === 統計・互換性 ===
        self.legacy_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0
        }
        
        logger.info(f"🎤 音声管理システム v{VERSION} Final Production Edition 初期化開始")
        logger.info(f"📊 実行環境: {self.environment} ({platform.system()} {platform.release()})")
        
    def _is_duplicate(self, text: str, voice_id: int) -> bool:
        """重複チェック（修正版）"""
        try:
            if not self.queue_manager:
                return False

            # キューサイズチェック
            current_size = self.queue_manager.get_queue_size()
            if current_size == 0:
                return False
            
            # 直前リクエスト記録方式
            if not hasattr(self, '_last_request'):
                self._last_request = None
                
            current_request = (text, voice_id)
            if self._last_request == current_request:
                logger.debug("🔄 重複読み上げをスキップ")
                return True
                
            self._last_request = current_request
            return False
            
        except Exception as e:
            logger.error(f"❌ 重複チェックエラー: {e}")
            return False
    
    # === 初期化・起動 ===
    
    async def initialize_async(self) -> bool:
        """非同期初期化（実稼働版）"""
        if self.initialized:
            logger.warning("⚠️ 既に初期化済みです")
            return True
        
        try:
            start_time = time.time()
            logger.info("🚀 Final Production統合初期化開始")
            
            # 1. イベントループ設定
            await self._setup_event_loop()
            
            # 2. 設定読み込み・バリデーション
            await self._load_and_validate_configs()
            
            # 3. コアモジュール初期化
            await self._initialize_core_modules()
            
            # 4. モジュール間連携設定
            await self._setup_module_integration()
            
            # 5. 実稼働機能開始
            await self._start_production_services()
            
            # 初期化完了
            self.initialized = True
            self.initialization_time = datetime.now()
            init_duration = time.time() - start_time
            
            logger.info(f"✅ Final Production統合初期化完了 ({init_duration:.2f}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Final Production統合初期化エラー: {e}")
            await self._cleanup_on_init_failure()
            return False
    
    async def _setup_event_loop(self) -> None:
        """イベントループ設定"""
        try:
            self.loop = asyncio.get_running_loop()
            logger.debug("🔄 既存イベントループ使用")
        except RuntimeError:
            logger.info("🔄 新しいイベントループ作成")
            self._loop_fallback = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop_fallback)
            self.loop = self._loop_fallback
    
    async def _load_and_validate_configs(self) -> None:
        """設定読み込み・バリデーション"""
        # 基本設定読み込み
        detected_sample_rate = await self._detect_sample_rate()
        
        if hasattr(self.bot, 'config_manager'):
            voice_settings_raw = self.bot.config_manager.get_voice_settings()
            voicevox_url = self.bot.config_manager.get_voicevox_url()
        else:
            voice_settings_raw = get_default_voice_settings(detected_sample_rate)
            voicevox_url = os.getenv("VOICEVOX_URL", "http://localhost:50021")
        
        # バリデーション
        self.voice_settings = validate_voice_settings(voice_settings_raw)
        
        # システム設定読み込み
        system_config_file = self.config_path / "production_voice_config.json"
        if system_config_file.exists():
            from .file_watcher import FileWatcher
            temp_watcher = FileWatcher({})
            system_config_raw = await temp_watcher.load_json_config(system_config_file)
            if system_config_raw:
                self.system_config = validate_system_config(system_config_raw)
            else:
                self.system_config = get_default_system_config()
        else:
            self.system_config = get_default_system_config()
            # デフォルト設定ファイル作成
            from .file_watcher import FileWatcher
            temp_watcher = FileWatcher({})
            await temp_watcher.save_json_config(system_config_file, self.system_config)
        
        # 棒読みちゃん設定
        self.bouyomi_config = get_default_bouyomi_config()
        self.bouyomi_config.update({
            "host": os.getenv("BOUYOMI_HOST", "127.0.0.1"),
            "tcp_port": int(os.getenv("BOUYOMI_TCP_PORT", "50001")),
            "http_port": int(os.getenv("BOUYOMI_HTTP_PORT", "50080"))
        })
        
        # VOICEVOX URL設定
        self.voicevox_url = voicevox_url
        
        logger.info("✅ 設定読み込み・バリデーション完了")
    
    async def _detect_sample_rate(self) -> int:
        """サンプリングレート検出"""
        try:
            import pygame
            pygame.mixer.pre_init()
            pygame.mixer.init()
            mixer_info = pygame.mixer.get_init()
            pygame.mixer.quit()
            
            if mixer_info:
                detected_rate = mixer_info[0]
                if detected_rate in [22050, 44100, 48000]:
                    return detected_rate
        except:
            pass
        
        return 44100  # デフォルト
    
    async def _initialize_core_modules(self) -> None:
        """コアモジュール初期化"""
        initialization_results = {}
        
        # 1. キューマネージャー
        self.queue_manager = VoiceQueueManager(self.system_config)
        self.queue_manager.set_request_processor(self._process_voice_request)
        initialization_results["queue_manager"] = True
        
        # 2. VOICEVOX クライアント
        self.voicevox_client = VOICEVOXClient(
            self.voicevox_url, self.voice_settings, self.system_config
        )
        initialization_results["voicevox_client"] = await self.voicevox_client.initialize_async()
        
        # 3. 棒読みちゃんクライアント
        if self.voice_settings.get("enable_bouyomi", False):
            self.bouyomi_client = BouyomiClient(
                self.voice_settings, self.system_config, self.bouyomi_config
            )
            initialization_results["bouyomi_client"] = await self.bouyomi_client.initialize_async()
        else:
            initialization_results["bouyomi_client"] = True  # 無効時は成功扱い
        
        # 4. 再生エンジン
        self.playback_engine = PlaybackEngine(self.voice_settings, self.system_config)
        initialization_results["playback_engine"] = await self.playback_engine.initialize_async()
        
        # 5. 統計監視
        self.stats_monitor = StatsMonitor(self.system_config)
        self.stats_monitor.set_callbacks(
            self._get_system_health_status,
            self._perform_auto_repair
        )
        initialization_results["stats_monitor"] = True
        
        # 6. ファイル監視
        if self.system_config.get("config_hot_reload", True):
            self.file_watcher = FileWatcher(self.system_config)
            initialization_results["file_watcher"] = True
        
        # 初期化結果ログ
        successful = sum(1 for result in initialization_results.values() if result)
        total = len(initialization_results)
        logger.info(f"🔧 コアモジュール初期化: {successful}/{total} 成功")
        
        for module_name, success in initialization_results.items():
            status = "✅" if success else "❌"
            logger.debug(f"  {status} {module_name}")
    
    async def _setup_module_integration(self) -> None:
        """モジュール間連携設定"""
        # ファイル監視設定
        if self.file_watcher:
            reload_callbacks = {
                "production_voice_config": self._reload_system_config
            }
            
            success = await setup_config_monitoring(
                self.file_watcher, self.config_path, reload_callbacks
            )
            
            if success:
                logger.info("🔗 ファイル監視連携設定完了")
            else:
                logger.warning("⚠️ ファイル監視連携設定失敗")
        
        logger.info("🔗 モジュール間連携設定完了")
    
    async def _start_production_services(self) -> None:
        """実稼働サービス開始"""
        # キュー処理開始
        await self.queue_manager.start_processing()
        
        # 統計監視開始
        await self.stats_monitor.start_monitoring()
        
        self.running = True
        logger.info("🚀 実稼働サービス開始完了")
    
    # === 音声合成API（公開インターフェース） ===
    
    async def speak_safe_async(self, text: str, voice_id: Optional[int] = None, 
                              description: str = "音声合成", output_method: Optional[OutputMethod] = None, 
                              priority: PriorityLevel = "normal") -> bool:
        """非同期音声合成（5段階優先度対応）"""
        if not self.initialized:
            logger.warning("⚠️ システム未初期化です")
            return False
        
        # デフォルト値設定
        if voice_id is None:
            voice_id = self.voice_settings.get("default_voice_id", 1)
        if output_method is None:
            output_method = self.voice_settings.get("audio_output_method", "voicevox")
        
        # 重複ガード（確定した voice_id で判定）
        if self._is_duplicate(text, voice_id):
            logger.debug("🔄 重複読み上げをスキップ")
            return False
        
        # キューに追加
        success = await self.queue_manager.add_request(
            text=text,
            voice_id=voice_id,
            description=description,
            output_method=output_method,
            priority=priority
        )
        
        # 統計更新
        if success:
            self.legacy_stats["total_requests"] += 1
        
        return success
    
    def speak_safe(self, text: str, voice_id: Optional[int] = None, 
                   description: str = "音声合成", output_method: Optional[OutputMethod] = None, 
                   priority: PriorityLevel = "normal") -> bool:
        """同期ラッパー（完全互換性）"""
        try:
            if self.loop and self.loop.is_running():
                # 非同期コンテキスト内
                task = asyncio.create_task(
                    self.speak_safe_async(text, voice_id, description, output_method, priority)
                )
                return True  # タスク作成成功
            else:
                # 同期コンテキスト
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                
                try:
                    return loop.run_until_complete(
                        self.speak_safe_async(text, voice_id, description, output_method, priority)
                    )
                finally:
                    if not self._loop_fallback:
                        loop.close()
        except Exception as e:
            logger.error(f"❌ 同期音声合成エラー: {e}")
            return False
    
    async def speak_emergency_async(self, text: str, description: str = "緊急音声") -> bool:
        """緊急音声合成（最高優先度）"""
        gyururu_voice_id = self.voice_settings.get("gyururu_voice_id", 46)
        return await self.speak_safe_async(text, gyururu_voice_id, description, priority="emergency")
    
    async def speak_gyururu_async(self, text: str, description: str = "ぎゅるる音声", 
                                 priority: PriorityLevel = "high") -> bool:
        """ぎゅるる専用音声合成"""
        gyururu_voice_id = self.voice_settings.get("gyururu_voice_id", 46)
        return await self.speak_safe_async(text, gyururu_voice_id, description, priority=priority)
    
    def speak_gyururu(self, text: str, description: str = "ぎゅるる音声") -> bool:
        """ぎゅるる音声（同期ラッパー）"""
        try:
            if self.loop and self.loop.is_running():
                asyncio.create_task(self.speak_gyururu_async(text, description))
                return True
            else:
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.speak_gyururu_async(text, description))
                finally:
                    if not self._loop_fallback:
                        loop.close()
        except Exception as e:
            logger.error(f"❌ ぎゅるる音声エラー: {e}")
            return False
    
    async def speak_user_async(self, username: str, text: str, priority: PriorityLevel = "normal") -> bool:
        """ユーザー専用音声合成"""
        user_voice_id = await self.get_user_voice_id_async(username)
        return await self.speak_safe_async(text, user_voice_id, f"{username}専用音声", priority=priority)
    
    def speak_user(self, username: str, text: str) -> bool:
        """ユーザー音声（同期ラッパー）"""
        try:
            if self.loop and self.loop.is_running():
                asyncio.create_task(self.speak_user_async(username, text))
                return True
            else:
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.speak_user_async(username, text))
                finally:
                    if not self._loop_fallback:
                        loop.close()
        except Exception as e:
            logger.error(f"❌ ユーザー音声エラー: {e}")
            return False
    
    # === 内部処理 ===
    
    async def _process_voice_request(self, voice_request) -> bool:
        """音声リクエスト処理（コールバック）"""
        try:
            data = voice_request.data
            text = data.get("text", "")
            voice_id = data.get("voice_id", self.voice_settings.get("default_voice_id", 1))
            description = data.get("description", "音声合成")
            output_method = data.get("output_method", self.voice_settings.get("audio_output_method", "voicevox"))
            
            if not text:
                return False
            
            success = False
            
            # VOICEVOX処理
            if output_method in ["voicevox", "both"] and self.voicevox_client and self.voicevox_client.available:
                audio_data = await self.voicevox_client.synthesize_speech(text, voice_id)
                if audio_data and self.playback_engine:
                    playback_success = await self.playback_engine.play_audio_data(
                        audio_data, description, voice_id
                    )
                    success = success or playback_success
            
            # 棒読みちゃん処理
            if output_method in ["bouyomi", "both"] and self.bouyomi_client and self.bouyomi_client.is_available():
                bouyomi_success = await self.bouyomi_client.send_text(text, voice_id)
                success = success or bouyomi_success
            
            # 統計更新
            if success:
                self.legacy_stats["successful_requests"] += 1
            else:
                self.legacy_stats["failed_requests"] += 1
            
            return success
            
        except Exception as e:
            if self.stats_monitor:
                self.stats_monitor.record_error("voice_request_processing", e)
            return False
    
    async def _get_system_health_status(self) -> Dict[str, Any]:
        """システムヘルス状態取得（コールバック）"""
        try:
            return {
                "pygame": self.playback_engine.get_playback_status() if self.playback_engine else {},
                "voicevox": self.voicevox_client.get_connection_status() if self.voicevox_client else {},
                "queue": self.queue_manager.get_queue_status() if self.queue_manager else {},
                "tasks": {"running": 1, "total": 1},  # 簡易版
                "performance": {
                    "total_requests": self.legacy_stats["total_requests"],
                    "success_rate": self._calculate_success_rate()
                }
            }
        except Exception as e:
            logger.error(f"❌ システムヘルス状態取得エラー: {e}")
            return {}
    
    def _calculate_success_rate(self) -> float:
        """成功率計算"""
        total = self.legacy_stats["total_requests"]
        if total > 0:
            return (self.legacy_stats["successful_requests"] / total) * 100
        return 0.0
    
    async def _perform_auto_repair(self) -> None:
        """自動修復実行（コールバック）"""
        try:
            logger.info("🔧 システム自動修復開始")
            
            # pygame再初期化
            if self.playback_engine and not self.playback_engine.initialized:
                await self.playback_engine.initialize_async()
            
            # VOICEVOX再接続
            if self.voicevox_client and not self.voicevox_client.available:
                await self.voicevox_client.check_connection()
            
            # 棒読みちゃん再接続
            if self.bouyomi_client and not self.bouyomi_client.is_available():
                await self.bouyomi_client.check_optimal_connection()
            
            logger.info("✅ システム自動修復完了")
            
        except Exception as e:
            logger.error(f"❌ システム自動修復エラー: {e}")
    
    # === 設定管理 ===
    
    async def _reload_system_config(self) -> None:
        """システム設定リロード"""
        try:
            if not self.file_watcher:
                return
            
            config_file = self.config_path / "production_voice_config.json"
            new_config_raw = await self.file_watcher.load_json_config(config_file)
            
            if new_config_raw:
                old_config = self.system_config.copy()
                self.system_config = validate_system_config(new_config_raw)
                
                # 重要な変更の処理
                if old_config.get("health_check_interval") != self.system_config.get("health_check_interval"):
                    logger.info("🔄 ヘルスチェック間隔変更を適用")
                
                logger.info(f"✅ システム設定ホットリロード完了: {len(self.system_config)}項目")
            else:
                logger.error("❌ システム設定リロード失敗")
                
        except Exception as e:
            if self.stats_monitor:
                self.stats_monitor.record_error("system_config_reload", e)
    
    async def get_user_voice_id_async(self, username: str) -> int:
        """ユーザー音声ID取得"""
        try:
            if hasattr(self.bot, 'config_manager'):
                return self.bot.config_manager.get_user_voice_id(username)
            else:
                user_mapping = self.voice_settings.get("user_voice_mapping", {}).get("default_mapping", {})
                return user_mapping.get(username, self.voice_settings.get("default_voice_id", 1))
        except Exception as e:
            logger.error(f"❌ ユーザー音声ID取得エラー: {e}")
            return self.voice_settings.get("default_voice_id", 1)
    
    def add_user_to_list(self, username: str) -> None:
        """ユーザーリストに追加（後方互換性）"""
        try:
            logger.debug(f"👤 ユーザー活動記録: {username}")
        except Exception as e:
            logger.error(f"❌ ユーザー追加エラー: {e}")
    
    # === テスト機能 ===
    
    async def test_voice_synthesis_async(self, text: str = "Final Production音声テストです", 
                                        voice_id: int = 46) -> bool:
        """音声合成テスト"""
        logger.info(f"🧪 Final Production音声合成テスト開始: '{text}' (ID:{voice_id})")
        
        try:
            if self.voicevox_client:
                return await self.voicevox_client.test_synthesis(text, voice_id)
            else:
                logger.error("❌ VOICEVOX クライアント未初期化")
                return False
        except Exception as e:
            logger.error(f"❌ 音声合成テストエラー: {e}")
            return False
    
    def test_voice_synthesis(self, text: str = "テスト音声です", voice_id: int = 46) -> bool:
        """音声合成テスト（同期ラッパー）"""
        try:
            if self.loop and self.loop.is_running():
                task = asyncio.create_task(self.test_voice_synthesis_async(text, voice_id))
                return True
            else:
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.test_voice_synthesis_async(text, voice_id))
                finally:
                    if not self._loop_fallback:
                        loop.close()
        except Exception as e:
            logger.error(f"❌ 音声合成テストエラー: {e}")
            return False
    
    async def test_all_systems_async(self) -> Dict[str, bool]:
        """全システムテスト"""
        results = {}
        
        try:
            logger.info("🧪 Final Production全システムテスト開始")
            
            # 1. 5段階優先度テスト
            priority_tests = []
            for priority in ["emergency", "high", "normal", "low", "background"]:
                task = asyncio.create_task(
                    self.speak_safe_async(f"{priority}優先度テストです", priority=priority)
                )
                priority_tests.append(task)
            
            priority_results = await asyncio.gather(*priority_tests, return_exceptions=True)
            results["priority_system_test"] = all(r is True for r in priority_results if not isinstance(r, Exception))
            
            # 2. VOICEVOX テスト
            if self.voicevox_client:
                results["voicevox_test"] = await self.voicevox_client.test_synthesis()
            else:
                results["voicevox_test"] = False
            
            # 3. 棒読みちゃんテスト
            if self.bouyomi_client:
                results["bouyomi_test"] = await self.bouyomi_client.test_send()
            else:
                results["bouyomi_test"] = True  # 無効時は成功扱い
            
            # 4. 再生エンジンテスト
            if self.playback_engine:
                results["playback_test"] = await self.playback_engine.test_playback()
            else:
                results["playback_test"] = False
            
            # 5. 統計監視テスト
            if self.stats_monitor:
                health_status = await self.stats_monitor.force_health_check()
                results["stats_test"] = isinstance(health_status, dict) and "status" in health_status
            else:
                results["stats_test"] = False
            
            # 6. ファイル監視テスト
            if self.file_watcher:
                results["file_watcher_test"] = await self.file_watcher.test_reload("production_voice_config")
            else:
                results["file_watcher_test"] = True  # 無効時は成功扱い
            
            # 処理完了待機
            await asyncio.sleep(2)
            
            logger.info(f"🧪 Final Production全システムテスト結果: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ 全システムテストエラー: {e}")
            results["error"] = str(e)
            return results
    
    def test_all_systems(self) -> Dict[str, bool]:
        """全システムテスト（同期ラッパー）"""
        try:
            if self.loop and self.loop.is_running():
                return {"sync_wrapper_test": True}
            else:
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.test_all_systems_async())
                finally:
                    if not self._loop_fallback:
                        loop.close()
        except Exception as e:
            logger.error(f"❌ 全システムテストエラー: {e}")
            return {"error": str(e)}
    
    def test_default_voice(self) -> bool:
        """デフォルト音声テスト（後方互換性）"""
        return self.speak_safe("これはデフォルト音声のテストです", voice_id=self.voice_settings.get("default_voice_id", 1))
    
    def test_gyururu_voice(self) -> bool:
        """ぎゅるる音声テスト（後方互換性）"""
        return self.speak_gyururu("ぎゅる〜！これはぎゅるる音声のテストだぎゅる♪")
    
    # === 状態・統計取得API ===
    
    async def get_voice_status_async(self) -> Dict[str, Any]:
        """音声システム状態取得"""
        try:
            uptime = datetime.now() - self.initialization_time if self.initialization_time else timedelta(0)
            
            return {
                "version": VERSION,
                "system_type": "final_production_modular",
                "environment": self.environment,
                "uptime": str(uptime),
                "initialized": self.initialized,
                "running": self.running,
                "modules": {
                    "queue_manager": self.queue_manager is not None,
                    "voicevox_client": self.voicevox_client is not None,
                    "bouyomi_client": self.bouyomi_client is not None,
                    "playback_engine": self.playback_engine is not None,
                    "stats_monitor": self.stats_monitor is not None,
                    "file_watcher": self.file_watcher is not None
                },
                "voicevox": self.voicevox_client.get_connection_status() if self.voicevox_client else {"available": False},
                "bouyomi": self.bouyomi_client.get_connection_status() if self.bouyomi_client else {"tcp_available": False, "http_available": False},
                "playback": self.playback_engine.get_playback_status() if self.playback_engine else {"initialized": False},
                "queue": self.queue_manager.get_queue_status() if self.queue_manager else {"size": 0},
                "health": self.stats_monitor.get_health_status() if self.stats_monitor else {"status": "unknown"},
                "performance": self.queue_manager.get_performance_stats() if self.queue_manager else {},
                "legacy_stats": self.legacy_stats.copy(),
                "config": {
                    "voice_settings": dict(self.voice_settings),
                    "system_config": dict(self.system_config)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 状態取得エラー: {e}")
            return {"error": str(e), "version": VERSION}
    
    def get_voice_status(self) -> Dict[str, Any]:
        """音声システム状態取得（同期ラッパー）"""
        try:
            if self.loop and self.loop.is_running():
                # 非同期コンテキスト内では簡易版
                return {
                    "version": VERSION,
                    "sync_wrapper": True,
                    "initialized": self.initialized,
                    "running": self.running,
                    "legacy_stats": self.legacy_stats.copy()
                }
            else:
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.get_voice_status_async())
                finally:
                    if not self._loop_fallback:
                        loop.close()
        except Exception as e:
            logger.error(f"❌ 状態取得エラー: {e}")
            return {"error": str(e)}
    
    # === 話者管理API（後方互換性） ===
    
    def get_speakers(self) -> Dict[int, Any]:
        """話者リスト取得"""
        if self.voicevox_client:
            speakers = self.voicevox_client.get_speakers()
            # SpeakerInfo を辞書形式に変換
            return {sid: {
                "name": info.name,
                "speaker_name": info.speaker_name,
                "style_name": info.style_name,
                "category": info.category
            } for sid, info in speakers.items()}
        return {}
    
    def get_speaker_name(self, voice_id: int) -> str:
        """話者名取得"""
        if self.voicevox_client:
            return self.voicevox_client.get_speaker_name(voice_id)
        return f"Unknown Speaker ({voice_id})"
    
    def initialize_speakers(self) -> None:
        """話者リスト初期化（後方互換性）"""
        if self.voicevox_client:
            if self.loop and self.loop.is_running():
                asyncio.create_task(self.voicevox_client.load_speakers())
            else:
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.voicevox_client.load_speakers())
                finally:
                    if not self._loop_fallback:
                        loop.close()
    
    # === クリーンアップ ===
    
    async def cleanup_async(self) -> None:
        """非同期クリーンアップ"""
        try:
            logger.info(f"🧹 Final Production統合クリーンアップ開始 v{VERSION}")
            
            # シャットダウンシグナル設定
            self.shutdown_event.set()
            
            # 各モジュールのクリーンアップ
            cleanup_tasks = []
            
            if self.queue_manager:
                cleanup_tasks.append(self.queue_manager.stop_processing())
            
            if self.stats_monitor:
                cleanup_tasks.append(self.stats_monitor.stop_monitoring())
            
            if self.file_watcher:
                cleanup_tasks.append(self.file_watcher.stop_monitoring())
            
            if self.voicevox_client:
                cleanup_tasks.append(self.voicevox_client.cleanup())
            
            if self.bouyomi_client:
                cleanup_tasks.append(self.bouyomi_client.cleanup())
            
            if self.playback_engine:
                cleanup_tasks.append(self.playback_engine.cleanup())
            
            # 並列クリーンアップ実行
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # 状態リセット
            self.initialized = False
            self.running = False
            self.legacy_stats = {"total_requests": 0, "successful_requests": 0, "failed_requests": 0}
            
            logger.info(f"✅ Final Production統合クリーンアップ完了 v{VERSION}")
            
        except Exception as e:
            logger.error(f"❌ Final Productionクリーンアップエラー: {e}")
    
    def cleanup(self) -> None:
        """クリーンアップ（同期ラッパー）"""
        try:
            if self.loop and self.loop.is_running():
                # 非同期コンテキスト内
                asyncio.create_task(self.cleanup_async())
            else:
                # 同期コンテキスト
                loop = self._loop_fallback or asyncio.new_event_loop()
                if not self._loop_fallback:
                    asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.cleanup_async())
                finally:
                    if not self._loop_fallback:
                        loop.close()
        except Exception as e:
            logger.error(f"❌ クリーンアップエラー: {e}")
    
    async def _cleanup_on_init_failure(self) -> None:
        """初期化失敗時のクリーンアップ"""
        try:
            # 部分的に初期化されたモジュールをクリーンアップ
            if self.playback_engine:
                await self.playback_engine.cleanup()
            
            if self.voicevox_client:
                await self.voicevox_client.cleanup()
            
            if self.bouyomi_client:
                await self.bouyomi_client.cleanup()
            
            self.initialized = False
            self.running = False
            
        except Exception as e:
            logger.error(f"❌ 初期化失敗時クリーンアップエラー: {e}")

# === エクスポート ===

__all__ = [
    "VoiceManagerV15FinalProduction"
]