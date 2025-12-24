#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIとチャチE��タチEPhase4 安�E化テストスクリプト (完�E牁E
フォールバック削除 + エラー修正の確認用
"""

import tkinter as tk
from tkinter import messagebox
import logging
import traceback
import sys
import os
from pathlib import Path

# パス設宁Ecurrent_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# ログ設宁Elogging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_import_safety():
    """インポ�Eト安�E性チE��チE""
    print("🧪 Phase4 安�E化テスト開姁E..")
    print("=" * 50)
    
    try:
        # 1. __init__.py チE��チE        print("1. __init__.py インポ�EトテスチE)
        try:
            from tab_chat import create_integrated_ai_chat_tab
            print("✁Ecreate_integrated_ai_chat_tab インポ�Eト�E劁E)
            
            # フォールバック関数が削除されてぁE��かチェチE��
            try:
                from tab_chat import create_chat_tab
                print("❁Ecreate_chat_tab がまだ存在します（削除されてぁE��せん�E�E)
                return False
            except ImportError:
                print("✁Ecreate_chat_tab 正常に削除済み")
                
        except ImportError as e:
            print(f"❁E__init__.py インポ�Eトエラー: {e}")
            return False
        
        # 2. AI ConnectorチE��チE        print("\n2. AI Connector 安�E性チE��チE)
        try:
            from tab_chat.gyururu_ai_connector_v15 import GyururuAIConnector
            
            # None botでの初期化テスチE            connector = GyururuAIConnector(bot_instance=None)
            print("✁EAIConnector None bot初期化�E劁E)
            
            # 設定読み込みチE��チE            ai_settings = connector._load_ai_settings()
            if ai_settings and isinstance(ai_settings, dict):
                print("✁EAI設定読み込み安�E")
            else:
                print("❁EAI設定読み込み失敁E)
                
            character_info = connector._load_character_info()
            if character_info and isinstance(character_info, dict):
                print("✁Eキャラクター惁E��読み込み安�E")
            else:
                print("❁Eキャラクター惁E��読み込み失敁E)
                
        except Exception as e:
            print(f"❁EAI Connector チE��トエラー: {e}")
            traceback.print_exc()
            return False
        
        # 3. 統合タブ作�EチE��チE        print("\n3. 統合タブ作�EチE��チE)
        try:
            # チE��ト用ルートウィンドウ
            test_root = tk.Tk()
            test_root.withdraw()  # 非表示
            
            # タブ作�EチE��チE            tab_instance = create_integrated_ai_chat_tab(test_root)
            print("✁E統吁EIチャチE��タブ作�E成功")
            
            # 基本メソチE��存在チェチE��
            required_methods = [
                'add_external_comment',
                'add_message', 
                'set_ai_available',
                'get_stats',
                'get_chat_history',
                'cleanup'
            ]
            
            missing_methods = []
            for method in required_methods:
                if not hasattr(tab_instance, method):
                    missing_methods.append(method)
            
            if missing_methods:
                print(f"❁E忁E��メソチE��が不足: {missing_methods}")
                return False
            else:
                print("✁E忁E��メソチE��全て存在")
            
            # クリーンアチE�EチE��チE            try:
                tab_instance.cleanup()
                print("✁EクリーンアチE�E実行�E劁E)
            except Exception as e:
                print(f"⚠�E�EクリーンアチE�E警呁E {e}")
            
            test_root.destroy()
            
        except Exception as e:
            print(f"❁E統合タブ作�EチE��トエラー: {e}")
            traceback.print_exc()
            return False
        
        print("\n" + "=" * 50)
        print("✁EPhase4 安�E化テスチE全て成功!")
        return True
        
    except Exception as e:
        print(f"❁EチE��ト実行エラー: {e}")
        traceback.print_exc()
        return False

def test_error_handling():
    """エラーハンドリングチE��チE""
    print("\n🛡�E�EエラーハンドリングチE��ト開姁E..")
    
    try:
        from tab_chat.gyururu_ai_connector_v15 import GyururuAIConnector
        
        # 1. 異常なbot instanceでの初期匁E        class FakeBadBot:
            def __init__(self):
                self.config_manager = None  # None設宁E        
        bad_bot = FakeBadBot()
        connector = GyururuAIConnector(bad_bot)
        
        # 設定読み込みがエラーで落ちなぁE��チE��チE        settings = connector._load_ai_settings()
        if settings:
            print("✁E異常bot でも設定読み込み安�E")
        
        # 2. API KEY取得テスチE        api_key = connector._get_api_key()
        print(f"✁EAPI KEY取得�E琁E���E (結果: {'あり' if api_key else 'なぁE})")
        
        # 3. フォールバック応答テスチE        fallback = connector.get_fallback_response({"comment": "チE��チE, "username": "test"})
        if fallback:
            print("✁Eフォールバック応答生成安�E")
        
        print("✁EエラーハンドリングチE��ト�E劁E)
        return True
        
    except Exception as e:
        print(f"❁EエラーハンドリングチE��トエラー: {e}")
        traceback.print_exc()
        return False

def run_gui_test():
    """GUI統合テスチE""
    print("\n🖼�E�EGUI統合テスト開姁E..")
    
    try:
        root = tk.Tk()
        root.title("Phase4 安�E匁EGUI チE��チE)
        root.geometry("800x600")
        
        # 統合タブ作�E
        from tab_chat import create_integrated_ai_chat_tab
        tab = create_integrated_ai_chat_tab(root)
        
        # チE��トメチE��ージ追加
        test_messages = [
            ("🧪 Phase4安�E化テスト開姁E, "system"),
            ("フォールバック機�E削除完亁E, "system"),
            ("エラーハンドリング強化完亁E, "system"),
        ]
        
        for message, msg_type in test_messages:
            tab.add_message(message, msg_type)
        
        # チE��トコメント追加
        test_comments = [
            ("こんにちは�E�テスト中でぁE, "チE��トユーザー1", "youtube"),
            ("Phase4チE��トコメンチE, "チE��トユーザー2", "twitch"),
            ("安�E化確認中", "チE��トユーザー3", "twitcasting")
        ]
        
        for comment, username, platform in test_comments:
            tab.add_external_comment(comment, username, platform)
        
        # 統計情報確誁E        stats = tab.get_stats()
        print(f"📊 統計情報取征E {'成功' if stats else '失敁E}")
        
        # チャチE��履歴確誁E        history = tab.get_chat_history()
        print(f"📜 チャチE��履歴取征E {len(history) if history else 0}件")
        
        print("✁EGUI統合テスト�E劁E- ウィンドウを閉じてチE��ト完亁E��てください")
        
        def on_closing():
            try:
                tab.cleanup()
                root.destroy()
                print("✁EGUI クリーンアチE�E完亁E)
            except Exception as e:
                print(f"⚠�E�EGUI クリーンアチE�E警呁E {e}")
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
        
        return True
        
    except Exception as e:
        print(f"❁EGUI統合テストエラー: {e}")
        traceback.print_exc()
        return False

def create_backup():
    """バックアチE�Eファイル作�E"""
    print("💾 バックアチE�Eファイル作�E中...")
    
    files_to_backup = [
        "tab_chat/__init__.py",
        "tab_chat/app.py",
        "tab_chat/gyururu_ai_connector_v15.py",
        "tab_chat/chat_display.py",
        "tab_chat/connection_manager.py"
    ]
    
    backup_count = 0
    for file_path in files_to_backup:
        try:
            original = Path(file_path)
            if original.exists():
                backup = Path(f"{file_path}.phase4_backup")
                backup.write_text(original.read_text(encoding='utf-8'), encoding='utf-8')
                print(f"✁E{file_path} バックアチE�E作�E")
                backup_count += 1
        except Exception as e:
            print(f"⚠�E�E{file_path} バックアチE�E失敁E {e}")
    
    print(f"📦 バックアチE�E完亁E {backup_count}/{len(files_to_backup)} ファイル")
    return backup_count > 0

def show_modification_guide():
    """修正ガイド表示"""
    print("\n📝 Phase4 修正ガイチE)
    print("=" * 50)
    
    guide_text = """
🔧 修正対象ファイルと場所:

1. tab_chat/__init__.py
   ↁE全体を新しいバ�Eジョンに置き換ぁE
2. tab_chat/app.py
   ↁE_initialize メソチE��を安�E版に置き換ぁE   ↁE_setup_ui_safe, _initialize_managers_safe メソチE��を追加
   ↁE外部アクセスメソチE��を安�E版に置き換ぁE   ↁEcreate_chat_tab 関数を削除

3. tab_chat/gyururu_ai_connector_v15.py
   ↁE_load_ai_settings メソチE��を安�E版に置き換ぁE   ↁE_load_character_info メソチE��を安�E版に置き換ぁE   ↁE_get_api_key メソチE��を安�E版に置き換ぁE
4. tab_chat/chat_display.py
   ↁE_add_chat_message メソチE��を安�E版に置き換ぁE   ↁEupdate_connection_info メソチE��を安�E版に置き換ぁE   ↁEupdate_ai_info メソチE��を安�E版に置き換ぁE   ↁEupdate_stats メソチE��を安�E版に置き換ぁE
5. tab_chat/connection_manager.py
   ↁE_on_wancome_comment メソチE��を安�E版に置き換ぁE   ↁE_on_platform_comment メソチE��を安�E版に置き換ぁE   ↁE_on_superchat_received メソチE��を安�E版に置き換ぁE   ↁE_update_connection_info メソチE��を安�E版に置き換ぁE   ↁE新しいヘルパ�EメソチE��3つを追加

⚠�E�E注愁E バックアチE�Eを作�Eしてから修正してください
✁E修正征E python phase4_test_script.py でチE��ト実衁E    """
    
    print(guide_text)

def main():
    """メインチE��ト実衁E""
    print("🎮 AIとチャチE��タチEPhase4 安�E化テスチE(完�E牁E")
    print("=" * 60)
    
    # バックアチE�E作�E確誁E    try:
        response = input("バックアチE�Eファイルを作�Eしますか�E�E(Y/n): ")
        if response.lower() != 'n':
            create_backup()
    except (KeyboardInterrupt, EOFError):
        print("\nバックアチE�EはスキチE�Eされました")
    
    # 修正ガイド表示
    print("\n")
    show_modification_guide()
    
    try:
        input("\n修正完亁E��、Enterキーを押してチE��トを開始してください...")
    except (KeyboardInterrupt, EOFError):
        print("\nチE��ト終亁E)
        return
    
    all_passed = True
    
    # 1. インポ�Eト安�E性チE��チE    if not test_import_safety():
        all_passed = False
    
    # 2. エラーハンドリングチE��チE    if not test_error_handling():
        all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 全ての安�E化テスト�E劁E")
        print("\n次のスチE��チE")
        print("1. ✁Eフォールバック機�E削除完亁E)
        print("2. ✁Eエラーハンドリング強化完亁E) 
        print("3. 🚀 Phase4-2: 高度機�E追加準備完亁E)
        
        # GUI チE��ト実行確誁E        try:
            response = input("\nGUI統合テストを実行しますか�E�E(y/N): ")
            if response.lower() == 'y':
                run_gui_test()
        except (KeyboardInterrupt, EOFError):
            print("\nGUIチE��ト�EスキチE�Eされました")
        
    else:
        print("❁E一部チE��トが失敗しました")
        print("修正が忁E��な頁E��がありまぁE)
        
        try:
            response = input("\n修正ガイドを再表示しますか�E�E(y/N): ")
            if response.lower() == 'y':
                show_modification_guide()
        except (KeyboardInterrupt, EOFError):
            pass

if __name__ == "__main__":
    main()
