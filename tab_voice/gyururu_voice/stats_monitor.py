#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 統計・ヘルス監視モジュール
パフォーマンス監視・自動修復・構造化ログ出力

Features:
✅ リアルタイムヘルス監視
✅ 自動修復システム
✅ 構造化ログ出力
✅ 日次統計管理
✅ エラー再通知システム
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Awaitable

from .config import SystemConfig, HealthStatus

try:
    from gyururu_utils.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class StatsMonitor:
    """
    統計・ヘルス監視システム
    パフォーマンス監視・自動修復・ログ出力を統合管理
    """
    
    def __init__(self, system_config: SystemConfig):
        """初期化"""
        self.system_config = system_config
        
        # === ヘルス監視 ===
        self.health_status: HealthStatus = "unknown"
        self.health_score = 0
        self.health_history = deque(maxlen=100)
        
        # === エラー管理 ===
        self.error_counts = defaultdict(int)
        self.error_last_notification = defaultdict(float)
        self.error_history = deque(maxlen=50)
        
        # === 統計データ ===
        self.daily_stats = defaultdict(int)
        self.last_daily_reset = datetime.now().date()
        self.performance_metrics = {
            "uptime_start": datetime.now(),
            "last_structured_log": datetime.now(),
            "total_health_checks": 0,
            "auto_repairs": 0,
            "log_outputs": 0
        }
        
        # === 監視タスク ===
        self.monitoring_active = False
        self.shutdown_event = asyncio.Event()
        self.health_task: Optional[asyncio.Task] = None
        self.logging_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.daily_reset_task: Optional[asyncio.Task] = None
        
        # === コールバック ===
        self.health_check_callback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None
        self.auto_repair_callback: Optional[Callable[[], Awaitable[None]]] = None
        
        logger.info("📊 統計・ヘルス監視システム初期化完了")
    
    def set_callbacks(self, health_check_callback: Callable[[], Awaitable[Dict[str, Any]]], 
                     auto_repair_callback: Callable[[], Awaitable[None]]) -> None:
        """コールバック設定"""
        self.health_check_callback = health_check_callback
        self.auto_repair_callback = auto_repair_callback
        logger.debug("🔗 監視コールバック設定完了")
    
    async def start_monitoring(self) -> None:
        """監視開始"""
        if self.monitoring_active:
            logger.warning("⚠️ 監視は既に開始されています")
            return
        
        if not self.health_check_callback or not self.auto_repair_callback:
            raise RuntimeError("監視コールバックが設定されていません")
        
        self.monitoring_active = True
        self.shutdown_event.clear()
        
        # 各監視タスク開始
        tasks = []
        
        # ヘルス監視
        self.health_task = asyncio.create_task(
            self._health_monitoring_loop(),
            name="health_monitor"
        )
        tasks.append(self.health_task)
        
        # 構造化ログ出力
        if self.system_config.get("log_structured_format", True):
            self.logging_task = asyncio.create_task(
                self._structured_logging_loop(),
                name="structured_logger"
            )
            tasks.append(self.logging_task)
        
        # 自動クリーンアップ
        self.cleanup_task = asyncio.create_task(
            self._auto_cleanup_loop(),
            name="auto_cleanup"
        )
        tasks.append(self.cleanup_task)
        
        # 日次統計リセット
        self.daily_reset_task = asyncio.create_task(
            self._daily_reset_loop(),
            name="daily_reset"
        )
        tasks.append(self.daily_reset_task)
        
        logger.info(f"🚀 統計・ヘルス監視開始: {len(tasks)}個のタスク")
    
    async def stop_monitoring(self) -> None:
        """監視停止"""
        if not self.monitoring_active:
            return
        
        logger.info("🛑 統計・ヘルス監視停止中...")
        
        # 停止シグナル送信
        self.shutdown_event.set()
        self.monitoring_active = False
        
        # タスク停止
        tasks_to_cancel = [
            self.health_task,
            self.logging_task,
            self.cleanup_task,
            self.daily_reset_task
        ]
        
        active_tasks = [task for task in tasks_to_cancel if task and not task.done()]
        
        if active_tasks:
            for task in active_tasks:
                task.cancel()
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*active_tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ 監視タスク停止タイムアウト")
        
        logger.info("✅ 統計・ヘルス監視停止完了")
    
    # === ヘルス監視ループ ===
    
    async def _health_monitoring_loop(self) -> None:
        """ヘルス監視ループ"""
        logger.info("🏥 ヘルス監視ループ開始")
        
        while not self.shutdown_event.is_set():
            try:
                interval = self.system_config.get("health_check_interval", 30)
                await asyncio.sleep(interval)
                
                await self._perform_health_check()
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await self._handle_error("health_monitoring", e)
                await asyncio.sleep(10)
        
        logger.info("🏥 ヘルス監視ループ終了")
    
    async def _perform_health_check(self) -> None:
        """ヘルスチェック実行"""
        try:
            # コールバックからシステム状態取得
            system_status = await self.health_check_callback()
            
            # ヘルススコア計算
            health_score = await self._calculate_health_score(system_status)
            
            # ヘルス状態更新
            old_status = self.health_status
            self.health_status = self._determine_health_status(health_score)
            self.health_score = health_score
            
            # 履歴記録
            self.health_history.append({
                "timestamp": datetime.now().isoformat(),
                "score": health_score,
                "status": self.health_status
            })
            
            # 統計更新
            self.performance_metrics["total_health_checks"] += 1
            self.daily_stats[f"health_check_{self.health_status}"] += 1
            
            # ステータス変化ログ
            if old_status != self.health_status:
                logger.info(f"🏥 ヘルス状態変化: {old_status} → {self.health_status} (スコア: {health_score})")
            
            # 自動修復判定
            poor_threshold = self.system_config.get("health_score_thresholds", {}).get("poor", 30)
            if health_score < poor_threshold:
                logger.warning(f"⚠️ ヘルス低下検出 (スコア: {health_score}) - 自動修復実行")
                await self._trigger_auto_repair()
            
        except Exception as e:
            await self._handle_error("health_check", e)
    
    async def _calculate_health_score(self, system_status: Dict[str, Any]) -> int:
        """ヘルススコア計算"""
        try:
            score = 0
            max_score = 100
            
            # pygame状態 (30点)
            pygame_status = system_status.get("pygame", {})
            if pygame_status.get("initialized", False):
                score += 30
            elif pygame_status.get("mixer_info"):
                score += 15
            
            # VOICEVOX接続 (25点)
            voicevox_status = system_status.get("voicevox", {})
            if voicevox_status.get("available", False):
                score += 25
            
            # キュー状態 (20点)
            queue_status = system_status.get("queue", {})
            queue_size = queue_status.get("size", 0)
            max_queue_size = queue_status.get("max_size", 100)
            if max_queue_size > 0:
                utilization = queue_size / max_queue_size
                if utilization < 0.8:
                    score += 20
                elif utilization < 0.9:
                    score += 15
                elif utilization < 1.0:
                    score += 10
            
            # タスク状態 (15点)
            tasks_status = system_status.get("tasks", {})
            running_tasks = tasks_status.get("running", 0)
            total_tasks = tasks_status.get("total", 0)
            if total_tasks > 0:
                task_health = min(15, running_tasks * 3)
                score += task_health
            
            # エラー率 (10点)
            performance = system_status.get("performance", {})
            total_requests = performance.get("total_requests", 0)
            if total_requests > 0:
                success_rate = performance.get("success_rate", 0)
                if success_rate >= 90:
                    score += 10
                elif success_rate >= 80:
                    score += 8
                elif success_rate >= 70:
                    score += 5
                elif success_rate >= 50:
                    score += 3
            else:
                score += 10  # リクエストがない場合は満点
            
            return min(score, max_score)
            
        except Exception as e:
            logger.error(f"❌ ヘルススコア計算エラー: {e}")
            return 0
    
    def _determine_health_status(self, score: int) -> HealthStatus:
        """ヘルス状態判定"""
        thresholds = self.system_config.get("health_score_thresholds", {})
        
        if score >= thresholds.get("excellent", 90):
            return "excellent"
        elif score >= thresholds.get("good", 70):
            return "good"
        elif score >= thresholds.get("fair", 50):
            return "fair"
        elif score >= thresholds.get("poor", 30):
            return "poor"
        else:
            return "critical"
    
    async def _trigger_auto_repair(self) -> None:
        """自動修復実行"""
        try:
            logger.info("🔧 自動修復開始")
            
            await self.auto_repair_callback()
            
            self.performance_metrics["auto_repairs"] += 1
            self.daily_stats["auto_repairs"] += 1
            
            logger.info("✅ 自動修復完了")
            
        except Exception as e:
            await self._handle_error("auto_repair", e)
    
    # === 構造化ログ出力ループ ===
    
    async def _structured_logging_loop(self) -> None:
        """構造化ログ出力ループ"""
        logger.info("📊 構造化ログ出力ループ開始")
        
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # 1分間隔
                
                if self.system_config.get("enable_performance_logging", True):
                    await self._output_structured_log()
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await self._handle_error("structured_logging", e)
                await asyncio.sleep(30)
        
        logger.info("📊 構造化ログ出力ループ終了")
    
    async def _output_structured_log(self) -> None:
        """構造化ログ出力実行"""
        try:
            now = datetime.now()
            uptime = now - self.performance_metrics["uptime_start"]
            
            # 統計データ収集
            log_data = {
                "timestamp": now.isoformat(),
                "component": "stats_monitor",
                "uptime_seconds": uptime.total_seconds(),
                "health": {
                    "status": self.health_status,
                    "score": self.health_score,
                    "total_checks": self.performance_metrics["total_health_checks"]
                },
                "errors": {
                    "total_types": len(self.error_counts),
                    "recent_errors": len([e for e in self.error_history if 
                                        (now - datetime.fromisoformat(e["timestamp"])).seconds < 3600])
                },
                "daily_stats": dict(self.daily_stats),
                "auto_repairs": self.performance_metrics["auto_repairs"]
            }
            
            logger.info(f"📊 STATS_MONITOR: {json.dumps(log_data, ensure_ascii=False)}")
            
            self.performance_metrics["log_outputs"] += 1
            self.performance_metrics["last_structured_log"] = now
            
        except Exception as e:
            await self._handle_error("structured_log_output", e)
    
    # === 自動クリーンアップループ ===
    
    async def _auto_cleanup_loop(self) -> None:
        """自動クリーンアップループ"""
        logger.info("🧹 自動クリーンアップループ開始")
        
        while not self.shutdown_event.is_set():
            try:
                interval = self.system_config.get("auto_cleanup_interval", 300)
                await asyncio.sleep(interval)
                
                await self._perform_cleanup()
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await self._handle_error("auto_cleanup", e)
                await asyncio.sleep(60)
        
        logger.info("🧹 自動クリーンアップループ終了")
    
    async def _perform_cleanup(self) -> None:
        """クリーンアップ実行"""
        try:
            current_time = time.time()
            retention_size = self.system_config.get("statistics_retention_size", 500)
            
            # ヘルス履歴制限
            if len(self.health_history) > retention_size // 5:  # 100件程度
                keep_size = retention_size // 10
                self.health_history = deque(
                    list(self.health_history)[-keep_size:],
                    maxlen=retention_size // 5
                )
            
            # エラー履歴制限
            if len(self.error_history) > 50:
                self.error_history = deque(
                    list(self.error_history)[-25:],
                    maxlen=50
                )
            
            # 古いエラー通知時間クリア（24時間以上前）
            old_keys = [
                key for key, timestamp in self.error_last_notification.items()
                if current_time - timestamp > 86400  # 24時間
            ]
            for key in old_keys:
                del self.error_last_notification[key]
            
            logger.debug("🧹 統計データクリーンアップ完了")
            
        except Exception as e:
            await self._handle_error("cleanup", e)
    
    # === 日次統計リセットループ ===
    
    async def _daily_reset_loop(self) -> None:
        """日次統計リセットループ"""
        logger.info("📅 日次統計管理ループ開始")
        
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(3600)  # 1時間ごとにチェック
                
                current_date = datetime.now().date()
                if current_date > self.last_daily_reset:
                    await self._reset_daily_stats(current_date)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await self._handle_error("daily_reset", e)
                await asyncio.sleep(300)
        
        logger.info("📅 日次統計管理ループ終了")
    
    async def _reset_daily_stats(self, new_date) -> None:
        """日次統計リセット"""
        try:
            logger.info(f"📊 日次統計リセット: {self.last_daily_reset} → {new_date}")
            
            # 前日統計をログ出力
            if self.daily_stats:
                daily_summary = {
                    "date": self.last_daily_reset.isoformat(),
                    "stats": dict(self.daily_stats)
                }
                logger.info(f"📊 DAILY_SUMMARY: {json.dumps(daily_summary, ensure_ascii=False)}")
            
            # 統計リセット
            self.daily_stats.clear()
            self.last_daily_reset = new_date
            
        except Exception as e:
            await self._handle_error("daily_reset", e)
    
    # === エラー管理 ===
    
    async def _handle_error(self, operation: str, error: Exception) -> None:
        """エラーハンドリング（再通知システム対応）"""
        self.error_counts[operation] += 1
        self.daily_stats[f"error_{operation}"] += 1
        
        current_time = time.time()
        error_count = self.error_counts[operation]
        notification_interval = self.system_config.get("error_notification_interval", 5)
        
        # エラー履歴記録
        self.error_history.append({
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "error": str(error),
            "count": error_count
        })
        
        error_msg = f"❌ {operation} エラー (#{error_count}): {error}"
        
        # 再通知システム
        if error_count <= 3:
            # 最初の3回は必ずログ出力
            logger.error(error_msg)
            self.error_last_notification[operation] = current_time
        elif error_count % notification_interval == 0:
            # N回目ごとに再通知
            logger.error(f"{error_msg} (再通知)")
            self.error_last_notification[operation] = current_time
        elif (current_time - self.error_last_notification.get(operation, 0)) > 300:
            # 5分経過後は再通知
            logger.warning(f"⚠️ {operation} 継続的エラー (#{error_count}) - 最新: {error}")
            self.error_last_notification[operation] = current_time
        # それ以外は抑制
    
    def record_error(self, operation: str, error: Exception) -> None:
        """外部からのエラー記録（同期）"""
        # 非同期コンテキスト内で使用する場合
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._handle_error(operation, error))
        except RuntimeError:
            # 同期コンテキストの場合は直接カウント更新のみ
            self.error_counts[operation] += 1
            self.daily_stats[f"error_{operation}"] += 1
            logger.error(f"❌ {operation} エラー: {error}")
    
    # === 統計・状態取得API ===
    
    def get_health_status(self) -> Dict[str, Any]:
        """ヘルス状態取得"""
        return {
            "status": self.health_status,
            "score": self.health_score,
            "total_checks": self.performance_metrics["total_health_checks"],
            "auto_repairs": self.performance_metrics["auto_repairs"],
            "recent_history": list(self.health_history)[-10:] if self.health_history else []
        }
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """エラー統計取得"""
        recent_errors = [
            e for e in self.error_history 
            if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 3600
        ]
        
        return {
            "error_counts": dict(self.error_counts),
            "total_error_types": len(self.error_counts),
            "recent_errors_1h": len(recent_errors),
            "error_history": list(self.error_history)[-10:] if self.error_history else []
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """パフォーマンスメトリクス取得"""
        uptime = datetime.now() - self.performance_metrics["uptime_start"]
        
        return {
            "uptime": str(uptime),
            "uptime_seconds": uptime.total_seconds(),
            "total_health_checks": self.performance_metrics["total_health_checks"],
            "auto_repairs": self.performance_metrics["auto_repairs"],
            "log_outputs": self.performance_metrics["log_outputs"],
            "last_structured_log": self.performance_metrics["last_structured_log"].isoformat(),
            "monitoring_active": self.monitoring_active
        }
    
    def get_daily_statistics(self) -> Dict[str, Any]:
        """日次統計取得"""
        return {
            "current_date": self.last_daily_reset.isoformat(),
            "stats": dict(self.daily_stats),
            "total_entries": len(self.daily_stats)
        }
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """包括的レポート取得"""
        return {
            "health": self.get_health_status(),
            "errors": self.get_error_statistics(),
            "performance": self.get_performance_metrics(),
            "daily_stats": self.get_daily_statistics(),
            "system_config": {
                "health_check_interval": self.system_config.get("health_check_interval", 30),
                "error_notification_interval": self.system_config.get("error_notification_interval", 5),
                "auto_cleanup_interval": self.system_config.get("auto_cleanup_interval", 300),
                "health_thresholds": self.system_config.get("health_score_thresholds", {})
            }
        }
    
    # === 手動操作API ===
    
    async def force_health_check(self) -> Dict[str, Any]:
        """手動ヘルスチェック実行"""
        try:
            logger.info("🔍 手動ヘルスチェック実行")
            await self._perform_health_check()
            return self.get_health_status()
        except Exception as e:
            await self._handle_error("manual_health_check", e)
            return {"error": str(e)}
    
    async def force_cleanup(self) -> bool:
        """手動クリーンアップ実行"""
        try:
            logger.info("🧹 手動クリーンアップ実行")
            await self._perform_cleanup()
            return True
        except Exception as e:
            await self._handle_error("manual_cleanup", e)
            return False
    
    def reset_error_counts(self) -> None:
        """エラーカウントリセット"""
        self.error_counts.clear()
        self.error_last_notification.clear()
        self.error_history.clear()
        logger.info("🔄 エラーカウントリセット完了")
    
    def reset_daily_stats(self) -> None:
        """日次統計手動リセット"""
        self.daily_stats.clear()
        self.last_daily_reset = datetime.now().date()
        logger.info("🔄 日次統計手動リセット完了")
    
    # === テスト・デバッグ機能 ===
    
    async def simulate_error(self, operation: str = "test_error") -> None:
        """エラーシミュレーション（テスト用）"""
        test_error = Exception("テスト用エラー")
        await self._handle_error(operation, test_error)
        logger.info(f"🧪 エラーシミュレーション実行: {operation}")
    
    def print_status_summary(self) -> None:
        """ステータスサマリー出力"""
        print("=" * 60)
        print("📊 統計・ヘルス監視システム サマリー")
        print("=" * 60)
        
        health = self.get_health_status()
        errors = self.get_error_statistics()
        performance = self.get_performance_metrics()
        
        print(f"ヘルス状態: {health['status']} (スコア: {health['score']})")
        print(f"監視状態: {'🟢 アクティブ' if self.monitoring_active else '🔴 停止'}")
        print(f"稼働時間: {performance['uptime']}")
        print(f"ヘルスチェック: {health['total_checks']}回")
        print(f"自動修復: {health['auto_repairs']}回")
        print(f"ログ出力: {performance['log_outputs']}回")
        print(f"エラー種類: {errors['total_error_types']}種類")
        print(f"直近1時間エラー: {errors['recent_errors_1h']}件")
        print()
        
        if self.daily_stats:
            print("日次統計:")
            for key, value in sorted(self.daily_stats.items()):
                print(f"  {key}: {value}")
        
        print("=" * 60)
    
    # === クリーンアップ ===
    
    async def cleanup(self) -> None:
        """クリーンアップ"""
        try:
            # 監視停止
            await self.stop_monitoring()
            
            # データクリア
            self.health_history.clear()
            self.error_counts.clear()
            self.error_last_notification.clear()
            self.error_history.clear()
            self.daily_stats.clear()
            
            # 状態リセット
            self.health_status = "shutdown"
            self.health_score = 0
            self.monitoring_active = False
            
            logger.info("🧹 統計・ヘルス監視システムクリーンアップ完了")
            
        except Exception as e:
            logger.error(f"❌ 統計・ヘルス監視クリーンアップエラー: {e}")

# === エクスポート ===

__all__ = [
    "StatsMonitor"
]