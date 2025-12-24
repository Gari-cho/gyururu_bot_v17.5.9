"""
ボイスチャット機能のUI管理クラス

機能:
- 音声認識インターフェース
- 音声合成コントロール
- デバイス管理
- リアルタイム音声処理状態表示
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
from datetime import datetime

class VoiceChatUI:
    """ボイスチャット機能のUIクラス"""
    
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.is_recording = False
        self.is_speaking = False
        self.voice_settings = self._load_voice_settings()
        
        # UI状態管理
        self.status = {
            'microphone': 'ready',  # ready, recording, processing
            'speaker': 'ready',     # ready, speaking, error
            'connection': 'disconnected'  # connected, disconnected, error
        }
        
        print("✅ ボイスチャットUI初期化完了")

    def _load_voice_settings(self):
        """音声設定を読み込み"""
        default_settings = {
            'microphone_device': 'default',
            'speaker_device': 'default',
            'volume': 70,
            'voice_sensitivity': 50,
            'auto_response': True,
            'voice_effects': False,
            'language': 'ja-JP'
        }
        
        try:
            with open('voice_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return {**default_settings, **settings}
        except FileNotFoundError:
            return default_settings
        except Exception as e:
            print(f"⚠️ 音声設定読み込みエラー: {e}")
            return default_settings

    def save_voice_settings(self):
        """音声設定を保存"""
        try:
            with open('voice_settings.json', 'w', encoding='utf-8') as f:
                json.dump(self.voice_settings, f, indent=2, ensure_ascii=False)
            print("✅ 音声設定保存完了")
        except Exception as e:
            print(f"❌ 音声設定保存エラー: {e}")

    def start_voice_recognition(self):
        """音声認識開始"""
        if self.is_recording:
            print("⚠️ 既に音声認識中です")
            return
            
        try:
            self.is_recording = True
            self.status['microphone'] = 'recording'
            
            # 音声認識スレッド開始
            recognition_thread = threading.Thread(
                target=self._voice_recognition_worker,
                daemon=True
            )
            recognition_thread.start()
            
            print("🎙️ 音声認識開始")
            
        except Exception as e:
            print(f"❌ 音声認識開始エラー: {e}")
            self.is_recording = False
            self.status['microphone'] = 'ready'

    def stop_voice_recognition(self):
        """音声認識停止"""
        try:
            self.is_recording = False
            self.status['microphone'] = 'ready'
            print("🛑 音声認識停止")
            
        except Exception as e:
            print(f"❌ 音声認識停止エラー: {e}")

    def _voice_recognition_worker(self):
        """音声認識ワーカー（バックグラウンド処理）"""
        try:
            # 実際の音声認識処理はここに実装
            # 現在は仮実装
            import time
            
            while self.is_recording:
                # 仮の音声認識処理
                time.sleep(0.1)
                
                # 音声が検出されたという仮定
                if self._detect_voice_activity():
                    recognized_text = self._process_speech_recognition()
                    if recognized_text:
                        self._handle_recognized_text(recognized_text)
                        
        except Exception as e:
            print(f"❌ 音声認識ワーカーエラー: {e}")
            self.is_recording = False
            self.status['microphone'] = 'ready'

    def _detect_voice_activity(self):
        """音声アクティビティ検出（仮実装）"""
        # 実際のマイク入力レベル検出はここに実装
        import random
        return random.random() < 0.01  # 1%の確率で音声検出

    def _process_speech_recognition(self):
        """音声認識処理（仮実装）"""
        # 実際の音声認識エンジン（Google Speech API等）はここに実装
        sample_texts = [
            "こんにちはだぎゅる",
            "今日はいい天気ですね",
            "ぎゅるるボットの調子はどうですか？",
            "音楽をかけてください",
            "天気予報を教えて"
        ]
        
        import random
        return random.choice(sample_texts)

    def _handle_recognized_text(self, text):
        """認識されたテキストの処理"""
        try:
            print(f"🎙️ 音声認識結果: {text}")
            
            # チャットシステムに送信（実装時にAIConnectorと連携）
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # 親アプリケーションにメッセージを送信
            if hasattr(self, 'message_callback'):
                self.message_callback(f"[音声] {text}")
            
            # AI応答を音声合成で再生
            if self.voice_settings.get('auto_response', True):
                self._generate_ai_response(text)
                
        except Exception as e:
            print(f"❌ 認識テキスト処理エラー: {e}")

    def _generate_ai_response(self, user_message):
        """AI応答生成と音声合成"""
        try:
            # 仮のAI応答生成
            sample_responses = [
                "こんにちはだぎゅる♪ 元気にしてるぎゅる？",
                "今日もいい天気だぎゅる～！",
                "ぎゅるるは元気だぎゅる！みんなと話せて嬉しいぎゅる♪",
                "音楽を再生するぎゅる♪ どんな曲がいいぎゅる？",
                "天気予報を調べてみるぎゅる～！"
            ]
            
            import random
            ai_response = random.choice(sample_responses)
            
            print(f"🤖 AI応答: {ai_response}")
            
            # 音声合成で再生
            self.speak_text(ai_response)
            
        except Exception as e:
            print(f"❌ AI応答生成エラー: {e}")

    def speak_text(self, text):
        """テキストを音声合成で再生"""
        if self.is_speaking:
            print("⚠️ 既に音声再生中です")
            return
            
        try:
            self.is_speaking = True
            self.status['speaker'] = 'speaking'
            
            # 音声合成スレッド開始
            speech_thread = threading.Thread(
                target=self._text_to_speech_worker,
                args=(text,),
                daemon=True
            )
            speech_thread.start()
            
            print(f"🔊 音声合成開始: {text}")
            
        except Exception as e:
            print(f"❌ 音声合成エラー: {e}")
            self.is_speaking = False
            self.status['speaker'] = 'ready'

    def _text_to_speech_worker(self, text):
        """音声合成ワーカー（バックグラウンド処理）"""
        try:
            # 実際の音声合成処理はここに実装
            # 現在は仮実装（時間経過をシミュレート）
            import time
            
            # 文字数に応じた再生時間計算
            play_duration = len(text) * 0.15  # 文字あたり0.15秒
            time.sleep(play_duration)
            
            print(f"🔊 音声再生完了: {text}")
            
        except Exception as e:
            print(f"❌ 音声合成ワーカーエラー: {e}")
        finally:
            self.is_speaking = False
            self.status['speaker'] = 'ready'

    def stop_speech(self):
        """音声再生停止"""
        try:
            self.is_speaking = False
            self.status['speaker'] = 'ready'
            print("🛑 音声再生停止")
            
        except Exception as e:
            print(f"❌ 音声停止エラー: {e}")

    def test_voice_output(self, test_text="こんにちはだぎゅる♪ テスト音声です！"):
        """音声出力テスト"""
        try:
            print(f"🔊 音声テスト実行: {test_text}")
            self.speak_text(test_text)
            
        except Exception as e:
            print(f"❌ 音声テストエラー: {e}")

    def get_available_devices(self):
        """利用可能な音声デバイス一覧取得"""
        try:
            # 実際のデバイス検出はここに実装
            # 現在は仮のデバイス一覧を返す
            
            microphones = [
                "システムデフォルト",
                "内蔵マイク",
                "USB マイク",
                "Bluetooth ヘッドセット"
            ]
            
            speakers = [
                "システムデフォルト", 
                "内蔵スピーカー",
                "USB スピーカー",
                "Bluetooth ヘッドセット"
            ]
            
            return {
                'microphones': microphones,
                'speakers': speakers
            }
            
        except Exception as e:
            print(f"❌ デバイス取得エラー: {e}")
            return {
                'microphones': ["システムデフォルト"],
                'speakers': ["システムデフォルト"]
            }

    def update_device_settings(self, mic_device=None, speaker_device=None):
        """デバイス設定更新"""
        try:
            if mic_device:
                self.voice_settings['microphone_device'] = mic_device
                print(f"🎙️ マイクデバイス変更: {mic_device}")
                
            if speaker_device:
                self.voice_settings['speaker_device'] = speaker_device
                print(f"🔊 スピーカーデバイス変更: {speaker_device}")
                
            self.save_voice_settings()
            
        except Exception as e:
            print(f"❌ デバイス設定更新エラー: {e}")

    def update_volume(self, volume):
        """音量設定更新"""
        try:
            self.voice_settings['volume'] = max(0, min(100, volume))
            print(f"🔊 音量設定: {self.voice_settings['volume']}%")
            self.save_voice_settings()
            
        except Exception as e:
            print(f"❌ 音量設定エラー: {e}")

    def get_status(self):
        """現在のステータス取得"""
        return {
            'microphone': self.status['microphone'],
            'speaker': self.status['speaker'],
            'connection': self.status['connection'],
            'is_recording': self.is_recording,
            'is_speaking': self.is_speaking,
            'settings': self.voice_settings
        }

    def set_message_callback(self, callback):
        """メッセージコールバック設定"""
        self.message_callback = callback

    def stop(self):
        """ボイスチャット機能停止"""
        try:
            self.stop_voice_recognition()
            self.stop_speech()
            print("✅ ボイスチャット機能停止完了")
            
        except Exception as e:
            print(f"❌ ボイスチャット停止エラー: {e}")

class VoiceChatStatus:
    """ボイスチャット状態管理クラス"""
    
    def __init__(self):
        self.recording_time = 0
        self.total_messages = 0
        self.successful_recognitions = 0
        self.failed_recognitions = 0
        self.speech_count = 0
        
    def add_recognition_result(self, success=True):
        """音声認識結果を記録"""
        if success:
            self.successful_recognitions += 1
        else:
            self.failed_recognitions += 1
            
    def add_speech_event(self):
        """音声合成イベントを記録"""
        self.speech_count += 1
        
    def get_recognition_accuracy(self):
        """音声認識精度を取得"""
        total = self.successful_recognitions + self.failed_recognitions
        if total == 0:
            return 0.0
        return (self.successful_recognitions / total) * 100
        
    def get_statistics(self):
        """統計情報を取得"""
        return {
            'recording_time': self.recording_time,
            'total_messages': self.total_messages,
            'recognition_accuracy': self.get_recognition_accuracy(),
            'speech_count': self.speech_count
        }