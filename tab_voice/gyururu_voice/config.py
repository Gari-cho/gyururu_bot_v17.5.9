#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 音声管理システム設定・型定義モジュール
実稼働環境対応の型安全な設定管理

Features:
✅ TypedDict完全対応
✅ Python 3.8+ 互換性
✅ 設定バリデーション
✅ デフォルト値管理
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

# Python 3.8+ 互換性確保
try:
    from typing import Dict, Any, Optional, List, Literal, TypedDict, Union
except ImportError:
    from typing_extensions import Dict, Any, Optional, List, Literal, TypedDict, Union

# === バージョン情報 ===
VERSION = "15.0.0-final"
REQUIRED_PYTHON = (3, 8)

# === 依存関係定義 ===
DEPENDENCIES = {
    "pygame": ">=2.5.0,<3.0.0",
    "aiohttp": ">=3.8.0,<4.0.0", 
    "aiofiles": ">=22.0.0,<24.0.0"
}

OPTIONAL_DEPENDENCIES = {
    "watchdog": ">=3.0.0,<4.0.0",
    "typing-extensions": ">=4.0.0,<5.0.0"
}

# === 型定義 ===

class VoiceSettings(TypedDict, total=False):
    """音声設定型定義（実稼働版）"""
    gyururu_voice_id: int
    default_voice_id: int
    speed: int
    pitch: int
    volume: int
    user_voice_mapping: Dict[str, Any]
    enable_voicevox: bool
    enable_bouyomi: bool
    audio_output_method: Literal["voicevox", "bouyomi", "both"]
    quality_mode: Literal["high", "normal", "fast"]
    anti_alias: bool
    noise_reduction: bool
    sample_rate: Literal[44100, 48000, 22050]
    buffer_size: Literal[1024, 2048, 4096, 8192]

class SystemConfig(TypedDict, total=False):
    """システム設定型定義（実稼働版）"""
    max_queue_size: int
    synthesis_timeout: int
    playback_timeout: int
    retry_attempts: int
    retry_delay: float
    retry_exponential_backoff: bool
    health_check_interval: int
    auto_cleanup_interval: int
    enable_performance_logging: bool
    log_structured_format: bool
    config_hot_reload: bool
    config_watchdog_enabled: bool
    log_rotation_enabled: bool
    log_max_days: int
    error_notification_interval: int
    health_score_thresholds: Dict[str, int]
    bouyomi_retry_interval: int
    statistics_retention_size: int

class BouyomiConfig(TypedDict, total=False):
    """棒読みちゃん設定型定義"""
    host: str
    tcp_port: int
    http_port: int
    tcp_available: bool
    http_available: bool
    preferred_method: Optional[Literal["tcp", "http"]]
    last_retry_time: float

class AudioDeviceInfo(TypedDict):
    """オーディオデバイス情報型定義"""
    sample_rate: int
    buffer_size: int
    channels: int
    format_bits: int

# === リテラル型定義 ===
PriorityLevel = Literal["emergency", "high", "normal", "low", "background"]
OutputMethod = Literal["voicevox", "bouyomi", "both"]
HealthStatus = Literal["excellent", "good", "fair", "poor", "critical", "unknown", "shutdown"]
EnvironmentType = Literal["windows", "linux", "macos", "executable", "test", "unknown"]

# === データクラス定義 ===

@dataclass(order=True)
class VoiceRequest:
    """型安全な優先度付き音声リクエスト"""
    priority: int
    timestamp: float = field(compare=True)
    data: Dict[str, Any] = field(compare=False)
    
    @classmethod
    def create(cls, priority: PriorityLevel, data: Dict[str, Any]) -> 'VoiceRequest':
        """ファクトリーメソッド（5段階優先度対応）"""
        priority_map = {
            "emergency": 0,
            "high": 1, 
            "normal": 5, 
            "low": 8,
            "background": 9
        }
        return cls(
            priority=priority_map[priority],
            timestamp=__import__('time').time(),
            data=data
        )

@dataclass
class SpeakerInfo:
    """話者情報データクラス"""
    id: int
    name: str
    speaker_name: str
    style_name: str
    speaker_uuid: str
    category: str

@dataclass
class AudioStats:
    """音声統計データクラス"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    voicevox_requests: int = 0
    bouyomi_requests: int = 0
    average_processing_time: float = 0.0
    average_synthesis_time: float = 0.0
    average_playback_time: float = 0.0

# === 設定デフォルト値 ===

def get_default_voice_settings(detected_sample_rate: int = 44100, 
                              detected_buffer_size: int = 4096) -> VoiceSettings:
    """デフォルト音声設定取得"""
    return {
        "gyururu_voice_id": 46,
        "default_voice_id": 1,
        "speed": 100,
        "pitch": 100,
        "volume": 70,
        "user_voice_mapping": {"enabled": True, "default_mapping": {}},
        "enable_voicevox": True,
        "enable_bouyomi": False,
        "audio_output_method": "voicevox",
        "quality_mode": "high",
        "anti_alias": True,
        "noise_reduction": True,
        "sample_rate": detected_sample_rate,
        "buffer_size": detected_buffer_size
    }

def get_default_system_config() -> SystemConfig:
    """デフォルトシステム設定取得"""
    return {
        "max_queue_size": 100,
        "synthesis_timeout": 30,
        "playback_timeout": 60,
        "retry_attempts": 3,
        "retry_delay": 1.0,
        "retry_exponential_backoff": True,
        "health_check_interval": 30,
        "auto_cleanup_interval": 300,
        "enable_performance_logging": True,
        "log_structured_format": True,
        "config_hot_reload": True,
        "config_watchdog_enabled": True,
        "log_rotation_enabled": True,
        "log_max_days": 7,
        "error_notification_interval": 5,
        "health_score_thresholds": {
            "excellent": 90,
            "good": 70,
            "fair": 50,
            "poor": 30,
            "critical": 10
        },
        "bouyomi_retry_interval": 300,
        "statistics_retention_size": 500
    }

def get_default_bouyomi_config() -> BouyomiConfig:
    """デフォルト棒読みちゃん設定取得"""
    return {
        "host": "127.0.0.1",
        "tcp_port": 50001,
        "http_port": 50080,
        "tcp_available": False,
        "http_available": False,
        "preferred_method": None,
        "last_retry_time": 0.0
    }

# === 設定バリデーション ===

def validate_voice_settings(settings: Dict[str, Any]) -> VoiceSettings:
    """音声設定バリデーション"""
    validated = {}
    
    # 必須項目チェック
    validated["gyururu_voice_id"] = max(0, int(settings.get("gyururu_voice_id", 46)))
    validated["default_voice_id"] = max(0, int(settings.get("default_voice_id", 1)))
    
    # 範囲チェック
    validated["speed"] = max(50, min(300, int(settings.get("speed", 100))))
    validated["pitch"] = max(50, min(200, int(settings.get("pitch", 100))))
    validated["volume"] = max(0, min(100, int(settings.get("volume", 70))))
    
    # フラグ
    validated["enable_voicevox"] = bool(settings.get("enable_voicevox", True))
    validated["enable_bouyomi"] = bool(settings.get("enable_bouyomi", False))
    validated["anti_alias"] = bool(settings.get("anti_alias", True))
    validated["noise_reduction"] = bool(settings.get("noise_reduction", True))
    
    # 選択項目
    output_method = settings.get("audio_output_method", "voicevox")
    if output_method in ["voicevox", "bouyomi", "both"]:
        validated["audio_output_method"] = output_method
    else:
        validated["audio_output_method"] = "voicevox"
    
    quality_mode = settings.get("quality_mode", "high")
    if quality_mode in ["high", "normal", "fast"]:
        validated["quality_mode"] = quality_mode
    else:
        validated["quality_mode"] = "high"
    
    # サンプリングレート
    sample_rate = int(settings.get("sample_rate", 44100))
    if sample_rate in [22050, 44100, 48000]:
        validated["sample_rate"] = sample_rate
    else:
        validated["sample_rate"] = 44100
    
    # バッファサイズ
    buffer_size = int(settings.get("buffer_size", 4096))
    if buffer_size in [1024, 2048, 4096, 8192]:
        validated["buffer_size"] = buffer_size
    else:
        validated["buffer_size"] = 4096
    
    # ユーザーマッピング
    user_mapping = settings.get("user_voice_mapping", {})
    if isinstance(user_mapping, dict):
        validated["user_voice_mapping"] = user_mapping
    else:
        validated["user_voice_mapping"] = {"enabled": True, "default_mapping": {}}
    
    return validated

def validate_system_config(config: Dict[str, Any]) -> SystemConfig:
    """システム設定バリデーション"""
    validated = {}
    
    # 数値項目
    validated["max_queue_size"] = max(10, min(1000, int(config.get("max_queue_size", 100))))
    validated["synthesis_timeout"] = max(5, min(120, int(config.get("synthesis_timeout", 30))))
    validated["playback_timeout"] = max(10, min(300, int(config.get("playback_timeout", 60))))
    validated["retry_attempts"] = max(1, min(10, int(config.get("retry_attempts", 3))))
    validated["retry_delay"] = max(0.1, min(10.0, float(config.get("retry_delay", 1.0))))
    validated["health_check_interval"] = max(10, min(300, int(config.get("health_check_interval", 30))))
    validated["auto_cleanup_interval"] = max(60, min(3600, int(config.get("auto_cleanup_interval", 300))))
    validated["error_notification_interval"] = max(1, min(20, int(config.get("error_notification_interval", 5))))
    validated["bouyomi_retry_interval"] = max(60, min(1800, int(config.get("bouyomi_retry_interval", 300))))
    validated["statistics_retention_size"] = max(50, min(2000, int(config.get("statistics_retention_size", 500))))
    validated["log_max_days"] = max(1, min(30, int(config.get("log_max_days", 7))))
    
    # フラグ項目
    validated["retry_exponential_backoff"] = bool(config.get("retry_exponential_backoff", True))
    validated["enable_performance_logging"] = bool(config.get("enable_performance_logging", True))
    validated["log_structured_format"] = bool(config.get("log_structured_format", True))
    validated["config_hot_reload"] = bool(config.get("config_hot_reload", True))
    validated["config_watchdog_enabled"] = bool(config.get("config_watchdog_enabled", True))
    validated["log_rotation_enabled"] = bool(config.get("log_rotation_enabled", True))
    
    # ヘルス閾値
    thresholds = config.get("health_score_thresholds", {})
    if isinstance(thresholds, dict):
        validated["health_score_thresholds"] = {
            "excellent": max(80, min(100, int(thresholds.get("excellent", 90)))),
            "good": max(60, min(90, int(thresholds.get("good", 70)))),
            "fair": max(40, min(70, int(thresholds.get("fair", 50)))),
            "poor": max(20, min(50, int(thresholds.get("poor", 30)))),
            "critical": max(0, min(30, int(thresholds.get("critical", 10))))
        }
    else:
        validated["health_score_thresholds"] = {
            "excellent": 90, "good": 70, "fair": 50, "poor": 30, "critical": 10
        }
    
    return validated

# === 環境検出 ===

def detect_environment() -> EnvironmentType:
    """実行環境検出"""
    try:
        import platform
        
        if hasattr(__import__('sys'), 'frozen'):
            return "executable"
        elif 'pytest' in __import__('sys').modules:
            return "test"
        elif platform.system() == "Windows":
            return "windows"
        elif platform.system() == "Linux":
            return "linux"
        elif platform.system() == "Darwin":
            return "macos"
        else:
            return "unknown"
    except:
        return "unknown"

def check_dependencies() -> Dict[str, bool]:
    """依存関係チェック"""
    results = {}
    
    # 必須依存関係
    for dep in DEPENDENCIES:
        try:
            __import__(dep)
            results[dep] = True
        except ImportError:
            results[dep] = False
    
    # オプション依存関係
    for dep in OPTIONAL_DEPENDENCIES:
        try:
            __import__(dep)
            results[f"{dep}_optional"] = True
        except ImportError:
            results[f"{dep}_optional"] = False
    
    return results

# === パッケージ情報 ===

PACKAGE_METADATA = {
    "name": "gyururu_voice",
    "version": VERSION,
    "description": "Gyururu Bot音声管理システム v15 Final Production Edition",
    "author": "Gyururu Bot Team",
    "license": "MIT",
    "python_requires": f">={REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}",
    "dependencies": DEPENDENCIES,
    "optional_dependencies": OPTIONAL_DEPENDENCIES
}

# === エクスポート ===

__all__ = [
    # バージョン・メタデータ
    "VERSION", "REQUIRED_PYTHON", "DEPENDENCIES", "OPTIONAL_DEPENDENCIES", "PACKAGE_METADATA",
    
    # 型定義
    "VoiceSettings", "SystemConfig", "BouyomiConfig", "AudioDeviceInfo",
    "PriorityLevel", "OutputMethod", "HealthStatus", "EnvironmentType",
    
    # データクラス
    "VoiceRequest", "SpeakerInfo", "AudioStats",
    
    # デフォルト値取得
    "get_default_voice_settings", "get_default_system_config", "get_default_bouyomi_config",
    
    # バリデーション
    "validate_voice_settings", "validate_system_config",
    
    # ユーティリティ
    "detect_environment", "check_dependencies"
]