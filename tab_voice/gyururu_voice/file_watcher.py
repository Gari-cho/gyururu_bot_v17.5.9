#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 ファイル監視モジュール
設定ホットリロード・Watchdog/ポーリング両対応

Features:
✅ Watchdog ファイルシステム監視
✅ ポーリング監視フォールバック
✅ JSON設定ファイル監視
✅ 変更検出・自動リロード
✅ エラー耐性・自動復旧
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable

from .config import SystemConfig

# Watchdog の optional import
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

try:
    from gyururu_utils.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ConfigFileWatcher(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """
    設定ファイル監視ハンドラー（Watchdog用）
    """
    
    def __init__(self, reload_callback: Callable[[], Awaitable[None]], target_files: list):
        if WATCHDOG_AVAILABLE:
            super().__init__()
        self.reload_callback = reload_callback
        self.target_files = set(target_files)
        self.last_reload_time = 0
        self.reload_cooldown = 2.0  # 2秒間のクールダウン
    
    def on_modified(self, event):
        """ファイル変更イベント処理"""
        if event.is_directory:
            return
        
        file_name = os.path.basename(event.src_path)
        if file_name in self.target_files:
            current_time = time.time()
            if current_time - self.last_reload_time > self.reload_cooldown:
                logger.info(f"🔄 設定ファイル変更検出: {file_name}")
                self.last_reload_time = current_time
                
                # 非同期コールバック実行
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.reload_callback())
                except RuntimeError:
                    logger.warning("⚠️ イベントループ外からの変更検出 - リロードスキップ")

class FileWatcher:
    """
    ファイル監視システム
    Watchdog/ポーリング両対応・設定ホットリロード
    """
    
    def __init__(self, system_config: SystemConfig):
        """初期化"""
        self.system_config = system_config
        
        # === 監視設定 ===
        self.watch_enabled = self.system_config.get("config_hot_reload", True)
        self.use_watchdog = self.system_config.get("config_watchdog_enabled", True) and WATCHDOG_AVAILABLE
        
        # === 監視対象 ===
        self.watch_directories: Dict[str, Path] = {}
        self.watch_files: Dict[str, Path] = {}
        self.file_mtimes: Dict[str, float] = {}
        
        # === Watchdog監視 ===
        self.observer: Optional[Observer] = None
        self.event_handlers: Dict[str, ConfigFileWatcher] = {}
        
        # === ポーリング監視 ===
        self.polling_task: Optional[asyncio.Task] = None
        self.polling_interval = 5.0  # 5秒間隔
        self.shutdown_event = asyncio.Event()
        
        # === コールバック ===
        self.reload_callbacks: Dict[str, Callable[[], Awaitable[None]]] = {}
        
        # === 統計 ===
        self.watch_count = 0
        self.reload_count = 0
        self.error_count = 0
        
        monitoring_method = "Watchdog" if self.use_watchdog else "Polling"
        logger.info(f"📁 ファイル監視システム初期化完了 ({monitoring_method})")
    
    def add_config_file(self, config_name: str, file_path: Path, 
                       reload_callback: Callable[[], Awaitable[None]]) -> bool:
        """設定ファイル監視追加"""
        try:
            if not file_path.exists():
                logger.warning(f"⚠️ 監視対象ファイルが存在しません: {file_path}")
                return False
            
            # 監視対象登録
            self.watch_files[config_name] = file_path
            self.reload_callbacks[config_name] = reload_callback
            self.file_mtimes[config_name] = file_path.stat().st_mtime
            
            # ディレクトリ監視登録
            directory = file_path.parent
            if str(directory) not in self.watch_directories:
                self.watch_directories[str(directory)] = directory
            
            self.watch_count += 1
            logger.info(f"📁 設定ファイル監視追加: {config_name} -> {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 設定ファイル監視追加エラー ({config_name}): {e}")
            self.error_count += 1
            return False
    
    async def start_monitoring(self) -> bool:
        """監視開始"""
        if not self.watch_enabled:
            logger.info("📁 ファイル監視は無効に設定されています")
            return True
        
        if not self.watch_files:
            logger.warning("⚠️ 監視対象ファイルが登録されていません")
            return False
        
        success = False
        
        try:
            if self.use_watchdog:
                success = await self._start_watchdog_monitoring()
                if not success:
                    logger.warning("⚠️ Watchdog監視開始失敗 - ポーリング監視にフォールバック")
                    success = await self._start_polling_monitoring()
            else:
                success = await self._start_polling_monitoring()
            
            if success:
                self.shutdown_event.clear()
                logger.info(f"🚀 ファイル監視開始成功 ({'Watchdog' if self.use_watchdog and self.observer else 'Polling'})")
            else:
                logger.error("❌ ファイル監視開始失敗")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ ファイル監視開始エラー: {e}")
            self.error_count += 1
            return False
    
    async def _start_watchdog_monitoring(self) -> bool:
        """Watchdog監視開始"""
        try:
            if not WATCHDOG_AVAILABLE:
                return False
            
            self.observer = Observer()
            
            # ディレクトリごとに監視設定
            for dir_path_str, dir_path in self.watch_directories.items():
                # そのディレクトリ内の監視対象ファイル一覧
                target_files = [
                    file_path.name for config_name, file_path in self.watch_files.items()
                    if file_path.parent == dir_path
                ]
                
                if target_files:
                    # 統合コールバック作成
                    combined_callback = self._create_combined_callback(dir_path, target_files)
                    
                    # イベントハンドラー作成
                    event_handler = ConfigFileWatcher(combined_callback, target_files)
                    self.event_handlers[dir_path_str] = event_handler
                    
                    # 監視開始
                    self.observer.schedule(event_handler, str(dir_path), recursive=False)
                    logger.debug(f"📁 Watchdog監視設定: {dir_path} (ファイル: {target_files})")
            
            self.observer.start()
            logger.info("✅ Watchdog監視開始完了")
            return True
            
        except Exception as e:
            logger.error(f"❌ Watchdog監視開始エラー: {e}")
            if self.observer:
                try:
                    self.observer.stop()
                except:
                    pass
                self.observer = None
            return False
    
    def _create_combined_callback(self, dir_path: Path, target_files: list) -> Callable[[], Awaitable[None]]:
        """統合コールバック作成"""
        async def combined_callback():
            for config_name, file_path in self.watch_files.items():
                if file_path.parent == dir_path and file_path.name in target_files:
                    if config_name in self.reload_callbacks:
                        try:
                            await self.reload_callbacks[config_name]()
                            self.reload_count += 1
                            logger.debug(f"🔄 設定リロード実行: {config_name}")
                        except Exception as e:
                            logger.error(f"❌ 設定リロードエラー ({config_name}): {e}")
                            self.error_count += 1
        
        return combined_callback
    
    async def _start_polling_monitoring(self) -> bool:
        """ポーリング監視開始"""
        try:
            self.polling_task = asyncio.create_task(
                self._polling_loop(),
                name="file_watcher_polling"
            )
            logger.info("✅ ポーリング監視開始完了")
            return True
            
        except Exception as e:
            logger.error(f"❌ ポーリング監視開始エラー: {e}")
            return False
    
    async def _polling_loop(self) -> None:
        """ポーリング監視ループ"""
        logger.info("📁 ポーリング監視ループ開始")
        
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(self.polling_interval)
                await self._check_file_changes()
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"❌ ポーリング監視エラー: {e}")
                self.error_count += 1
                await asyncio.sleep(10)  # エラー時は長めに待機
        
        logger.info("📁 ポーリング監視ループ終了")
    
    async def _check_file_changes(self) -> None:
        """ファイル変更チェック"""
        for config_name, file_path in self.watch_files.items():
            try:
                if not file_path.exists():
                    logger.warning(f"⚠️ 監視対象ファイルが存在しません: {file_path}")
                    continue
                
                current_mtime = file_path.stat().st_mtime
                last_mtime = self.file_mtimes.get(config_name, 0)
                
                if current_mtime > last_mtime:
                    logger.info(f"🔄 設定ファイル変更検出: {config_name}")
                    self.file_mtimes[config_name] = current_mtime
                    
                    # リロードコールバック実行
                    if config_name in self.reload_callbacks:
                        try:
                            await self.reload_callbacks[config_name]()
                            self.reload_count += 1
                            logger.info(f"✅ 設定リロード完了: {config_name}")
                        except Exception as e:
                            logger.error(f"❌ 設定リロードエラー ({config_name}): {e}")
                            self.error_count += 1
                
            except Exception as e:
                logger.error(f"❌ ファイル変更チェックエラー ({config_name}): {e}")
                self.error_count += 1
    
    async def stop_monitoring(self) -> None:
        """監視停止"""
        try:
            logger.info("🛑 ファイル監視停止中...")
            
            # 停止シグナル設定
            self.shutdown_event.set()
            
            # Watchdog監視停止
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)
                self.observer = None
                logger.debug("🛑 Watchdog監視停止完了")
            
            # ポーリング監視停止
            if self.polling_task and not self.polling_task.done():
                self.polling_task.cancel()
                try:
                    await self.polling_task
                except asyncio.CancelledError:
                    pass
                logger.debug("🛑 ポーリング監視停止完了")
            
            logger.info("✅ ファイル監視停止完了")
            
        except Exception as e:
            logger.error(f"❌ ファイル監視停止エラー: {e}")
    
    # === 手動操作API ===
    
    async def force_reload_all(self) -> Dict[str, bool]:
        """全設定ファイル強制リロード"""
        results = {}
        
        for config_name, callback in self.reload_callbacks.items():
            try:
                await callback()
                results[config_name] = True
                self.reload_count += 1
                logger.info(f"✅ 強制リロード成功: {config_name}")
            except Exception as e:
                results[config_name] = False
                self.error_count += 1
                logger.error(f"❌ 強制リロードエラー ({config_name}): {e}")
        
        return results
    
    async def force_reload_config(self, config_name: str) -> bool:
        """特定設定ファイル強制リロード"""
        if config_name not in self.reload_callbacks:
            logger.warning(f"⚠️ 未登録の設定名: {config_name}")
            return False
        
        try:
            await self.reload_callbacks[config_name]()
            self.reload_count += 1
            logger.info(f"✅ 強制リロード成功: {config_name}")
            return True
        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ 強制リロードエラー ({config_name}): {e}")
            return False
    
    def update_file_mtime(self, config_name: str) -> bool:
        """ファイル更新時刻手動更新"""
        if config_name not in self.watch_files:
            return False
        
        try:
            file_path = self.watch_files[config_name]
            if file_path.exists():
                self.file_mtimes[config_name] = file_path.stat().st_mtime
                logger.debug(f"🔄 ファイル更新時刻更新: {config_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ ファイル更新時刻更新エラー ({config_name}): {e}")
            return False
    
    # === 状態取得API ===
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """監視状態取得"""
        return {
            "enabled": self.watch_enabled,
            "method": "watchdog" if (self.use_watchdog and self.observer) else "polling",
            "watchdog_available": WATCHDOG_AVAILABLE,
            "observer_active": self.observer is not None and self.observer.is_alive() if self.observer else False,
            "polling_active": self.polling_task is not None and not self.polling_task.done() if self.polling_task else False,
            "watched_files": len(self.watch_files),
            "watched_directories": len(self.watch_directories)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計取得"""
        return {
            "watch_count": self.watch_count,
            "reload_count": self.reload_count,
            "error_count": self.error_count,
            "success_rate": round((self.reload_count / max(self.reload_count + self.error_count, 1)) * 100, 2)
        }
    
    def get_watched_files(self) -> Dict[str, Dict[str, Any]]:
        """監視ファイル一覧取得"""
        result = {}
        
        for config_name, file_path in self.watch_files.items():
            try:
                result[config_name] = {
                    "path": str(file_path),
                    "exists": file_path.exists(),
                    "mtime": self.file_mtimes.get(config_name, 0),
                    "size": file_path.stat().st_size if file_path.exists() else 0
                }
            except Exception as e:
                result[config_name] = {
                    "path": str(file_path),
                    "exists": False,
                    "error": str(e)
                }
        
        return result
    
    # === テスト・デバッグ機能 ===
    
    async def test_reload(self, config_name: str) -> bool:
        """リロードテスト"""
        logger.info(f"🧪 リロードテスト開始: {config_name}")
        return await self.force_reload_config(config_name)
    
    def print_status_summary(self) -> None:
        """ステータスサマリー出力"""
        status = self.get_monitoring_status()
        stats = self.get_statistics()
        files = self.get_watched_files()
        
        print("=" * 60)
        print("📁 ファイル監視システム サマリー")
        print("=" * 60)
        print(f"監視状態: {'🟢 有効' if status['enabled'] else '🔴 無効'}")
        print(f"監視方式: {status['method']}")
        print(f"Watchdog利用可能: {'✅' if status['watchdog_available'] else '❌'}")
        print(f"Observer状態: {'🟢 アクティブ' if status['observer_active'] else '🔴 停止'}")
        print(f"Polling状態: {'🟢 アクティブ' if status['polling_active'] else '🔴 停止'}")
        print(f"監視ファイル数: {status['watched_files']}")
        print(f"監視ディレクトリ数: {status['watched_directories']}")
        print(f"リロード実行回数: {stats['reload_count']}")
        print(f"エラー回数: {stats['error_count']}")
        print(f"成功率: {stats['success_rate']}%")
        print()
        
        if files:
            print("監視ファイル一覧:")
            for config_name, file_info in files.items():
                exists_icon = "✅" if file_info.get("exists", False) else "❌"
                size = file_info.get("size", 0)
                print(f"  {exists_icon} {config_name}: {file_info['path']} ({size}bytes)")
        
        print("=" * 60)
    
    # === 設定ファイル操作ユーティリティ ===
    
    async def load_json_config(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """JSON設定ファイル読み込み"""
        try:
            if not file_path.exists():
                logger.warning(f"⚠️ 設定ファイルが存在しません: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                config_data = json.loads(content)
            
            logger.debug(f"📁 JSON設定読み込み成功: {file_path} ({len(config_data)}項目)")
            return config_data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON設定解析エラー ({file_path}): {e}")
            return None
        except Exception as e:
            logger.error(f"❌ JSON設定読み込みエラー ({file_path}): {e}")
            return None
    
    async def save_json_config(self, file_path: Path, config_data: Dict[str, Any]) -> bool:
        """JSON設定ファイル保存"""
        try:
            # バックアップ作成
            if file_path.exists():
                backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
                backup_path.write_bytes(file_path.read_bytes())
                logger.debug(f"📁 設定バックアップ作成: {backup_path}")
            
            # 設定保存
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # 更新時刻更新
            for config_name, watch_path in self.watch_files.items():
                if watch_path == file_path:
                    self.file_mtimes[config_name] = file_path.stat().st_mtime
                    break
            
            logger.debug(f"📁 JSON設定保存成功: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ JSON設定保存エラー ({file_path}): {e}")
            return False
    
    def validate_json_config(self, file_path: Path) -> bool:
        """JSON設定ファイルバリデーション"""
        try:
            if not file_path.exists():
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            
            return True
            
        except json.JSONDecodeError:
            return False
        except Exception:
            return False
    
    # === クリーンアップ ===
    
    async def cleanup(self) -> None:
        """クリーンアップ"""
        try:
            # 監視停止
            await self.stop_monitoring()
            
            # データクリア
            self.watch_directories.clear()
            self.watch_files.clear()
            self.file_mtimes.clear()
            self.reload_callbacks.clear()
            self.event_handlers.clear()
            
            # 状態リセット
            self.watch_count = 0
            self.reload_count = 0
            self.error_count = 0
            
            logger.info("🧹 ファイル監視システムクリーンアップ完了")
            
        except Exception as e:
            logger.error(f"❌ ファイル監視クリーンアップエラー: {e}")

# === ユーティリティ関数 ===

def create_file_watcher(system_config: SystemConfig) -> FileWatcher:
    """ファイル監視システムファクトリー関数"""
    return FileWatcher(system_config)

async def setup_config_monitoring(watcher: FileWatcher, config_dir: Path, 
                                 reload_callbacks: Dict[str, Callable[[], Awaitable[None]]]) -> bool:
    """設定監視セットアップヘルパー"""
    try:
        success_count = 0
        
        for config_name, callback in reload_callbacks.items():
            config_file = config_dir / f"{config_name}.json"
            if watcher.add_config_file(config_name, config_file, callback):
                success_count += 1
        
        if success_count > 0:
            return await watcher.start_monitoring()
        else:
            logger.warning("⚠️ 監視対象ファイルの追加に失敗しました")
            return False
            
    except Exception as e:
        logger.error(f"❌ 設定監視セットアップエラー: {e}")
        return False

# === エクスポート ===

__all__ = [
    "FileWatcher",
    "ConfigFileWatcher", 
    "WATCHDOG_AVAILABLE",
    "create_file_watcher",
    "setup_config_monitoring"
]