#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚨 エラーハンドリング統一モジュール
例外チェーン化・詳細エラー情報・デバッグ支援

Features:
✅ カスタム例外階層
✅ 例外チェーン化で原因追跡
✅ 詳細エラー情報収集
✅ デバッグ支援機能
✅ ログ統合
"""

import asyncio
import traceback
import sys
from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Any, Optional, Type, Union, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

try:
    from gyururu_utils.logger import get_gui_logger
    logger = get_gui_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# === エラー重要度 ===

class ErrorSeverity(Enum):
    """エラー重要度"""
    CRITICAL = "critical"    # システム停止レベル
    HIGH = "high"           # 機能停止レベル  
    MEDIUM = "medium"       # 部分機能影響
    LOW = "low"            # 軽微な問題
    INFO = "info"          # 情報レベル

# === カスタム例外階層 ===

class GyururuVoiceError(Exception):
    """音声管理システム基底例外"""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 context: Optional[Dict[str, Any]] = None, component: str = "unknown"):
        super().__init__(message)
        self.severity = severity
        self.context = context or {}
        self.component = component
        self.timestamp = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """例外情報を辞書形式で取得"""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "severity": self.severity.value,
            "component": self.component,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "traceback": traceback.format_exc() if sys.exc_info()[0] else None
        }

class VoiceInitializationError(GyururuVoiceError):
    """初期化エラー"""
    def __init__(self, message: str, component: str = "initialization", **kwargs):
        super().__init__(message, ErrorSeverity.CRITICAL, component=component, **kwargs)

class VoiceConfigurationError(GyururuVoiceError):
    """設定エラー"""
    def __init__(self, message: str, component: str = "configuration", **kwargs):
        super().__init__(message, ErrorSeverity.HIGH, component=component, **kwargs)

class VoiceNetworkError(GyururuVoiceError):
    """ネットワークエラー"""
    def __init__(self, message: str, component: str = "network", **kwargs):
        super().__init__(message, ErrorSeverity.MEDIUM, component=component, **kwargs)

class VoicePlaybackError(GyururuVoiceError):
    """再生エラー"""
    def __init__(self, message: str, component: str = "playback", **kwargs):
        super().__init__(message, ErrorSeverity.HIGH, component=component, **kwargs)

class VoiceQueueError(GyururuVoiceError):
    """キューエラー"""
    def __init__(self, message: str, component: str = "queue", **kwargs):
        super().__init__(message, ErrorSeverity.MEDIUM, component=component, **kwargs)

class VoiceFileWatchError(GyururuVoiceError):
    """ファイル監視エラー"""
    def __init__(self, message: str, component: str = "file_watcher", **kwargs):
        super().__init__(message, ErrorSeverity.LOW, component=component, **kwargs)

# === エラー情報収集 ===

@dataclass
class ErrorContext:
    """エラーコンテキスト情報"""
    operation: str
    component: str
    parameters: Dict[str, Any]
    system_info: Dict[str, Any]
    timestamp: datetime
    
    @classmethod
    def create(cls, operation: str, component: str, **kwargs) -> 'ErrorContext':
        """エラーコンテキスト作成"""
        import platform
        import psutil
        
        try:
            system_info = {
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "memory_usage": psutil.virtual_memory().percent,
                "cpu_usage": psutil.cpu_percent(interval=0.1)
            }
        except:
            system_info = {"platform": platform.system()}
        
        return cls(
            operation=operation,
            component=component,
            parameters=kwargs,
            system_info=system_info,
            timestamp=datetime.now()
        )

# === エラーハンドリングコンテキストマネージャー ===

@contextmanager
def error_context(operation: str, component: str, 
                 reraise_as: Optional[Type[GyururuVoiceError]] = None,
                 **context_params):
    """同期エラーハンドリングコンテキスト"""
    error_ctx = ErrorContext.create(operation, component, **context_params)
    
    try:
        yield error_ctx
    except GyururuVoiceError:
        # 既にカスタム例外の場合はそのまま再raise
        raise
    except Exception as e:
        # 標準例外をカスタム例外にチェーン
        error_message = f"{operation}エラー: {e}"
        
        if reraise_as:
            raise reraise_as(error_message, component=component, context=error_ctx.parameters) from e
        else:
            raise GyururuVoiceError(error_message, component=component, context=error_ctx.parameters) from e

@asynccontextmanager
async def async_error_context(operation: str, component: str,
                             reraise_as: Optional[Type[GyururuVoiceError]] = None,
                             **context_params):
    """非同期エラーハンドリングコンテキスト"""
    error_ctx = ErrorContext.create(operation, component, **context_params)
    
    try:
        yield error_ctx
    except asyncio.CancelledError:
        # キャンセル例外は特別扱い
        logger.debug(f"⏹️ {operation} キャンセル ({component})")
        raise
    except GyururuVoiceError:
        # 既にカスタム例外の場合はそのまま再raise
        raise
    except Exception as e:
        # 標準例外をカスタム例外にチェーン
        error_message = f"{operation}エラー: {e}"
        
        if reraise_as:
            raise reraise_as(error_message, component=component, context=error_ctx.parameters) from e
        else:
            raise GyururuVoiceError(error_message, component=component, context=error_ctx.parameters) from e

# === エラー統計・追跡 ===

class ErrorTracker:
    """エラー統計・追跡システム"""
    
    def __init__(self):
        self.error_counts = {}
        self.error_history = []
        self.last_errors = {}
        self.suppression_rules = {}
    
    def record_error(self, error: GyururuVoiceError) -> bool:
        """エラー記録・抑制判定"""
        error_key = f"{error.component}:{error.__class__.__name__}"
        
        # エラーカウント更新
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # 履歴追加
        error_info = error.to_dict()
        self.error_history.append(error_info)
        
        # 履歴サイズ制限
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-50:]
        
        # 抑制判定
        should_log = self._should_log_error(error_key, error)
        
        if should_log:
            self._log_error(error)
        
        self.last_errors[error_key] = datetime.now()
        return should_log
    
    def _should_log_error(self, error_key: str, error: GyururuVoiceError) -> bool:
        """エラーログ出力判定"""
        count = self.error_counts[error_key]
        
        # 重要度がCRITICALまたはHIGHは常にログ出力
        if error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            return True
        
        # 初回～3回目は出力
        if count <= 3:
            return True
        
        # 5回目ごとに出力
        if count % 5 == 0:
            return True
        
        # 最後のエラーから5分経過後は出力
        last_time = self.last_errors.get(error_key)
        if last_time and (datetime.now() - last_time).seconds > 300:
            return True
        
        return False
    
    def _log_error(self, error: GyururuVoiceError) -> None:
        """エラーログ出力"""
        error_info = error.to_dict()
        
        # 重要度に応じたログレベル
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"🔥 CRITICAL: {error}")
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(f"❌ HIGH: {error}")
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"⚠️ MEDIUM: {error}")
        elif error.severity == ErrorSeverity.LOW:
            logger.info(f"ℹ️ LOW: {error}")
        else:
            logger.debug(f"🔍 INFO: {error}")
        
        # 詳細情報をデバッグログに出力
        logger.debug(f"エラー詳細: {error_info}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """エラーサマリー取得"""
        return {
            "error_counts": dict(self.error_counts),
            "total_errors": sum(self.error_counts.values()),
            "recent_errors": self.error_history[-10:] if self.error_history else [],
            "error_types": len(self.error_counts)
        }

# === グローバルエラートラッカー ===
_global_error_tracker = ErrorTracker()

def get_error_tracker() -> ErrorTracker:
    """グローバルエラートラッカー取得"""
    return _global_error_tracker

# === デバッグ支援関数 ===

def log_error_chain(error: Exception) -> None:
    """エラーチェーン詳細ログ出力"""
    chain = []
    current = error
    
    while current:
        if isinstance(current, GyururuVoiceError):
            chain.append({
                "type": current.__class__.__name__,
                "message": str(current),
                "component": current.component,
                "severity": current.severity.value,
                "context": current.context
            })
        else:
            chain.append({
                "type": current.__class__.__name__,
                "message": str(current),
                "component": "unknown",
                "severity": "unknown"
            })
        current = current.__cause__
    
    logger.error(f"🔗 エラーチェーン詳細:")
    for i, error_info in enumerate(chain):
        logger.error(f"  {i+1}. {error_info['type']}: {error_info['message']} [{error_info['component']}]")

def create_detailed_error_report(error: Exception) -> Dict[str, Any]:
    """詳細エラーレポート作成"""
    import platform
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "system_info": {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "platform_release": platform.release()
        },
        "traceback": traceback.format_exc(),
        "error_chain": []
    }
    
    # エラーチェーン情報
    current = error
    while current:
        error_info = {
            "type": current.__class__.__name__,
            "message": str(current)
        }
        
        if isinstance(current, GyururuVoiceError):
            error_info.update({
                "component": current.component,
                "severity": current.severity.value,
                "context": current.context
            })
        
        report["error_chain"].append(error_info)
        current = current.__cause__
    
    return report

# === 特殊エラーハンドラー ===

def handle_initialization_error(func):
    """初期化エラー専用デコレータ"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            component = getattr(args[0], '__class__', 'unknown').__name__ if args else 'unknown'
            raise VoiceInitializationError(
                f"{func.__name__}初期化失敗: {e}",
                component=component.lower(),
                context={"function": func.__name__, "args": str(args), "kwargs": str(kwargs)}
            ) from e
    return wrapper

def handle_async_initialization_error(func):
    """非同期初期化エラー専用デコレータ"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            component = getattr(args[0], '__class__', 'unknown').__name__ if args else 'unknown'
            raise VoiceInitializationError(
                f"{func.__name__}非同期初期化失敗: {e}",
                component=component.lower(),
                context={"function": func.__name__, "args": str(args), "kwargs": str(kwargs)}
            ) from e
    return wrapper

# === 安全実行ヘルパー ===

async def safe_async_execute(coro: Awaitable, operation: str, component: str, 
                            default_return=None, reraise_as: Optional[Type[GyururuVoiceError]] = None):
    """安全な非同期実行"""
    async with async_error_context(operation, component, reraise_as=reraise_as):
        try:
            return await coro
        except GyururuVoiceError as e:
            get_error_tracker().record_error(e)
            if e.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
                raise  # 重要なエラーは再raise
            return default_return
        except Exception as e:
            # 予期しないエラーは常に再raise
            raise

def safe_execute(func: Callable, operation: str, component: str, 
                default_return=None, reraise_as: Optional[Type[GyururuVoiceError]] = None):
    """安全な同期実行"""
    with error_context(operation, component, reraise_as=reraise_as):
        try:
            return func()
        except GyururuVoiceError as e:
            get_error_tracker().record_error(e)
            if e.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
                raise  # 重要なエラーは再raise
            return default_return
        except Exception as e:
            # 予期しないエラーは常に再raise
            raise

# === エクスポート ===

__all__ = [
    # 例外クラス
    "GyururuVoiceError", "VoiceInitializationError", "VoiceConfigurationError",
    "VoiceNetworkError", "VoicePlaybackError", "VoiceQueueError", "VoiceFileWatchError",
    
    # エラー重要度
    "ErrorSeverity",
    
    # コンテキストマネージャー
    "error_context", "async_error_context",
    
    # エラー追跡
    "ErrorTracker", "get_error_tracker",
    
    # デバッグ支援
    "log_error_chain", "create_detailed_error_report",
    
    # デコレータ
    "handle_initialization_error", "handle_async_initialization_error",
    
    # 安全実行
    "safe_async_execute", "safe_execute"
]