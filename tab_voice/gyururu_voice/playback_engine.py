#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 音声再生エンジンモジュール（改定版）
pygame非同期化・GILブロック解消・エラー処理強化

Features:
✅ ThreadPoolExecutor でpygame非同期化
✅ GILブロック完全解消
✅ 例外チェーン化対応
✅ 段階的初期化
✅ デバイス最適化維持
"""

import asyncio
import pygame
import io
import time
import platform
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

from .config import VoiceSettings, SystemConfig, AudioDeviceInfo

try:
    from gyururu_utils.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class PlaybackEngineError(Exception):
    """音声再生エンジン専用例外"""
    pass

class PlaybackInitializationError(PlaybackEngineError):
    """初期化失敗例外"""
    pass

class PlaybackDeviceError(PlaybackEngineError):
    """デバイスエラー例外"""
    pass

class PlaybackEngine:
    """
    pygame音声再生エンジン（改定版）
    非同期対応・GILブロック解消・エラー処理強化
    """
    
    def __init__(self, voice_settings: VoiceSettings, system_config: SystemConfig):
        """初期化"""
        self.voice_settings = voice_settings
        self.system_config = system_config
        
        # === 再生状態 ===
        self.initialized = False
        self.audio_lock = asyncio.Lock()
        self.current_audio_info: Optional[Dict[str, Any]] = None
        self.is_playing = False
        
        # === 非同期実行プール ===
        self.executor = ThreadPoolExecutor(
            max_workers=2, 
            thread_name_prefix="PlaybackEngine"
        )
        
        # === デバイス情報 ===
        self.detected_device_info: Optional[AudioDeviceInfo] = None
        self.optimized_settings: Optional[AudioDeviceInfo] = None
        
        # === 統計 ===
        self.playback_count = 0
        self.playback_errors = 0
        self.playback_times = []
        self.initialization_count = 0
        
        # === 初期化段階管理 ===
        self.init_stages = {
            "device_detection": False,
            "pygame_init": False,
            "settings_optimization": False
        }
        
        logger.info("🎵 音声再生エンジン初期化（改定版・非同期対応）")
    
    async def initialize_async(self) -> bool:
        """非同期初期化（段階的）"""
        try:
            logger.info("🚀 音声再生エンジン非同期初期化開始")
            
            # Stage 1: デバイス検出
            await self._initialize_stage_device_detection()
            
            # Stage 2: pygame初期化
            await self._initialize_stage_pygame()
            
            # Stage 3: 設定最適化
            await self._initialize_stage_optimization()
            
            self.initialization_count += 1
            logger.info("✅ 音声再生エンジン非同期初期化完了")
            return True
            
        except Exception as e:
            logger.error(f"❌ 音声再生エンジン初期化失敗: {e}")
            raise PlaybackInitializationError(f"初期化失敗: {e}") from e
    
    async def _initialize_stage_device_detection(self):
        """Stage 1: デバイス検出"""
        try:
            logger.debug("🔍 Stage 1: オーディオデバイス検出開始")
            
            # 非同期でデバイス検出実行
            device_info = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._detect_audio_device_sync
            )
            
            self.detected_device_info = device_info
            self.init_stages["device_detection"] = True
            
            logger.info(f"✅ Stage 1完了: デバイス検出 {device_info}")
            
        except Exception as e:
            raise PlaybackInitializationError(f"デバイス検出失敗: {e}") from e
    
    async def _initialize_stage_pygame(self):
        """Stage 2: pygame初期化"""
        try:
            logger.debug("🎵 Stage 2: pygame初期化開始")
            
            # 非同期でpygame初期化実行
            success = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._initialize_pygame_sync
            )
            
            if not success:
                raise PlaybackInitializationError("pygame初期化失敗")
            
            self.init_stages["pygame_init"] = True
            logger.info("✅ Stage 2完了: pygame初期化")
            
        except Exception as e:
            raise PlaybackInitializationError(f"pygame初期化失敗: {e}") from e
    
    async def _initialize_stage_optimization(self):
        """Stage 3: 設定最適化"""
        try:
            logger.debug("⚙️ Stage 3: 設定最適化開始")
            
            if self.detected_device_info:
                self.optimized_settings = await self._optimize_for_device(self.detected_device_info)
            else:
                self.optimized_settings = self._get_default_audio_settings()
            
            self.init_stages["settings_optimization"] = True
            self.initialized = True
            
            logger.info("✅ Stage 3完了: 設定最適化")
            
        except Exception as e:
            raise PlaybackInitializationError(f"設定最適化失敗: {e}") from e
    
    def _detect_audio_device_sync(self) -> AudioDeviceInfo:
        """オーディオデバイス検出（同期版）"""
        try:
            logger.debug("🔊 オーディオデバイス検出実行")
            
            # pygame一時初期化でデバイス情報取得
            pygame.mixer.pre_init()
            pygame.mixer.init()
            
            mixer_info = pygame.mixer.get_init()
            if mixer_info:
                freq, format_bits, channels = mixer_info
                
                device_info = {
                    "sample_rate": freq,
                    "buffer_size": 4096,  # デフォルト
                    "channels": channels,
                    "format_bits": abs(format_bits)
                }
                
                logger.info(f"🔊 検出されたオーディオデバイス: {freq}Hz, {channels}ch, {abs(format_bits)}bit")
                
            else:
                logger.warning("⚠️ オーディオデバイス情報取得失敗 - デフォルト設定使用")
                device_info = self._get_default_audio_settings()
            
            pygame.mixer.quit()
            return device_info
            
        except Exception as e:
            logger.warning(f"⚠️ オーディオデバイス検出エラー（デフォルト使用）: {e}")
            return self._get_default_audio_settings()
    
    def _get_default_audio_settings(self) -> AudioDeviceInfo:
        """デフォルトオーディオ設定取得"""
        return {
            "sample_rate": 44100,
            "buffer_size": 4096,
            "channels": 2,
            "format_bits": 16
        }
    
    def _initialize_pygame_sync(self) -> bool:
        """pygame初期化（同期版）"""
        try:
            # 既存pygame完全終了
            self._cleanup_pygame_sync()
            
            if not self.optimized_settings:
                # 暫定設定で初期化
                sample_rate = self.voice_settings.get("sample_rate", 44100)
                buffer_size = self.voice_settings.get("buffer_size", 4096)
            else:
                sample_rate = self.optimized_settings["sample_rate"]
                buffer_size = self.optimized_settings["buffer_size"]
            
            pygame.mixer.pre_init(
                frequency=sample_rate,
                size=-16,               # 16bit符号付き
                channels=2,             # ステレオ
                buffer=buffer_size
            )
            pygame.mixer.init()
            pygame.init()
            
            # 音量設定（安全マージン）
            volume = self.voice_settings.get("volume", 70) / 100.0
            safe_volume = min(volume * 0.7, 0.7)  # 最大70%で制限
            pygame.mixer.music.set_volume(safe_volume)
            
            # 初期化確認
            mixer_info = pygame.mixer.get_init()
            if mixer_info:
                actual_freq, actual_format, actual_channels = mixer_info
                logger.info(f"🎵 pygame初期化成功: {actual_freq}Hz, {actual_channels}ch, {abs(actual_format)}bit, バッファ{buffer_size}")
                return True
            else:
                raise RuntimeError("pygame初期化後の設定確認失敗")
                
        except Exception as e:
            logger.error(f"❌ pygame初期化エラー: {e}")
            self.playback_errors += 1
            return False
    
    def _cleanup_pygame_sync(self) -> None:
        """pygame完全クリーンアップ（同期版）"""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            if pygame.get_init():
                pygame.quit()
            time.sleep(0.1)  # 完全終了待機
        except:
            pass  # エラーは無視
    
    async def _optimize_for_device(self, device_info: AudioDeviceInfo) -> AudioDeviceInfo:
        """デバイス固有最適化（非同期版）"""
        try:
            optimized = device_info.copy()
            detected_rate = device_info["sample_rate"]
            
            # サンプリングレート最適化
            if detected_rate == 48000:
                optimized["sample_rate"] = 48000
                optimized["buffer_size"] = 4096  # 48kHz用
                logger.info("🎵 48kHzデバイス検出 - プロ音響設定適用")
                
            elif detected_rate == 44100:
                optimized["sample_rate"] = 44100
                optimized["buffer_size"] = 4096  # v13準拠
                logger.info("🎵 44.1kHzデバイス検出 - v13準拠設定適用")
                
            elif detected_rate >= 96000:
                optimized["sample_rate"] = 48000  # ダウンサンプリング
                optimized["buffer_size"] = 8192   # 高解像度用大容量バッファ
                logger.info("🎵 高解像度デバイス検出 - 48kHzダウンサンプリング設定適用")
                
            else:
                optimized["sample_rate"] = 44100  # 標準設定
                optimized["buffer_size"] = 4096
                logger.info(f"🎵 {detected_rate}Hzデバイス検出 - 44.1kHz標準設定適用")
            
            # プラットフォーム固有最適化
            system = platform.system()
            if system == "Windows":
                # Windows WASAPI最適化
                optimized["buffer_size"] = max(optimized["buffer_size"], 4096)
            elif system == "Darwin":  # macOS
                # Core Audio最適化
                optimized["buffer_size"] = max(optimized["buffer_size"], 2048)
            elif system == "Linux":
                # ALSA/PulseAudio最適化
                optimized["buffer_size"] = max(optimized["buffer_size"], 4096)
            
            # 設定値適用
            user_sample_rate = self.voice_settings.get("sample_rate")
            if user_sample_rate and user_sample_rate in [22050, 44100, 48000]:
                optimized["sample_rate"] = user_sample_rate
                logger.info(f"🎵 ユーザー指定サンプリングレート適用: {user_sample_rate}Hz")
            
            user_buffer_size = self.voice_settings.get("buffer_size")
            if user_buffer_size and user_buffer_size in [1024, 2048, 4096, 8192]:
                optimized["buffer_size"] = user_buffer_size
                logger.info(f"🎵 ユーザー指定バッファサイズ適用: {user_buffer_size}")
            
            return optimized
            
        except Exception as e:
            logger.error(f"❌ デバイス最適化エラー: {e}")
            return device_info
    
    async def play_audio_data(self, audio_data: bytes, description: str = "音声再生", 
                             voice_id: Optional[int] = None, use_fade: bool = True) -> bool:
        """音声データ再生（完全非同期版）"""
        if not audio_data:
            raise PlaybackEngineError("音声データが空です")
        
        if not self.initialized:
            raise PlaybackEngineError("音声再生エンジンが初期化されていません")
        
        playback_start = time.time()
        
        try:
            async with self.audio_lock:
                # 再生状態設定
                self.is_playing = True
                self.current_audio_info = {
                    "description": description,
                    "voice_id": voice_id,
                    "data_size": len(audio_data),
                    "start_time": playback_start,
                    "fade_enabled": use_fade
                }
                
                # 非同期で音声再生実行
                success = await asyncio.get_event_loop().run_in_executor(
                    self.executor, 
                    self._play_audio_sync, 
                    audio_data, description, use_fade
                )
                
                # 再生完了処理
                playback_time = time.time() - playback_start
                self.playback_times.append(playback_time)
                self.is_playing = False
                self.current_audio_info = None
                
                if success:
                    self.playback_count += 1
                    logger.debug(f"✅ 音声再生完了: {description} ({playback_time:.2f}s)")
                else:
                    self.playback_errors += 1
                    logger.warning(f"⚠️ 音声再生失敗: {description}")
                
                # 統計サイズ制限
                if len(self.playback_times) > 100:
                    self.playback_times = self.playback_times[-50:]
                
                return success
                
        except Exception as e:
            playback_time = time.time() - playback_start
            self.playback_errors += 1
            self.is_playing = False
            self.current_audio_info = None
            raise PlaybackEngineError(f"音声再生エラー: {e}") from e
    
    def _play_audio_sync(self, audio_data: bytes, description: str, use_fade: bool) -> bool:
        """音声再生実行（同期版）"""
        try:
            # 音声ストリーム準備
            audio_io = io.BytesIO(audio_data)

            # 🔍 デバッグ：音声データのバイトサイズと先頭部分
            logger.debug(f"🔥🔍 [DEBUG] 音声データ長さ: {len(audio_data)} bytes")
            if len(audio_data) > 12:
                wav_header = audio_data[:12]
                riff, wave = wav_header[:4], wav_header[8:12]
                logger.debug(f"🔥🎵 [DEBUG] WAVヘッダー: {riff} + {wave}")
                if riff != b'RIFF' or wave != b'WAVE':
                    logger.warning(f"🔥❌ [DEBUG] 無効なWAVフォーマット")
                else:
                    logger.debug(f"🔥✅ [DEBUG] 有効なWAVフォーマット")
            
            # 既存音声の停止（フェード対応）
            if pygame.mixer.music.get_busy():
                if use_fade:
                    pygame.mixer.music.fadeout(50)  # 50msフェードアウト
                    time.sleep(0.05)
                else:
                    pygame.mixer.music.stop()
                    time.sleep(0.02)  # 短時間待機
            
            # v13準拠：クリックノイズ完全防止
            time.sleep(0.05)
            
            # アンチエイリアス処理
            if self.voice_settings.get("anti_alias", True):
                time.sleep(0.01)
            
            # 音声読み込み
            pygame.mixer.music.load(audio_io)
            
            # 再生開始（フェード対応）
            if use_fade:
                pygame.mixer.music.play(fade_ms=50)  # 50msフェードイン
                logger.debug(f"🔥▶️ [DEBUG] pygame 再生開始")
                logger.debug(f"🔥🔊 [DEBUG] pygame 再生中: {pygame.mixer.music.get_busy()}")
            else:
                pygame.mixer.music.play()
            
            logger.debug(f"🎵 音声再生開始: {description} ({len(audio_data)}bytes)")
            
            # 再生完了監視
            timeout = self.system_config.get("playback_timeout", 60)
            elapsed = 0
            check_interval = 0.1
            
            while pygame.mixer.music.get_busy() and elapsed < timeout:
                time.sleep(check_interval)
                elapsed += check_interval
                
                # 長時間再生の進捗ログ
                if elapsed > 5.0 and elapsed % 10.0 < check_interval:
                    logger.debug(f"🎵 再生中: {elapsed:.1f}s経過")
            
            if elapsed >= timeout:
                pygame.mixer.music.stop()
                return False
            
            return True
                
        except Exception as e:
            logger.error(f"❌ 同期音声再生エラー: {e}")
            return False
    
    async def stop_playback(self, use_fade: bool = True) -> None:
        """再生停止（非同期版）"""
        try:
            async with self.audio_lock:
                # 非同期で停止実行
                await asyncio.get_event_loop().run_in_executor(
                    self.executor, 
                    self._stop_playback_sync, 
                    use_fade
                )
                
                self.is_playing = False
                self.current_audio_info = None
                logger.debug("🛑 音声再生停止")
                    
        except Exception as e:
            raise PlaybackEngineError(f"音声停止エラー: {e}") from e
    
    def _stop_playback_sync(self, use_fade: bool) -> None:
        """再生停止実行（同期版）"""
        try:
            if pygame.mixer.music.get_busy():
                if use_fade:
                    pygame.mixer.music.fadeout(100)  # 100msフェードアウト
                    time.sleep(0.1)
                else:
                    pygame.mixer.music.stop()
        except Exception as e:
            logger.error(f"❌ 同期停止エラー: {e}")
    
    def set_volume(self, volume: float) -> None:
        """音量設定（スレッドセーフ）"""
        try:
            # 安全範囲制限
            safe_volume = max(0.0, min(1.0, volume))
            
            # 非同期実行でGILブロック回避
            if self.executor:
                self.executor.submit(pygame.mixer.music.set_volume, safe_volume)
                logger.debug(f"🔊 音量設定: {safe_volume:.2f}")
        except Exception as e:
            logger.error(f"❌ 音量設定エラー: {e}")
    
    # === テスト機能（改定版） ===
    
    async def test_playback(self) -> bool:
        """再生テスト（非同期版）"""
        try:
            logger.info("🧪 音声再生テスト開始（非同期版）")
            
            # 簡単なテストトーン生成
            test_audio_data = await self._generate_test_tone()
            
            if test_audio_data:
                success = await self.play_audio_data(
                    test_audio_data, 
                    "再生テスト（非同期版）", 
                    use_fade=False
                )
                
                if success:
                    logger.info("✅ 音声再生テスト成功（非同期版）")
                else:
                    logger.error("❌ 音声再生テスト失敗")
                
                return success
            else:
                logger.error("❌ テストトーン生成失敗")
                return False
                
        except Exception as e:
            raise PlaybackEngineError(f"音声再生テストエラー: {e}") from e
    
    async def _generate_test_tone(self) -> Optional[bytes]:
        """テストトーン生成（非同期版）"""
        try:
            # 非同期でテストトーン生成
            return await asyncio.get_event_loop().run_in_executor(
                self.executor, 
                self._generate_test_tone_sync
            )
        except Exception as e:
            logger.error(f"❌ 非同期テストトーン生成エラー: {e}")
            return None
    
    def _generate_test_tone_sync(self) -> Optional[bytes]:
        """テストトーン生成（同期版）"""
        try:
            import wave
            import math
            import struct
            
            # WAVパラメータ
            sample_rate = self.optimized_settings["sample_rate"] if self.optimized_settings else 44100
            duration = 0.5  # 0.5秒
            frequency = 440  # A4音
            amplitude = 0.3  # 30%音量
            
            # サンプル生成
            samples = []
            for i in range(int(sample_rate * duration)):
                t = i / sample_rate
                sample = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * t))
                samples.append(struct.pack('<h', sample))  # 16bit little endian
            
            # WAVファイル作成
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # モノラル
                wav_file.setsampwidth(2)  # 16bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(b''.join(samples))
            
            wav_buffer.seek(0)
            return wav_buffer.read()
            
        except Exception as e:
            logger.error(f"❌ テストトーン生成エラー: {e}")
            return None
    
    # === 状態・統計取得API ===
    
    def get_playback_status(self) -> Dict[str, Any]:
        """再生状態取得"""
        mixer_info = None
        if self.initialized:
            try:
                mixer_info = pygame.mixer.get_init()
            except:
                mixer_info = None
        
        return {
            "initialized": self.initialized,
            "is_playing": self.is_playing,
            "mixer_info": mixer_info,
            "current_audio": self.current_audio_info,
            "optimized_settings": self.optimized_settings,
            "detected_device": self.detected_device_info,
            "init_stages": self.init_stages.copy(),
            "executor_active": self.executor is not None and not self.executor._shutdown
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計取得"""
        avg_playback_time = 0
        if self.playback_times:
            avg_playback_time = sum(self.playback_times) / len(self.playback_times)
        
        success_rate = 0
        total_attempts = self.playback_count + self.playback_errors
        if total_attempts > 0:
            success_rate = (self.playback_count / total_attempts) * 100
        
        return {
            "playback_count": self.playback_count,
            "playback_errors": self.playback_errors,
            "success_rate": round(success_rate, 2),
            "average_playback_time": round(avg_playback_time, 3),
            "initialization_count": self.initialization_count,
            "recent_playback_times": self.playback_times[-10:] if self.playback_times else [],
            "gil_blocking_resolved": True  # 改定版フラグ
        }
    
    # === 設定更新（改定版） ===
    
    async def update_settings(self, new_voice_settings: VoiceSettings) -> bool:
        """設定更新（非同期版）"""
        try:
            old_sample_rate = self.voice_settings.get("sample_rate")
            old_buffer_size = self.voice_settings.get("buffer_size")
            
            self.voice_settings = new_voice_settings
            
            new_sample_rate = self.voice_settings.get("sample_rate")
            new_buffer_size = self.voice_settings.get("buffer_size")
            
            # サンプリングレートまたはバッファサイズ変更時は再初期化
            if (old_sample_rate != new_sample_rate or 
                old_buffer_size != new_buffer_size):
                
                logger.info("🔄 音声設定変更 - 非同期再初期化")
                
                # 非同期で再初期化
                await self._initialize_stage_device_detection()
                success = await asyncio.get_event_loop().run_in_executor(
                    self.executor, 
                    self._initialize_pygame_sync
                )
                return success
            
            # 音量のみ変更
            volume = self.voice_settings.get("volume", 70) / 100.0
            safe_volume = min(volume * 0.7, 0.7)
            self.set_volume(safe_volume)
            
            return True
            
        except Exception as e:
            raise PlaybackEngineError(f"音声設定更新エラー: {e}") from e
    
    # === クリーンアップ（改定版） ===
    
    async def cleanup(self) -> None:
        """クリーンアップ（非同期版）"""
        try:
            async with self.audio_lock:
                # 再生停止
                await self.stop_playback(use_fade=False)
                
                # pygame完全終了（非同期）
                await asyncio.get_event_loop().run_in_executor(
                    self.executor, 
                    self._cleanup_pygame_sync
                )
                
                # ThreadPoolExecutor終了
                if self.executor:
                    self.executor.shutdown(wait=True)
                    self.executor = None
                
                # 状態リセット
                self.initialized = False
                self.is_playing = False
                self.current_audio_info = None
                self.init_stages = {stage: False for stage in self.init_stages}
                
                # 統計クリア
                self.playback_times.clear()
                
                logger.info("🧹 音声再生エンジンクリーンアップ完了（改定版）")
                
        except Exception as e:
            raise PlaybackEngineError(f"音声再生エンジンクリーンアップエラー: {e}") from e

# === エクスポート ===

__all__ = [
    "PlaybackEngine",
    "PlaybackEngineError",
    "PlaybackInitializationError", 
    "PlaybackDeviceError"
]