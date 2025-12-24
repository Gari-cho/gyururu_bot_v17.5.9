#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎤 ぎゅるるボット音声管理システム v15 Final Production Edition
実稼働環境完全対応パッケージ

Version: v15.0.0-final
License: MIT
Author: Gyururu Bot Team
"""

from .manager import VoiceManagerV15FinalProduction
from .config import VERSION, VoiceSettings, SystemConfig, PriorityLevel, OutputMethod

# 公開API
__version__ = "15.0.0-final"
__all__ = [
    "VoiceManagerV15FinalProduction", 
    "VoiceSettings", 
    "SystemConfig", 
    "PriorityLevel", 
    "OutputMethod",
    "VERSION"
]

# 後方互換性のためのエイリアス
VoiceManager = VoiceManagerV15FinalProduction

def create_voice_manager(bot_instance):
    """音声管理システムファクトリー関数"""
    return VoiceManagerV15FinalProduction(bot_instance)

# パッケージ情報
PACKAGE_INFO = {
    "name": "gyururu_voice",
    "version": __version__,
    "description": "Gyururu Bot音声管理システム - 実稼働環境完全対応",
    "features": [
        "完全asyncio統合",
        "型安全性保証",
        "Watchdog設定監視",
        "ログローテート",
        "指数バックオフリトライ",
        "5段階優先度システム",
        "自動デバイス最適化",
        "CI/CD対応"
    ],
    "compatibility": {
        "python": ">=3.8",
        "platforms": ["Windows", "Linux", "macOS"],
        "audio_engines": ["VOICEVOX", "棒読みちゃん"]
    }
}