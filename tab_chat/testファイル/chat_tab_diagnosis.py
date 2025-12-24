#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI縺ｨ繝√Ε繝・ヨ繧ｿ繝冶ｨｺ譁ｭ繧ｹ繧ｯ繝ｪ繝励ヨ
tab_chat/app.py縺ｮ迥ｶ豕√ｒ隧ｳ邏ｰ遒ｺ隱・"""

import os
import sys
import importlib.util
from pathlib import Path

def diagnose_chat_tab():
    """AI縺ｨ繝√Ε繝・ヨ繧ｿ繝悶・險ｺ譁ｭ"""
    print("剥 AI縺ｨ繝√Ε繝・ヨ繧ｿ繝冶ｨｺ譁ｭ髢句ｧ・..")
    print("=" * 50)
    
    # 1. 迴ｾ蝨ｨ縺ｮ繝・ぅ繝ｬ繧ｯ繝医Μ遒ｺ隱・    current_dir = os.getcwd()
    print(f"唐 迴ｾ蝨ｨ縺ｮ繝・ぅ繝ｬ繧ｯ繝医Μ: {current_dir}")
    
    # 2. tab_chat繝・ぅ繝ｬ繧ｯ繝医Μ縺ｮ蟄伜惠遒ｺ隱・    tab_chat_dir = Path(current_dir) / "tab_chat"
    print(f"唐 tab_chat繝・ぅ繝ｬ繧ｯ繝医Μ蟄伜惠: {tab_chat_dir.exists()}")
    
    if tab_chat_dir.exists():
        print(f"唐 tab_chat繝・ぅ繝ｬ繧ｯ繝医Μ蜀・ｮｹ:")
        for item in tab_chat_dir.iterdir():
            print(f"   - {item.name}")
    
    # 3. app.py繝輔ぃ繧､繝ｫ縺ｮ蟄伜惠遒ｺ隱・    app_py_path = tab_chat_dir / "app.py"
    print(f"塘 tab_chat/app.py蟄伜惠: {app_py_path.exists()}")
    
    if not app_py_path.exists():
        print("笶・tab_chat/app.py縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ")
        
        # 莉悶・蜿ｯ閭ｽ諤ｧ繧呈爾縺・        print("\n剥 莉悶・app.py繝輔ぃ繧､繝ｫ繧呈爾縺励※縺・∪縺・..")
        for root, dirs, files in os.walk(current_dir):
            if "app.py" in files:
                relative_path = os.path.relpath(os.path.join(root, "app.py"), current_dir)
                print(f"   塘 逋ｺ隕・ {relative_path}")
        
        return False
    
    # 4. app.py縺ｮ蜀・ｮｹ遒ｺ隱・    print(f"\n当 {app_py_path} 縺ｮ蜀・ｮｹ蛻・梵...")
    try:
        with open(app_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 髢｢謨ｰ縺ｮ讀懃ｴ｢
        import re
        
        # create_縺ｧ蟋九∪繧矩未謨ｰ繧呈､懃ｴ｢
        create_functions = re.findall(r'def (create_[^(]+)', content)
        print(f"剥 逋ｺ隕九＆繧後◆create髢｢謨ｰ: {create_functions}")
        
        # 迚ｹ螳壹・髢｢謨ｰ縺ｮ蟄伜惠遒ｺ隱・        target_functions = [
            'create_integrated_ai_chat_tab',
            'create_chat_tab',
            'create_ai_chat_tab'
        ]
        
        for func_name in target_functions:
            if func_name in content:
                print(f"笨・{func_name} 髢｢謨ｰ逋ｺ隕・)
                
                # 髢｢謨ｰ縺ｮ螳夂ｾｩ陦後ｒ謗｢縺・                pattern = rf'def {func_name}\([^)]*\):'
                matches = re.findall(pattern, content)
                if matches:
                    print(f"   搭 螳夂ｾｩ: {matches[0]}")
            else:
                print(f"笶・{func_name} 髢｢謨ｰ譛ｪ逋ｺ隕・)
        
        # 繧､繝ｳ繝昴・繝域枚縺ｮ遒ｺ隱・        print(f"\n逃 繧､繝ｳ繝昴・繝域枚:")
        import_lines = [line.strip() for line in content.split('\n') if line.strip().startswith(('import ', 'from '))]
        for imp in import_lines[:10]:  # 譛蛻昴・10蛟九・繧､繝ｳ繝昴・繝域枚縺ｮ縺ｿ陦ｨ遉ｺ
            print(f"   {imp}")
        if len(import_lines) > 10:
            print(f"   ... 莉本len(import_lines)-10}蛟九・繧､繝ｳ繝昴・繝域枚")
            
    except Exception as e:
        print(f"笶・繝輔ぃ繧､繝ｫ隱ｭ縺ｿ霎ｼ縺ｿ繧ｨ繝ｩ繝ｼ: {e}")
        return False
    
    # 5. 螳滄圀縺ｮ繧､繝ｳ繝昴・繝医ユ繧ｹ繝・    print(f"\nｧｪ 繧､繝ｳ繝昴・繝医ユ繧ｹ繝・..")
    
    # 繝代せ繧定ｿｽ蜉
    if str(tab_chat_dir) not in sys.path:
        sys.path.insert(0, str(tab_chat_dir))
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # 繝代ち繝ｼ繝ｳ1: tab_chat.app
    try:
        import tab_chat.app as chat_app
        print("笨・tab_chat.app 繧､繝ｳ繝昴・繝域・蜉・)
        
        # 蛻ｩ逕ｨ蜿ｯ閭ｽ縺ｪ髢｢謨ｰ繝ｪ繧ｹ繝・        functions = [name for name in dir(chat_app) if name.startswith('create_')]
        print(f"剥 蛻ｩ逕ｨ蜿ｯ閭ｽ縺ｪ髢｢謨ｰ: {functions}")
        
        # 蜷・未謨ｰ縺ｮ隧ｳ邏ｰ
        for func_name in functions:
            func = getattr(chat_app, func_name)
            try:
                import inspect
                sig = inspect.signature(func)
                print(f"搭 {func_name}{sig}")
            except:
                print(f"搭 {func_name}: 繧ｷ繧ｰ繝阪メ繝｣蜿門ｾ怜､ｱ謨・)
                
    except ImportError as e:
        print(f"笶・tab_chat.app 繧､繝ｳ繝昴・繝医お繝ｩ繝ｼ: {e}")
    
    # 繝代ち繝ｼ繝ｳ2: 逶ｴ謗･app
    try:
        import app
        print("笨・app.py 逶ｴ謗･繧､繝ｳ繝昴・繝域・蜉・)
        
        functions = [name for name in dir(app) if name.startswith('create_')]
        print(f"剥 app.py蜀・・create髢｢謨ｰ: {functions}")
        
    except ImportError as e:
        print(f"笶・app.py 逶ｴ謗･繧､繝ｳ繝昴・繝医お繝ｩ繝ｼ: {e}")
    
    # 繝代ち繝ｼ繝ｳ3: spec菴ｿ逕ｨ
    try:
        spec = importlib.util.spec_from_file_location("chat_app", app_py_path)
        if spec and spec.loader:
            chat_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(chat_module)
            
            print("笨・importlib.util邨檎罰繧､繝ｳ繝昴・繝域・蜉・)
            
            functions = [name for name in dir(chat_module) if name.startswith('create_')]
            print(f"剥 importlib邨檎罰縺ｮ髢｢謨ｰ: {functions}")
            
            # create_integrated_ai_chat_tab 縺ｮ繝・せ繝・            if hasattr(chat_module, 'create_integrated_ai_chat_tab'):
                print("笨・create_integrated_ai_chat_tab 髢｢謨ｰ遒ｺ隱・)
                func = getattr(chat_module, 'create_integrated_ai_chat_tab')
                print(f"搭 髢｢謨ｰ繧ｿ繧､繝・ {type(func)}")
                
                try:
                    import inspect
                    sig = inspect.signature(func)
                    print(f"搭 繧ｷ繧ｰ繝阪メ繝｣: create_integrated_ai_chat_tab{sig}")
                except Exception as sig_e:
                    print(f"笶・繧ｷ繧ｰ繝阪メ繝｣蜿門ｾ励お繝ｩ繝ｼ: {sig_e}")
                    
    except Exception as e:
        print(f"笶・importlib.util邨檎罰繧､繝ｳ繝昴・繝医お繝ｩ繝ｼ: {e}")
    
    # 6. __init__.py 縺ｮ遒ｺ隱・    init_py_path = tab_chat_dir / "__init__.py"
    print(f"\n塘 {init_py_path} 蟄伜惠: {init_py_path.exists()}")
    
    if init_py_path.exists():
        try:
            with open(init_py_path, 'r', encoding='utf-8') as f:
                init_content = f.read()
            print(f"当 __init__.py 蜀・ｮｹ:")
            print(init_content[:200] + "..." if len(init_content) > 200 else init_content)
        except Exception as e:
            print(f"笶・__init__.py 隱ｭ縺ｿ霎ｼ縺ｿ繧ｨ繝ｩ繝ｼ: {e}")
    
    print("\n" + "=" * 50)
    print("剥 險ｺ譁ｭ螳御ｺ・)
    
    return True

if __name__ == "__main__":
    diagnose_chat_tab()
