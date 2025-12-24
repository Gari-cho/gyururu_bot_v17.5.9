"""
ボイスチャット機能パッケージ

Phase4-2で追加された新機能:
- 音声認識（Speech-to-Text）
- 音声合成（Text-to-Speech）  
- リアルタイム音声処理
- 音声設定管理
"""

__version__ = "1.0.0"
__author__ = "ぎゅるるボット開発チーム"

# 主要クラスのインポート
try:
    from .voice_chat_ui import VoiceChatUI
    from .voice_settings import VoiceSettings
    __all__ = ['VoiceChatUI', 'VoiceSettings']
except ImportError as e:
    print(f"⚠️ ボイスチャット機能のインポートエラー: {e}")
    __all__ = []