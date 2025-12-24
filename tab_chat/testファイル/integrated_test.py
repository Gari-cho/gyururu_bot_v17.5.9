#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OneComme + 髻ｳ螢ｰ騾｣謳ｺ邨ｱ蜷医ユ繧ｹ繝・- integrated_test.py
繧ｷ繝ｳ繝励Ν縺ｪ髻ｳ螢ｰ騾｣謳ｺ縺ｧ縺ｨ繧翫≠縺医★蜍穂ｽ懃｢ｺ隱・"""

import sys
import os
from pathlib import Path
import time

# 繝代せ險ｭ螳・current_dir = Path.cwd()
sys.path.insert(0, str(current_dir))

def main():
    print("ｧｪ OneComme + 髻ｳ螢ｰ騾｣謳ｺ邨ｱ蜷医ユ繧ｹ繝・)
    print("=" * 50)
    
    try:
        # 1. 髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ繝・せ繝・        print("矧 髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ繝・せ繝・..")
        from simple_voice_test import SimpleVoiceManager
        
        voice_manager = SimpleVoiceManager()
        available_engines = voice_manager.get_available_engines()
        
        print(f"投 蛻ｩ逕ｨ蜿ｯ閭ｽ髻ｳ螢ｰ繧ｨ繝ｳ繧ｸ繝ｳ: {available_engines}")
        
        if available_engines:
            # 邁｡蜊倥↑髻ｳ螢ｰ繝・せ繝・            voice_manager.speak("髻ｳ螢ｰ繝・せ繝磯幕蟋・)
            time.sleep(2)
        
        # 2. OneComme邨ｱ蜷医す繧ｹ繝・Β繝・せ繝茨ｼ磯浹螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ莉倥″・・        print("\n藤 OneComme邨ｱ蜷医す繧ｹ繝・Β繝・せ繝茨ｼ磯浹螢ｰ騾｣謳ｺ莉倥″・・..")
        
        # 繝√Ε繝・ヨ陦ｨ遉ｺ繝｢繝・け
        class TestChatDisplay:
            def __init__(self):
                self.messages = []
            
            def add_message(self, sender, message, msg_type):
                formatted_msg = f"[{msg_type}] {sender}: {message}"
                self.messages.append(formatted_msg)
                print(f"町 繝√Ε繝・ヨ: {formatted_msg}")
            
            def add_formatted_message(self, message_data):
                emoji = message_data.get('service_emoji', '笞ｪ')
                username = message_data.get('username', 'Unknown')
                message = message_data.get('message', '')
                formatted = f"{emoji} {username}: {message}"
                self.messages.append(formatted)
                print(f"町 繝√Ε繝・ヨ: {formatted}")
        
        # OneComme邨ｱ蜷医す繧ｹ繝・Β・磯浹螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ莉倥″・我ｽ懈・
        from tab_chat.onecomme_integration import OneCommeIntegration
        
        chat_display = TestChatDisplay()
        # 髻ｳ螢ｰ繝槭ロ繝ｼ繧ｸ繝｣繝ｼ繧堤ｵｱ蜷医す繧ｹ繝・Β縺ｫ貂｡縺・        integration = OneCommeIntegration(
            chat_display=chat_display, 
            voice_manager=voice_manager if available_engines else None
        )
        
        print(f"笨・OneComme邨ｱ蜷医す繧ｹ繝・Β蛻晄悄蛹門ｮ御ｺ・)
        
        # 3. 邨ｱ蜷医ユ繧ｹ繝亥ｮ溯｡・        print("\nｧｪ 邨ｱ蜷医ユ繧ｹ繝亥ｮ溯｡・..")
        
        # 繝・せ繝医さ繝｡繝ｳ繝茨ｼ磯浹螢ｰ隱ｭ縺ｿ荳翫￡莉倥″・・        test_comments = [
            "[YouTube] 繝・せ繝・: 縺薙ｓ縺ｫ縺｡縺ｯ縺縺弱ｅ繧具ｼ・,
            "[Twitch] 繝・せ繝・: 髻ｳ螢ｰ繝・せ繝井ｸｭ縺ｧ縺・,
            "[繝・う繧ｭ繝｣繧ｹ] 繝・せ繝・: 繧ｷ繧ｹ繝・Β豁｣蟶ｸ蜍穂ｽ應ｸｭ"
        ]
        
        for i, comment in enumerate(test_comments, 1):
            print(f"\nｧｪ 邨ｱ蜷医ユ繧ｹ繝・{i}: {comment}")
            
            # 繧ｳ繝｡繝ｳ繝亥・逅・ｼ医メ繝｣繝・ヨ陦ｨ遉ｺ + 髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡・・            success = integration._process_comment_line(comment)
            
            if success:
                print(f"笨・邨ｱ蜷医ユ繧ｹ繝・{i} 謌仙粥")
            else:
                print(f"笶・邨ｱ蜷医ユ繧ｹ繝・{i} 螟ｱ謨・)
            
            time.sleep(3)  # 髻ｳ螢ｰ蜀咲函螳御ｺ・ｾ・■
        
        # 4. 邨ｱ險育｢ｺ隱・        print("\n投 邨ｱ蜷医ユ繧ｹ繝育ｵ先棡...")
        stats = integration.get_statistics()
        
        print(f"邱上さ繝｡繝ｳ繝域焚: {stats['total_comments']}")
        print(f"隱ｭ縺ｿ荳翫￡謨ｰ: {stats['read_comments']}")
        print(f"繝√Ε繝・ヨ蜿嶺ｿ｡謨ｰ: {len(chat_display.messages)}")
        
        # 5. 謌仙粥蛻､螳・        if stats['total_comments'] > 0 and len(chat_display.messages) > 0:
            print("\n脂 邨ｱ蜷医ユ繧ｹ繝域・蜉・")
            print("笨・OneComme 竊・繝√Ε繝・ヨ陦ｨ遉ｺ: OK")
            print(f"笨・髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡: {'OK' if stats['read_comments'] > 0 else '繧ｹ繧ｭ繝・・'}")
            
            print("\n噫 谺｡縺ｮ繧ｹ繝・ャ繝・")
            print("   1. python tab_chat/app.py 縺ｧ繝｡繧､繝ｳ繧｢繝励Μ襍ｷ蜍・)
            print("   2. OneComme邨ｱ蜷医メ繝｣繝・ヨ繧ｿ繝悶ｒ髢九￥")
            print("   3. 螳滄圀縺ｮ繧上ｓ繧ｳ繝｡繝輔ぃ繧､繝ｫ繧定ｨｭ螳・)
            print("   4. 繝ｪ繧｢繝ｫ繧ｿ繧､繝逶｣隕悶ｒ髢句ｧ・)
            
            return True
        else:
            print("\n笶・邨ｱ蜷医ユ繧ｹ繝亥､ｱ謨・)
            return False
            
    except Exception as e:
        print(f"\n笶・邨ｱ蜷医ユ繧ｹ繝医お繝ｩ繝ｼ: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 繧ｯ繝ｪ繝ｼ繝ｳ繧｢繝・・
        try:
            integration.stop()
        except:
            pass

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n識 邨ｱ蜷医す繧ｹ繝・Β貅門ｙ螳御ｺ・")
    else:
        print("\n笞・・蝠城｡後ｒ菫ｮ豁｣縺励※縺九ｉ蜀榊ｮ溯｡後＠縺ｦ縺上□縺輔＞")
