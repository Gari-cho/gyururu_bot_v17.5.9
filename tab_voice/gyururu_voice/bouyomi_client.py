#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 棒読みちゃんクライアントモジュール
TCP/HTTP両対応・自動フォールバック・定期再試行

Features:
✅ TCP/HTTP両方式対応
✅ 自動最適接続方式選択
✅ フォールバック機能
✅ 定期再試行スケジューラー
✅ 接続状態監視
"""

import asyncio
import aiohttp
import socket
import struct
import time
from typing import Optional, Literal, Dict, Any

from .config import VoiceSettings, SystemConfig, BouyomiConfig

try:
    from gyururu_utils.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class BouyomiClient:
    """
    棒読みちゃん非同期クライアント
    TCP/HTTP両対応・自動フォールバック・定期再試行
    """
    
    def __init__(self, voice_settings: VoiceSettings, system_config: SystemConfig, 
                 bouyomi_config: BouyomiConfig):
        """初期化"""
        self.voice_settings = voice_settings
        self.system_config = system_config
        self.config = bouyomi_config.copy()
        
        # === 接続状態 ===
        self.tcp_available = False
        self.http_available = False
        self.preferred_method: Optional[Literal["tcp", "http"]] = None
        self.last_retry_time = 0
        
        # === 統計 ===
        self.tcp_send_count = 0
        self.http_send_count = 0
        self.tcp_errors = 0
        self.http_errors = 0
        self.last_success_time = 0
        
        # === 再試行管理 ===
        self.retry_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
        
        logger.info(f"📢 棒読みちゃんクライアント初期化: {self.config['host']}:{self.config['tcp_port']}")
    
    async def initialize_async(self) -> bool:
        """非同期初期化"""
        try:
            # 接続テスト・最適方式選択
            await self.check_optimal_connection()
            
            # 定期再試行スケジューラー開始
            await self.start_retry_scheduler()
            
            return self.preferred_method is not None
            
        except Exception as e:
            logger.error(f"❌ 棒読みちゃんクライアント初期化エラー: {e}")
            return False
    
    async def check_optimal_connection(self) -> None:
        """最適接続方式チェック"""
        try:
            current_time = time.time()
            retry_interval = self.system_config.get("bouyomi_retry_interval", 300)
            
            # 再試行間隔チェック
            if (current_time - self.last_retry_time) < retry_interval:
                return
            
            self.last_retry_time = current_time
            
            logger.debug("🔍 棒読みちゃん接続方式チェック開始")
            
            # TCP接続テスト
            self.tcp_available = await self._test_tcp_connection()
            
            # HTTP接続テスト
            self.http_available = await self._test_http_connection()
            
            # 最適方式決定
            if self.tcp_available:
                self.preferred_method = "tcp"
                logger.info("✅ 棒読みちゃん: TCP接続を優先使用")
            elif self.http_available:
                self.preferred_method = "http"
                logger.info("✅ 棒読みちゃん: HTTP接続を使用")
            else:
                self.preferred_method = None
                logger.debug("📢 棒読みちゃん接続不可")
            
            # 設定更新
            self.config.update({
                "tcp_available": self.tcp_available,
                "http_available": self.http_available,
                "preferred_method": self.preferred_method,
                "last_retry_time": current_time
            })
            
        except Exception as e:
            logger.error(f"❌ 棒読みちゃん接続チェックエラー: {e}")
    
    async def _test_tcp_connection(self) -> bool:
        """TCP接続テスト"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config["host"], self.config["tcp_port"]),
                timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            logger.debug("✅ 棒読みちゃんTCP接続テスト成功")
            return True
        except Exception as e:
            logger.debug(f"📢 棒読みちゃんTCP接続テスト失敗: {e}")
            return False
    
    async def _test_http_connection(self) -> bool:
        """HTTP接続テスト"""
        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"http://{self.config['host']}:{self.config['http_port']}/talk",
                    params={"text": ""},
                ) as response:
                    result = response.status == 200
                    if result:
                        logger.debug("✅ 棒読みちゃんHTTP接続テスト成功")
                    else:
                        logger.debug(f"📢 棒読みちゃんHTTP接続テスト失敗: HTTP {response.status}")
                    return result
        except Exception as e:
            logger.debug(f"📢 棒読みちゃんHTTP接続テスト失敗: {e}")
            return False
    
    async def send_text(self, text: str, voice_id: int = 0) -> bool:
        """テキスト送信（自動方式選択）"""
        if not text or not text.strip():
            logger.warning("⚠️ 棒読みちゃん: 送信テキストが空です")
            return False
        
        if not self.preferred_method:
            logger.debug("📢 棒読みちゃん接続不可のため送信スキップ")
            return False
        
        text = text.strip()
        success = False
        
        try:
            # 優先方式で送信
            if self.preferred_method == "tcp":
                success = await self._send_tcp(text, voice_id)
                if success:
                    self.tcp_send_count += 1
                else:
                    self.tcp_errors += 1
                    # TCP失敗時はHTTPフォールバック
                    if self.http_available:
                        logger.info("🔄 TCP失敗 - HTTPフォールバック")
                        success = await self._send_http(text, voice_id)
                        if success:
                            self.http_send_count += 1
                            self.preferred_method = "http"  # 方式切り替え
                        else:
                            self.http_errors += 1
            
            elif self.preferred_method == "http":
                success = await self._send_http(text, voice_id)
                if success:
                    self.http_send_count += 1
                else:
                    self.http_errors += 1
                    # HTTP失敗時はTCPフォールバック
                    if self.tcp_available:
                        logger.info("🔄 HTTP失敗 - TCPフォールバック")
                        success = await self._send_tcp(text, voice_id)
                        if success:
                            self.tcp_send_count += 1
                            self.preferred_method = "tcp"  # 方式切り替え
                        else:
                            self.tcp_errors += 1
            
            if success:
                self.last_success_time = time.time()
                logger.debug(f"📢 棒読みちゃん送信成功 ({self.preferred_method}): '{text[:30]}...'")
            else:
                # 両方失敗した場合は接続状態をリセット
                await self._handle_connection_failure()
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 棒読みちゃん送信エラー: {e}")
            return False
    
    async def _send_tcp(self, text: str, voice_id: int) -> bool:
        """TCP送信（棒読みちゃんプロトコル準拠）"""
        try:
            # パラメータ準備
            command = 0x0001  # 音声合成コマンド
            speed = min(max(int(self.voice_settings.get("speed", 100)), 50), 300)
            tone = min(max(int(self.voice_settings.get("pitch", 100)), 50), 200)
            volume = min(max(int(self.voice_settings.get("volume", 70)), 0), 100)
            voice = voice_id % 10  # 棒読みちゃんの音声範囲に調整
            
            # テキストエンコード
            text_bytes = text.encode('shift_jis', errors='ignore')
            text_length = len(text_bytes)
            
            # パケット構築
            packet = struct.pack('<HHHHHH', command, speed, tone, volume, voice, text_length)
            packet += text_bytes
            
            # 非同期TCP送信
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config["host"], self.config["tcp_port"]),
                timeout=5.0
            )
            
            writer.write(packet)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            
            return True
            
        except Exception as e:
            logger.debug(f"📢 棒読みちゃんTCP送信エラー: {e}")
            return False
    
    async def _send_http(self, text: str, voice_id: int) -> bool:
        """HTTP送信"""
        try:
            params = {
                "text": text,
                "voice": voice_id % 10,
                "volume": min(max(int(self.voice_settings.get("volume", 70)), 0), 100),
                "speed": min(max(int(self.voice_settings.get("speed", 100)), 50), 300),
                "tone": min(max(int(self.voice_settings.get("pitch", 100)), 50), 200)
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"http://{self.config['host']}:{self.config['http_port']}/talk",
                    params=params
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.debug(f"📢 棒読みちゃんHTTP送信エラー: {e}")
            return False
    
    async def _handle_connection_failure(self) -> None:
        """接続失敗処理"""
        # 接続状態リセット
        self.tcp_available = False
        self.http_available = False
        self.preferred_method = None
        
        # 設定更新
        self.config.update({
            "tcp_available": False,
            "http_available": False,
            "preferred_method": None
        })
        
        logger.warning("⚠️ 棒読みちゃん接続完全失敗 - 再試行スケジューラーで復旧予定")
    
    async def start_retry_scheduler(self) -> None:
        """再試行スケジューラー開始"""
        if self.retry_task and not self.retry_task.done():
            return
        
        self.retry_task = asyncio.create_task(
            self._retry_scheduler_loop(),
            name="bouyomi_retry_scheduler"
        )
        logger.info("⏰ 棒読みちゃん再試行スケジューラー開始")
    
    async def stop_retry_scheduler(self) -> None:
        """再試行スケジューラー停止"""
        if self.retry_task and not self.retry_task.done():
            self.retry_task.cancel()
            try:
                await self.retry_task
            except asyncio.CancelledError:
                pass
        logger.info("⏰ 棒読みちゃん再試行スケジューラー停止")
    
    async def _retry_scheduler_loop(self) -> None:
        """再試行スケジューラーループ"""
        logger.info("📢 棒読みちゃん再試行スケジューラーループ開始")
        
        while not self.shutdown_event.is_set():
            try:
                retry_interval = self.system_config.get("bouyomi_retry_interval", 300)
                await asyncio.sleep(retry_interval)
                
                # 接続不可の場合のみ再試行
                if not self.preferred_method:
                    logger.info("🔄 棒読みちゃん定期再試行実行")
                    await self.check_optimal_connection()
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"❌ 棒読みちゃん再試行スケジューラーエラー: {e}")
                await asyncio.sleep(30)
        
        logger.info("📢 棒読みちゃん再試行スケジューラーループ終了")
    
    # === テスト機能 ===
    
    async def test_connection(self) -> Dict[str, bool]:
        """接続テスト"""
        logger.info("🧪 棒読みちゃん接続テスト開始")
        
        tcp_result = await self._test_tcp_connection()
        http_result = await self._test_http_connection()
        
        results = {
            "tcp": tcp_result,
            "http": http_result,
            "any_available": tcp_result or http_result
        }
        
        logger.info(f"🧪 棒読みちゃん接続テスト結果: {results}")
        return results
    
    async def test_send(self, text: str = "棒読みちゃんテストです") -> bool:
        """送信テスト"""
        logger.info(f"🧪 棒読みちゃん送信テスト: '{text}'")
        
        result = await self.send_text(text, voice_id=0)
        
        if result:
            logger.info("✅ 棒読みちゃん送信テスト成功")
        else:
            logger.error("❌ 棒読みちゃん送信テスト失敗")
        
        return result
    
    # === 状態取得API ===
    
    def get_connection_status(self) -> Dict[str, Any]:
        """接続状態取得"""
        return {
            "tcp_available": self.tcp_available,
            "http_available": self.http_available,
            "preferred_method": self.preferred_method,
            "last_retry_time": self.last_retry_time,
            "last_success_time": self.last_success_time,
            "config": self.config.copy()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計取得"""
        total_sends = self.tcp_send_count + self.http_send_count
        total_errors = self.tcp_errors + self.http_errors
        
        success_rate = 0
        if (total_sends + total_errors) > 0:
            success_rate = (total_sends / (total_sends + total_errors)) * 100
        
        return {
            "tcp_sends": self.tcp_send_count,
            "http_sends": self.http_send_count,
            "tcp_errors": self.tcp_errors,
            "http_errors": self.http_errors,
            "total_sends": total_sends,
            "total_errors": total_errors,
            "success_rate": round(success_rate, 2),
            "preferred_method": self.preferred_method
        }
    
    def is_available(self) -> bool:
        """利用可能状態取得"""
        return self.preferred_method is not None
    
    # === 設定管理 ===
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """設定更新"""
        old_config = self.config.copy()
        self.config.update(new_config)
        
        # ホスト・ポート変更時は接続状態リセット
        if (old_config.get("host") != self.config.get("host") or
            old_config.get("tcp_port") != self.config.get("tcp_port") or
            old_config.get("http_port") != self.config.get("http_port")):
            
            logger.info("🔄 棒読みちゃん設定変更 - 接続状態リセット")
            self.tcp_available = False
            self.http_available = False
            self.preferred_method = None
            
            # 次回チェック時に再確認するため時間リセット
            self.last_retry_time = 0
    
    # === クリーンアップ ===
    
    async def cleanup(self) -> None:
        """クリーンアップ"""
        try:
            # シャットダウンシグナル設定
            self.shutdown_event.set()
            
            # 再試行スケジューラー停止
            await self.stop_retry_scheduler()
            
            # 接続状態リセット
            self.tcp_available = False
            self.http_available = False
            self.preferred_method = None
            
            logger.info("🧹 棒読みちゃんクライアントクリーンアップ完了")
            
        except Exception as e:
            logger.error(f"❌ 棒読みちゃんクリーンアップエラー: {e}")

# === エクスポート ===

__all__ = [
    "BouyomiClient"
]