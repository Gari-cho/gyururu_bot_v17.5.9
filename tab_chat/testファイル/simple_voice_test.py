#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
繝・せ繝育畑髻ｳ螢ｰ騾｣謳ｺ繧ｷ繧ｹ繝・Β - simple_voice_test.py
縺ｨ繧翫≠縺医★菴輔°縺励ｉ縺ｮ髻ｳ螢ｰ縺ｧ隱ｭ縺ｿ荳翫￡縺後〒縺阪ｌ縺ｰOK迚・"""

import os
import subprocess
import threading
import time

class SimpleVoiceManager:
    """繧ｷ繝ｳ繝励Ν髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ・医ユ繧ｹ繝育畑・・""
    
    def __init__(self):
        self.voice_engines = []
        self.current_engine = None
        
        # 蛻ｩ逕ｨ蜿ｯ閭ｽ縺ｪ髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ繧呈､懷・
        self._detect_available_engines()
        
        print(f"笨・髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ蛻晄悄蛹門ｮ御ｺ・)
        print(f"矧 蛻ｩ逕ｨ蜿ｯ閭ｽ繧ｨ繝ｳ繧ｸ繝ｳ: {', '.join(self.voice_engines) if self.voice_engines else '縺ｪ縺・}")
        print(f"識 驕ｸ謚槭お繝ｳ繧ｸ繝ｳ: {self.current_engine}")

    def _detect_available_engines(self):
        """蛻ｩ逕ｨ蜿ｯ閭ｽ縺ｪ髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ繧呈､懷・"""
        # 1. VOICEVOX 繝√ぉ繝・け
        try:
            import requests
            response = requests.get("http://localhost:50021/docs", timeout=2)
            if response.status_code == 200:
                self.voice_engines.append("voicevox")
                if not self.current_engine:
                    self.current_engine = "voicevox"
                print("矧 VOICEVOX: 蛻ｩ逕ｨ蜿ｯ閭ｽ")
        except:
            print("笶・VOICEVOX: 蛻ｩ逕ｨ荳榊庄")

        # 2. 譽定ｪｭ縺ｿ縺｡繧・ｓ 繝√ぉ繝・け
        try:
            import requests
            response = requests.get("http://localhost:50080/talk?text=test", timeout=2)
            if response.status_code == 200:
                self.voice_engines.append("bouyomi")
                if not self.current_engine:
                    self.current_engine = "bouyomi"
                print("矧 譽定ｪｭ縺ｿ縺｡繧・ｓ: 蛻ｩ逕ｨ蜿ｯ閭ｽ")
        except:
            print("笶・譽定ｪｭ縺ｿ縺｡繧・ｓ: 蛻ｩ逕ｨ荳榊庄")

        # 3. Windows繧ｷ繧ｹ繝・Β髻ｳ螢ｰ 繝√ぉ繝・け
        if os.name == 'nt':
            try:
                import win32com.client
                self.voice_engines.append("windows")
                if not self.current_engine:
                    self.current_engine = "windows"
                print("矧 Windows髻ｳ螢ｰ: 蛻ｩ逕ｨ蜿ｯ閭ｽ")
            except ImportError:
                print("笶・Windows髻ｳ螢ｰ: win32com譛ｪ繧､繝ｳ繧ｹ繝医・繝ｫ")
        
        # 4. 繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ・医Ο繧ｰ蜃ｺ蜉帙・縺ｿ・・        if not self.voice_engines:
            self.voice_engines.append("log")
            self.current_engine = "log"
            print("笞・・髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ縺ｪ縺・- 繝ｭ繧ｰ蜃ｺ蜉帙・縺ｿ")

    def speak(self, text: str, engine: str = None) -> bool:
        """髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡螳溯｡・""
        try:
            target_engine = engine or self.current_engine
            
            if not target_engine:
                print(f"笶・蛻ｩ逕ｨ蜿ｯ閭ｽ縺ｪ髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ縺後≠繧翫∪縺帙ｓ")
                return False
            
            print(f"矧 髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡髢句ｧ・ {text[:30]}... (繧ｨ繝ｳ繧ｸ繝ｳ: {target_engine})")
            
            # 髱槫酔譛溘〒髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡螳溯｡・            def speak_async():
                if target_engine == "voicevox":
                    self._speak_voicevox(text)
                elif target_engine == "bouyomi":
                    self._speak_bouyomi(text)
                elif target_engine == "windows":
                    self._speak_windows(text)
                else:
                    self._speak_log(text)
            
            # 蛻･繧ｹ繝ｬ繝・ラ縺ｧ螳溯｡鯉ｼ医ヶ繝ｭ繝・け繧帝∩縺代ｋ・・            threading.Thread(target=speak_async, daemon=True).start()
            return True
            
        except Exception as e:
            print(f"笶・髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡繧ｨ繝ｩ繝ｼ: {e}")
            return False

    def _speak_voicevox(self, text: str):
        """VOICEVOX髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡"""
        try:
            import requests
            
            # 髻ｳ螢ｰ繧ｯ繧ｨ繝ｪ菴懈・
            query_response = requests.post(
                "http://localhost:50021/audio_query",
                params={'text': text, 'speaker': 1},
                timeout=10
            )
            
            if query_response.status_code == 200:
                audio_query = query_response.json()
                
                # 髻ｳ螢ｰ蜷域・
                synthesis_response = requests.post(
                    "http://localhost:50021/synthesis",
                    params={'speaker': 1},
                    json=audio_query,
                    timeout=15
                )
                
                if synthesis_response.status_code == 200:
                    # 髻ｳ螢ｰ蜀咲函・郁､・焚縺ｮ譁ｹ豕輔ｒ隧ｦ陦鯉ｼ・                    self._play_audio_bytes(synthesis_response.content)
                    print(f"笨・VOICEVOX隱ｭ縺ｿ荳翫￡螳御ｺ・ {text[:20]}...")
                    return True
            
            print(f"笶・VOICEVOX隱ｭ縺ｿ荳翫￡螟ｱ謨・)
            return False
            
        except Exception as e:
            print(f"笶・VOICEVOX隱ｭ縺ｿ荳翫￡繧ｨ繝ｩ繝ｼ: {e}")
            return False

    def _speak_bouyomi(self, text: str):
        """譽定ｪｭ縺ｿ縺｡繧・ｓ髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡"""
        try:
            import requests
            
            response = requests.get(
                "http://localhost:50080/talk",
                params={
                    'text': text,
                    'voice': 0,
                    'volume': 80,
                    'speed': 100,
                    'tone': 100
                },
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"笨・譽定ｪｭ縺ｿ縺｡繧・ｓ隱ｭ縺ｿ荳翫￡螳御ｺ・ {text[:20]}...")
                return True
            else:
                print(f"笶・譽定ｪｭ縺ｿ縺｡繧・ｓ隱ｭ縺ｿ荳翫￡螟ｱ謨・ {response.status_code}")
                return False
                
        except Exception as e:
            print(f"笶・譽定ｪｭ縺ｿ縺｡繧・ｓ隱ｭ縺ｿ荳翫￡繧ｨ繝ｩ繝ｼ: {e}")
            return False

    def _speak_windows(self, text: str):
        """Windows髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡"""
        try:
            import win32com.client
            
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(text)
            
            print(f"笨・Windows髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡螳御ｺ・ {text[:20]}...")
            return True
            
        except Exception as e:
            print(f"笶・Windows髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡繧ｨ繝ｩ繝ｼ: {e}")
            return False

    def _speak_log(self, text: str):
        """繝ｭ繧ｰ蜃ｺ蜉帙・縺ｿ・医ヵ繧ｩ繝ｼ繝ｫ繝舌ャ繧ｯ・・""
        print(f"矧 [髻ｳ螢ｰ] {text}")
        return True

    def _play_audio_bytes(self, audio_bytes: bytes):
        """髻ｳ螢ｰ繝舌う繝医ョ繝ｼ繧ｿ繧貞・逕滂ｼ郁､・焚謇区ｳ輔ｒ隧ｦ陦鯉ｼ・""
        try:
            # 譁ｹ豕・: pygame菴ｿ逕ｨ
            try:
                import pygame
                import io
                
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                
                sound = pygame.mixer.Sound(io.BytesIO(audio_bytes))
                sound.play()
                return True
            except ImportError:
                pass
            
            # 譁ｹ豕・: winsound菴ｿ逕ｨ・・indows・・            if os.name == 'nt':
                try:
                    import winsound
                    import tempfile
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                        temp_file.write(audio_bytes)
                        temp_path = temp_file.name
                    
                    winsound.PlaySound(temp_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    
                    # 3遘貞ｾ後↓荳譎ゅヵ繧｡繧､繝ｫ蜑企勁
                    def cleanup():
                        time.sleep(3)
                        try:
                            os.unlink(temp_path)
                        except:
                            pass
                    
                    threading.Thread(target=cleanup, daemon=True).start()
                    return True
                except ImportError:
                    pass
            
            # 譁ｹ豕・: 螟夜Κ繝励Ξ繝ｼ繝､繝ｼ菴ｿ逕ｨ
            try:
                import tempfile
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(audio_bytes)
                    temp_path = temp_file.name
                
                if os.name == 'nt':
                    # Windows: 髢｢騾｣莉倥￠繧峨ｌ縺溘い繝励Μ縺ｧ蜀咲函・医し繧､繝ｬ繝ｳ繝茨ｼ・                    subprocess.run(['start', '/MIN', temp_path], shell=True, 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Linux/Mac
                    subprocess.run(['xdg-open', temp_path], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                return True
                
            except Exception as e:
                print(f"笞・・螟夜Κ繝励Ξ繝ｼ繝､繝ｼ蜀咲函螟ｱ謨・ {e}")
            
            return False
            
        except Exception as e:
            print(f"笶・髻ｳ螢ｰ蜀咲函繧ｨ繝ｩ繝ｼ: {e}")
            return False

    def test_voice(self):
        """髻ｳ螢ｰ繝・せ繝亥ｮ溯｡・""
        test_texts = [
            "縺薙ｓ縺ｫ縺｡縺ｯ縲・浹螢ｰ繝・せ繝医〒縺・,
            "VOICEVOX騾｣謳ｺ繝・せ繝井ｸｭ",
            "繧ｷ繧ｹ繝・Β豁｣蟶ｸ蜍穂ｽ懃｢ｺ隱・
        ]
        
        print("ｧｪ 髻ｳ螢ｰ繝・せ繝磯幕蟋・..")
        
        for i, text in enumerate(test_texts, 1):
            print(f"ｧｪ 繝・せ繝・{i}: {text}")
            success = self.speak(text)
            
            if success:
                print(f"笨・繝・せ繝・{i} 謌仙粥")
            else:
                print(f"笶・繝・せ繝・{i} 螟ｱ謨・)
            
            time.sleep(2)  # 2遘帝俣髫・        
        print("笨・髻ｳ螢ｰ繝・せ繝亥ｮ御ｺ・)

    def get_available_engines(self) -> list:
        """蛻ｩ逕ｨ蜿ｯ閭ｽ繧ｨ繝ｳ繧ｸ繝ｳ荳隕ｧ蜿門ｾ・""
        return self.voice_engines.copy()

    def set_engine(self, engine: str) -> bool:
        """髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ繧定ｨｭ螳・""
        if engine in self.voice_engines:
            self.current_engine = engine
            print(f"肌 髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ螟画峩: {engine}")
            return True
        else:
            print(f"笶・蛻ｩ逕ｨ縺ｧ縺阪↑縺・浹螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ: {engine}")
            return False


# 繝・せ繝亥ｮ溯｡・def test_simple_voice_manager():
    """繝・せ繝育畑髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ縺ｮ繝・せ繝・""
    print("ｧｪ 繝・せ繝育畑髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ 繝・せ繝磯幕蟋・)
    print("=" * 50)
    
    # 髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ菴懈・
    voice_manager = SimpleVoiceManager()
    
    # 蛻ｩ逕ｨ蜿ｯ閭ｽ繧ｨ繝ｳ繧ｸ繝ｳ遒ｺ隱・    engines = voice_manager.get_available_engines()
    print(f"投 蛻ｩ逕ｨ蜿ｯ閭ｽ繧ｨ繝ｳ繧ｸ繝ｳ謨ｰ: {len(engines)}")
    
    if engines:
        # 蜷・お繝ｳ繧ｸ繝ｳ縺ｧ繝・せ繝・        for engine in engines[:2]:  # 譛蛻昴・2縺､縺ｮ繧ｨ繝ｳ繧ｸ繝ｳ縺ｧ繝・せ繝・            print(f"\n肌 繧ｨ繝ｳ繧ｸ繝ｳ蛻・崛: {engine}")
            voice_manager.set_engine(engine)
            
            test_text = f"{engine}縺ｧ縺ｮ髻ｳ螢ｰ繝・せ繝医〒縺・
            success = voice_manager.speak(test_text)
            
            if success:
                print(f"笨・{engine} 繝・せ繝域・蜉・)
                time.sleep(3)  # 髻ｳ螢ｰ蜀咲函螳御ｺ・ｾ・■
            else:
                print(f"笶・{engine} 繝・せ繝亥､ｱ謨・)
        
        print(f"\n笨・髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ繝・せ繝亥ｮ御ｺ・)
        return voice_manager
    else:
        print("笶・蛻ｩ逕ｨ蜿ｯ閭ｽ縺ｪ髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ縺後≠繧翫∪縺帙ｓ")
        return None


if __name__ == "__main__":
    test_simple_voice_manager()
