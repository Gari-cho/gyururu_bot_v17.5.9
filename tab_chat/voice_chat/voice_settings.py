"""
ボイスチャット機能の設定管理クラス

機能:
- 音声デバイス設定
- 音声認識設定  
- 音声合成設定
- 詳細パラメータ調整
"""

import json
import os
from datetime import datetime

class VoiceSettings:
    """音声設定管理クラス"""
    
    def __init__(self, settings_file="voice_settings.json"):
        self.settings_file = settings_file
        self.settings = self._load_default_settings()
        self.load_settings()
        
    def _load_default_settings(self):
        """デフォルト設定を読み込み"""
        return {
            # === デバイス設定 ===
            'microphone_device': 'default',
            'speaker_device': 'default',
            'microphone_sensitivity': 50,  # 0-100
            'speaker_volume': 70,         # 0-100
            
            # === 音声認識設定 ===
            'recognition_language': 'ja-JP',
            'recognition_engine': 'google',  # google, azure, local
            'recognition_continuous': True,
            'recognition_timeout': 5.0,
            'noise_reduction': True,
            'voice_activity_detection': True,
            
            # === 音声合成設定 ===
            'tts_engine': 'system',  # system, google, azure, voicevox
            'tts_voice': 'default',
            'tts_speed': 1.0,       # 0.5-2.0
            'tts_pitch': 1.0,       # 0.5-2.0
            'tts_volume': 80,       # 0-100
            
            # === ぎゅるる専用設定 ===
            'gyururu_voice_effects': True,
            'gyururu_pitch_variation': 0.2,
            'gyururu_speed_variation': 0.1,
            'add_gyururu_suffix': True,    # "だぎゅる"を自動追加
            
            # === 動作設定 ===
            'auto_response': True,
            'response_delay': 0.5,         # 秒
            'max_recording_duration': 30,  # 秒
            'auto_stop_silence': 3.0,      # 秒
            
            # === UI設定 ===
            'show_recognition_text': True,
            'show_waveform': False,
            'visual_feedback': True,
            
            # === 高度設定 ===
            'sample_rate': 16000,
            'bit_depth': 16,
            'channels': 1,
            'buffer_size': 1024,
            
            # === 統計・ログ ===
            'save_recognition_log': False,
            'save_speech_log': False,
            'statistics_enabled': True
        }

    def load_settings(self):
        """設定ファイルから読み込み"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    # デフォルト設定に保存された設定をマージ
                    self.settings.update(saved_settings)
                    print(f"✅ 音声設定読み込み完了: {self.settings_file}")
            else:
                print(f"⚠️ 設定ファイルが見つかりません。デフォルト設定を使用: {self.settings_file}")
                self.save_settings()  # デフォルト設定を保存
                
        except Exception as e:
            print(f"❌ 設定読み込みエラー: {e}")
            print("⚠️ デフォルト設定を使用します")

    def save_settings(self):
        """設定をファイルに保存"""
        try:
            # バックアップ作成
            if os.path.exists(self.settings_file):
                backup_file = f"{self.settings_file}.backup"
                os.rename(self.settings_file, backup_file)
                
            # 設定保存
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
                
            print(f"✅ 音声設定保存完了: {self.settings_file}")
            
        except Exception as e:
            print(f"❌ 設定保存エラー: {e}")

    def get(self, key, default=None):
        """設定値を取得"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """設定値を更新"""
        try:
            old_value = self.settings.get(key)
            self.settings[key] = value
            
            print(f"🔧 設定更新: {key} = {value} (旧値: {old_value})")
            
            # 重要な設定変更時は自動保存
            if key in ['microphone_device', 'speaker_device', 'recognition_language']:
                self.save_settings()
                
        except Exception as e:
            print(f"❌ 設定更新エラー: {e}")

    def update_multiple(self, settings_dict):
        """複数設定を一括更新"""
        try:
            for key, value in settings_dict.items():
                if key in self.settings:
                    self.settings[key] = value
                    print(f"🔧 設定更新: {key} = {value}")
                else:
                    print(f"⚠️ 未知の設定キー: {key}")
                    
        except Exception as e:
            print(f"❌ 一括設定更新エラー: {e}")

    def reset_to_default(self):
        """デフォルト設定にリセット"""
        try:
            self.settings = self._load_default_settings()
            self.save_settings()
            print("✅ 設定をデフォルトにリセットしました")
            
        except Exception as e:
            print(f"❌ 設定リセットエラー: {e}")

    def export_settings(self, export_file):
        """設定をエクスポート"""
        try:
            export_data = {
                'settings': self.settings,
                'export_time': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            print(f"✅ 設定エクスポート完了: {export_file}")
            
        except Exception as e:
            print(f"❌ 設定エクスポートエラー: {e}")

    def import_settings(self, import_file):
        """設定をインポート"""
        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
                
            if 'settings' in import_data:
                # 既存設定をバックアップ
                backup_settings = self.settings.copy()
                
                try:
                    self.settings.update(import_data['settings'])
                    self.save_settings()
                    print(f"✅ 設定インポート完了: {import_file}")
                    
                except Exception as e:
                    # インポートエラー時はバックアップから復元
                    self.settings = backup_settings
                    raise e
            else:
                raise ValueError("不正な設定ファイル形式")
                
        except Exception as e:
            print(f"❌ 設定インポートエラー: {e}")

    def get_device_settings(self):
        """デバイス関連設定を取得"""
        return {
            'microphone_device': self.get('microphone_device'),
            'speaker_device': self.get('speaker_device'),
            'microphone_sensitivity': self.get('microphone_sensitivity'),
            'speaker_volume': self.get('speaker_volume')
        }

    def get_recognition_settings(self):
        """音声認識関連設定を取得"""
        return {
            'language': self.get('recognition_language'),
            'engine': self.get('recognition_engine'),
            'continuous': self.get('recognition_continuous'),
            'timeout': self.get('recognition_timeout'),
            'noise_reduction': self.get('noise_reduction'),
            'voice_activity_detection': self.get('voice_activity_detection')
        }

    def get_tts_settings(self):
        """音声合成関連設定を取得"""
        return {
            'engine': self.get('tts_engine'),
            'voice': self.get('tts_voice'),
            'speed': self.get('tts_speed'),
            'pitch': self.get('tts_pitch'),
            'volume': self.get('tts_volume')
        }

    def get_gyururu_settings(self):
        """ぎゅるる専用設定を取得"""
        return {
            'voice_effects': self.get('gyururu_voice_effects'),
            'pitch_variation': self.get('gyururu_pitch_variation'),
            'speed_variation': self.get('gyururu_speed_variation'),
            'add_suffix': self.get('add_gyururu_suffix')
        }

    def validate_settings(self):
        """設定値の妥当性チェック"""
        errors = []
        
        # 数値範囲チェック
        numeric_ranges = {
            'microphone_sensitivity': (0, 100),
            'speaker_volume': (0, 100),
            'tts_speed': (0.1, 3.0),
            'tts_pitch': (0.1, 3.0),
            'tts_volume': (0, 100),
            'response_delay': (0, 10),
            'max_recording_duration': (1, 300),
            'auto_stop_silence': (0.5, 30)
        }
        
        for key, (min_val, max_val) in numeric_ranges.items():
            value = self.get(key)
            if value is not None and not (min_val <= value <= max_val):
                errors.append(f"{key} は {min_val}-{max_val} の範囲で設定してください (現在値: {value})")
        
        # 文字列選択肢チェック
        choice_options = {
            'recognition_language': ['ja-JP', 'en-US', 'zh-CN'],
            'recognition_engine': ['google', 'azure', 'local'],
            'tts_engine': ['system', 'google', 'azure', 'voicevox']
        }
        
        for key, options in choice_options.items():
            value = self.get(key)
            if value is not None and value not in options:
                errors.append(f"{key} は {options} から選択してください (現在値: {value})")
        
        return errors

    def apply_gyururu_effects(self, text):
        """ぎゅるる効果をテキストに適用"""
        if not self.get('gyururu_voice_effects'):
            return text
            
        processed_text = text
        
        # "だぎゅる"接尾辞を追加
        if self.get('add_gyururu_suffix') and not processed_text.endswith(('だぎゅる', 'ぎゅる')):
            if processed_text.endswith('。'):
                processed_text = processed_text[:-1] + 'だぎゅる。'
            elif processed_text.endswith(('!', '！')):
                processed_text = processed_text[:-1] + 'だぎゅる！'
            else:
                processed_text += 'だぎゅる♪'
        
        return processed_text

    def get_all_settings(self):
        """全設定を取得"""
        return self.settings.copy()

    def __str__(self):
        """設定の文字列表現"""
        return f"VoiceSettings({len(self.settings)} items)"

    def __repr__(self):
        """設定の詳細表現"""
        return f"VoiceSettings(file='{self.settings_file}', items={len(self.settings)})"