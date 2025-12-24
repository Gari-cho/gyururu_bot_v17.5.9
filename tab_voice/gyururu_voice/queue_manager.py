#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 音声キュー管理モジュール
優先度付きキュー・バックグラウンド処理・統計管理

Features:
✅ 5段階優先度システム (emergency/high/normal/low/background)
✅ 非同期優先度付きキュー
✅ キューオーバーフロー対策
✅ 統計・パフォーマンス監視
✅ 自動クリーンアップ
"""

import asyncio
import time
import weakref
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Awaitable

from .config import VoiceRequest, PriorityLevel, SystemConfig, AudioStats

try:
    from gyururu_utils.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class VoiceQueueManager:
    """
    音声キュー管理システム
    優先度付きキューとバックグラウンド処理を統合管理
    """
    
    def __init__(self, system_config: SystemConfig):
        """初期化"""
        self.system_config = system_config
        
        # === キューシステム ===
        self.voice_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.processing_active = False
        self.shutdown_event = asyncio.Event()
        
        # === 処理コールバック ===
        self.request_processor: Optional[Callable[[VoiceRequest], Awaitable[bool]]] = None
        
        # === 統計管理 ===
        self.stats = AudioStats()
        self.queue_stats = defaultdict(int)  # 優先度別統計
        self.processing_times = deque(maxlen=self.system_config.get("statistics_retention_size", 500))
        self.error_counts = defaultdict(int)
        
        # === パフォーマンス監視 ===
        self.last_cleanup_time = time.time()
        self.queue_size_history = deque(maxlen=100)
        self.processing_rate_history = deque(maxlen=50)
        
        # === タスク管理 ===
        self.processing_task: Optional[asyncio.Task] = None
        self.monitoring_task: Optional[asyncio.Task] = None
        
        logger.info("🎤 音声キュー管理システム初期化完了")
    
    def set_request_processor(self, processor: Callable[[VoiceRequest], Awaitable[bool]]) -> None:
        """音声リクエスト処理コールバック設定"""
        self.request_processor = processor
        logger.debug("🔗 音声リクエスト処理コールバック設定完了")
    
    async def start_processing(self) -> None:
        """キュー処理開始"""
        if self.processing_active:
            logger.warning("⚠️ キュー処理は既に開始されています")
            return
        
        if not self.request_processor:
            raise RuntimeError("音声リクエスト処理コールバックが設定されていません")
        
        self.processing_active = True
        self.shutdown_event.clear()
        
        # メイン処理タスク開始
        self.processing_task = asyncio.create_task(
            self._processing_loop(),
            name="voice_queue_processor"
        )
        
        # 監視タスク開始
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(),
            name="voice_queue_monitor"
        )
        
        logger.info("🚀 音声キュー処理開始")
    
    async def stop_processing(self) -> None:
        """キュー処理停止"""
        if not self.processing_active:
            return
        
        logger.info("🛑 音声キュー処理停止中...")
        
        # 停止シグナル送信
        self.shutdown_event.set()
        self.processing_active = False
        
        # タスク停止
        tasks_to_cancel = []
        if self.processing_task and not self.processing_task.done():
            tasks_to_cancel.append(self.processing_task)
        if self.monitoring_task and not self.monitoring_task.done():
            tasks_to_cancel.append(self.monitoring_task)
        
        if tasks_to_cancel:
            for task in tasks_to_cancel:
                task.cancel()
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ タスク停止タイムアウト")
        
        # キュークリア
        cleared_count = await self._clear_queue()
        
        logger.info(f"✅ 音声キュー処理停止完了 (残存{cleared_count}件クリア)")
    
    async def add_request(self, text: str, voice_id: Optional[int] = None, 
                         description: str = "音声合成", output_method: str = "voicevox",
                         priority: PriorityLevel = "normal") -> bool:
        """音声リクエスト追加"""
        try:
            # キューサイズチェック
            max_queue_size = self.system_config.get("max_queue_size", 100)
            if self.voice_queue.qsize() >= max_queue_size:
                logger.warning(f"⚠️ キューが満杯です ({self.voice_queue.qsize()}/{max_queue_size})")
                self.error_counts["queue_overflow"] += 1
                return False
            
            # 空テキストチェック
            if not text or not text.strip():
                logger.warning("⚠️ 音声テキストが空です")
                self.error_counts["empty_text"] += 1
                return False
            
            # リクエストデータ作成
            request_data = {
                "text": text.strip(),
                "voice_id": voice_id,
                "description": description,
                "output_method": output_method,
                "timestamp": datetime.now().isoformat(),
                "request_id": f"req_{int(time.time() * 1000)}_{id(text)}"
            }
            
            # 優先度付きリクエスト作成
            voice_request = VoiceRequest.create(priority, request_data)
            
            # キューに追加
            await self.voice_queue.put(voice_request)
            
            # 統計更新
            self.queue_stats[priority] += 1
            self.stats.total_requests += 1
            
            logger.debug(f"🎤 音声リクエスト追加: {description} (優先度:{priority}, キュー:{self.voice_queue.qsize()})")
            return True
            
        except Exception as e:
            logger.error(f"❌ 音声リクエスト追加エラー: {e}")
            self.error_counts["add_request"] += 1
            return False
    
    async def add_emergency_request(self, text: str, voice_id: Optional[int] = None, 
                                  description: str = "緊急音声") -> bool:
        """緊急音声リクエスト追加"""
        return await self.add_request(text, voice_id, description, priority="emergency")
    
    async def _processing_loop(self) -> None:
        """メイン処理ループ"""
        logger.info("🎤 音声キュー処理ループ開始")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while not self.shutdown_event.is_set():
            try:
                # キューから取得（タイムアウト付き）
                try:
                    voice_request = await asyncio.wait_for(
                        self.voice_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                if voice_request is None:  # 終了シグナル
                    break
                
                # 処理開始
                start_time = time.time()
                
                # コールバック実行
                try:
                    success = await self.request_processor(voice_request)
                except Exception as e:
                    logger.error(f"❌ 音声リクエスト処理エラー: {e}")
                    success = False
                
                # 処理時間記録
                processing_time = time.time() - start_time
                self.processing_times.append(processing_time)
                
                # 統計更新
                if success:
                    self.stats.successful_requests += 1
                    consecutive_errors = 0
                else:
                    self.stats.failed_requests += 1
                    consecutive_errors += 1
                    self.error_counts["processing_failed"] += 1
                
                # 平均処理時間更新
                if self.processing_times:
                    self.stats.average_processing_time = sum(self.processing_times) / len(self.processing_times)
                
                # 連続エラー対策
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(f"⚠️ 連続エラー{consecutive_errors}回 - 短時間休止")
                    await asyncio.sleep(2.0)
                    consecutive_errors = 0
                
                # タスク完了通知
                self.voice_queue.task_done()
                
            except asyncio.CancelledError:
                # キャンセル例外は再raise
                raise
            except Exception as e:
                logger.error(f"❌ 処理ループエラー: {e}")
                consecutive_errors += 1
                self.error_counts["processing_loop"] += 1
                await asyncio.sleep(0.5)
        
        logger.info("🎤 音声キュー処理ループ終了")
    
    async def _monitoring_loop(self) -> None:
        """監視ループ"""
        logger.info("📊 キュー監視ループ開始")
        
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # 30秒間隔
                
                # 現在のキューサイズ記録
                current_queue_size = self.voice_queue.qsize()
                self.queue_size_history.append(current_queue_size)
                
                # 処理レート計算
                if len(self.processing_times) >= 2:
                    recent_times = list(self.processing_times)[-10:]  # 最新10件
                    if recent_times:
                        avg_time = sum(recent_times) / len(recent_times)
                        processing_rate = 1.0 / avg_time if avg_time > 0 else 0
                        self.processing_rate_history.append(processing_rate)
                
                # 自動クリーンアップ
                current_time = time.time()
                cleanup_interval = self.system_config.get("auto_cleanup_interval", 300)
                if current_time - self.last_cleanup_time > cleanup_interval:
                    await self._auto_cleanup()
                    self.last_cleanup_time = current_time
                
                # 統計ログ出力
                if self.system_config.get("enable_performance_logging", True):
                    await self._log_performance_stats()
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"❌ 監視ループエラー: {e}")
                await asyncio.sleep(10)
        
        logger.info("📊 キュー監視ループ終了")
    
    async def _auto_cleanup(self) -> None:
        """自動クリーンアップ"""
        try:
            # 統計データサイズ制限
            retention_size = self.system_config.get("statistics_retention_size", 500)
            
            if len(self.processing_times) > retention_size:
                # 新しい半分を残す
                keep_size = retention_size // 2
                self.processing_times = deque(
                    list(self.processing_times)[-keep_size:], 
                    maxlen=retention_size
                )
            
            # 履歴データクリーンアップ
            if len(self.queue_size_history) > 100:
                self.queue_size_history = deque(
                    list(self.queue_size_history)[-50:], 
                    maxlen=100
                )
            
            if len(self.processing_rate_history) > 50:
                self.processing_rate_history = deque(
                    list(self.processing_rate_history)[-25:], 
                    maxlen=50
                )
            
            logger.debug("🧹 自動クリーンアップ完了")
            
        except Exception as e:
            logger.error(f"❌ 自動クリーンアップエラー: {e}")
    
    async def _log_performance_stats(self) -> None:
        """パフォーマンス統計ログ出力"""
        try:
            if not self.system_config.get("log_structured_format", True):
                return
            
            # 統計データ収集
            queue_size = self.voice_queue.qsize()
            avg_processing_time = self.stats.average_processing_time
            
            # 処理レート計算
            processing_rate = 0
            if self.processing_rate_history:
                processing_rate = sum(self.processing_rate_history) / len(self.processing_rate_history)
            
            # 成功率計算
            success_rate = 0
            if self.stats.total_requests > 0:
                success_rate = (self.stats.successful_requests / self.stats.total_requests) * 100
            
            stats_data = {
                "timestamp": datetime.now().isoformat(),
                "component": "voice_queue_manager",
                "queue": {
                    "current_size": queue_size,
                    "max_size": self.system_config.get("max_queue_size", 100),
                    "utilization_percent": (queue_size / self.system_config.get("max_queue_size", 100)) * 100
                },
                "performance": {
                    "total_requests": self.stats.total_requests,
                    "success_rate": round(success_rate, 2),
                    "avg_processing_time": round(avg_processing_time, 3),
                    "processing_rate_per_sec": round(processing_rate, 2)
                },
                "priority_stats": dict(self.queue_stats),
                "errors": dict(self.error_counts)
            }
            
            logger.info(f"📊 QUEUE_STATS: {stats_data}")
            
        except Exception as e:
            logger.error(f"❌ 統計ログ出力エラー: {e}")
    
    async def _clear_queue(self) -> int:
        """キュークリア"""
        cleared_count = 0
        while not self.voice_queue.empty() and cleared_count < 100:
            try:
                await asyncio.wait_for(self.voice_queue.get(), timeout=0.1)
                self.voice_queue.task_done()
                cleared_count += 1
            except asyncio.TimeoutError:
                break
        return cleared_count
    
    # === 状態取得API ===
    
    def get_queue_status(self) -> Dict[str, Any]:
        """キューステータス取得"""
        queue_size = self.voice_queue.qsize()
        max_size = self.system_config.get("max_queue_size", 100)
        
        return {
            "size": queue_size,
            "max_size": max_size,
            "utilization_percent": (queue_size / max_size) * 100 if max_size > 0 else 0,
            "processing_active": self.processing_active,
            "priority_stats": dict(self.queue_stats),
            "error_counts": dict(self.error_counts)
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """パフォーマンス統計取得"""
        # 処理レート計算
        processing_rate = 0
        if self.processing_rate_history:
            processing_rate = sum(self.processing_rate_history) / len(self.processing_rate_history)
        
        # 成功率計算
        success_rate = 0
        if self.stats.total_requests > 0:
            success_rate = (self.stats.successful_requests / self.stats.total_requests) * 100
        
        return {
            "total_requests": self.stats.total_requests,
            "successful_requests": self.stats.successful_requests,
            "failed_requests": self.stats.failed_requests,
            "success_rate": round(success_rate, 2),
            "average_processing_time": round(self.stats.average_processing_time, 3),
            "processing_rate_per_sec": round(processing_rate, 2),
            "queue_utilization_history": list(self.queue_size_history)[-10:] if self.queue_size_history else []
        }
    
    def get_detailed_stats(self) -> AudioStats:
        """詳細統計取得"""
        return self.stats
    
    # === ユーティリティメソッド ===
    
    def reset_stats(self) -> None:
        """統計リセット"""
        self.stats = AudioStats()
        self.queue_stats.clear()
        self.processing_times.clear()
        self.error_counts.clear()
        self.queue_size_history.clear()
        self.processing_rate_history.clear()
        logger.info("📊 統計データリセット完了")
    
    async def wait_queue_empty(self, timeout: float = 30.0) -> bool:
        """キューが空になるまで待機"""
        try:
            start_time = time.time()
            while not self.voice_queue.empty():
                if time.time() - start_time > timeout:
                    return False
                await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"❌ キュー待機エラー: {e}")
            return False
    
    def get_queue_size(self) -> int:
        """現在のキューサイズ取得"""
        return self.voice_queue.qsize()
    
    def is_processing_active(self) -> bool:
        """処理アクティブ状態取得"""
        return self.processing_active
    
    # === デバッグ・テスト用メソッド ===
    
    async def add_test_requests(self, count: int = 5) -> None:
        """テスト用リクエスト追加"""
        priorities = ["emergency", "high", "normal", "low", "background"]
        
        for i in range(count):
            priority = priorities[i % len(priorities)]
            await self.add_request(
                text=f"テストリクエスト{i+1}",
                description=f"テスト{i+1}({priority})",
                priority=priority
            )
        
        logger.info(f"🧪 テストリクエスト{count}件追加完了")
    
    def print_stats_summary(self) -> None:
        """統計サマリー出力"""
        queue_status = self.get_queue_status()
        perf_stats = self.get_performance_stats()
        
        print("=" * 60)
        print("🎤 音声キュー管理システム統計サマリー")
        print("=" * 60)
        print(f"キューサイズ: {queue_status['size']}/{queue_status['max_size']} ({queue_status['utilization_percent']:.1f}%)")
        print(f"処理状態: {'🟢 アクティブ' if queue_status['processing_active'] else '🔴 停止'}")
        print(f"総リクエスト: {perf_stats['total_requests']}")
        print(f"成功率: {perf_stats['success_rate']}%")
        print(f"平均処理時間: {perf_stats['average_processing_time']}秒")
        print(f"処理レート: {perf_stats['processing_rate_per_sec']}件/秒")
        print()
        print("優先度別統計:")
        for priority, count in queue_status['priority_stats'].items():
            print(f"  {priority}: {count}件")
        print()
        print("エラー統計:")
        for error_type, count in queue_status['error_counts'].items():
            print(f"  {error_type}: {count}件")
        print("=" * 60)

# === エクスポート ===

__all__ = [
    "VoiceQueueManager"
]