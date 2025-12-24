#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
式 邨ｱ蜷域ｧ謾ｹ蝟・沿 閾ｪ蜍墓磁邯售lideSwitch v3.0
Improved Auto Connection SlideSwitch with Unified State Management

謾ｹ蝟・・繧､繝ｳ繝・
- SlideSwitch.set() 繧剃ｸｭ蠢・→縺励◆荳蜈・噪迥ｶ諷狗ｮ｡逅・- set_slide_switch_state() 縺ｯ SlideSwitch.set() 繧貞・驛ｨ蜻ｼ縺ｳ蜃ｺ縺・- UI譖ｴ譁ｰ縺ｨ繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ蜻ｼ縺ｳ蜃ｺ縺励・螳悟・蜷梧悄
- 繧ｯ繝ｪ繝・け謫堺ｽ懊→迥ｶ諷句､画峩縺ｮ遒ｺ螳溘↑騾｣謳ｺ
- 閾ｪ蜍墓磁邯壹・閾ｪ蜍桧FF讖溯・縺ｨ縺ｮ螳悟・謨ｴ蜷域ｧ
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import logging

# 繝ｭ繧ｰ險ｭ螳・logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


class SlideSwitch(tk.Frame):
    """
    謾ｹ濶ｯ迚・lideSwitch - 迥ｶ諷九→UI螳悟・蜷梧悄
    
    迚ｹ蠕ｴ:
    - set() 繝｡繧ｽ繝・ラ縺ｫ繧医ｋ荳蜈・噪迥ｶ諷狗ｮ｡逅・    - UI譖ｴ譁ｰ縺ｨ繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺ｮ螳悟・蜷梧悄
    - 閾ｪ蜍桧FF讖溯・邨ｱ蜷・    """
    
    def __init__(self, master=None, text_on="ON", text_off="OFF", 
                 initial_value=False, callback=None, service_key=None, **kwargs):
        """
        蛻晄悄蛹・        
        Args:
            master: 隕ｪ繧ｦ繧｣繧ｸ繧ｧ繝・ヨ
            text_on: ON陦ｨ遉ｺ繝・く繧ｹ繝・            text_off: OFF陦ｨ遉ｺ繝・く繧ｹ繝・            initial_value: 蛻晄悄蛟､
            callback: 迥ｶ諷句､画峩譎ゅ・繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ髢｢謨ｰ callback(service_key, value)
            service_key: 繧ｵ繝ｼ繝薙せ隴伜挨繧ｭ繝ｼ
        """
        super().__init__(master, **kwargs)
        
        # 蝓ｺ譛ｬ險ｭ螳・        self._value = initial_value
        self._text_on = text_on
        self._text_off = text_off
        self._callback = callback
        self._service_key = service_key
        self._after_id = None
        
        # UI菴懈・
        self._create_ui()
        
        # 蛻晄悄迥ｶ諷句渚譏
        self._update_ui()
    
    def _create_ui(self):
        """UI隕∫ｴ菴懈・"""
        self.configure(width=80, height=30, bg="#f5f5f5")
        
        # 繧ｭ繝｣繝ｳ繝舌せ菴懈・
        self.canvas = tk.Canvas(
            self, 
            width=80, 
            height=30, 
            bd=0, 
            highlightthickness=0,
            bg="#e57373"  # 蛻晄悄: 襍､・・FF迥ｶ諷具ｼ・        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # UI隕∫ｴ菴懈・
        self.bg_rect = self.canvas.create_rectangle(2, 2, 78, 28, outline="", fill="#e57373")
        self.indicator = self.canvas.create_oval(5, 5, 25, 25, outline="#cccccc", fill="white", width=2)
        self.text = self.canvas.create_text(40, 15, text=self._text_off, fill="white", font=("Yu Gothic UI", 8, "bold"))
        
        # 繧､繝吶Φ繝医ヰ繧､繝ｳ繝・        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.bind("<Leave>", lambda e: self.canvas.config(cursor=""))
    
    def _on_canvas_click(self, event=None):
        """繧ｭ繝｣繝ｳ繝舌せ繧ｯ繝ｪ繝・け蜃ｦ逅・""
        # 閾ｪ蜍桧FF莠育ｴ・ｸｭ縺ｯ繧ｯ繝ｪ繝・け繧偵ヶ繝ｭ繝・け
        if self._after_id:
            logger.debug(f"笞・・{self._service_key}: 閾ｪ蜍桧FF莠育ｴ・ｸｭ縺ｮ縺溘ａ繧ｯ繝ｪ繝・け辟｡隕・)
            return
            
        # 繝医げ繝ｫ謫堺ｽ懷ｮ溯｡・        self.toggle()
    
    def toggle(self):
        """迥ｶ諷九ヨ繧ｰ繝ｫ・・et()繧貞・驛ｨ蜻ｼ縺ｳ蜃ｺ縺暦ｼ・""
        self.set(not self._value)
    
    def set(self, value: bool, trigger_callback=True):
        """
        迥ｶ諷玖ｨｭ螳夲ｼ井ｸ蜈・噪迥ｶ諷狗ｮ｡逅・ｼ・        
        Args:
            value: 險ｭ螳壼､
            trigger_callback: 繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ蜻ｼ縺ｳ蜃ｺ縺励ヵ繝ｩ繧ｰ
        """
        # 蛟､縺悟､峨ｏ繧峨↑縺・ｴ蜷医・菴輔ｂ縺励↑縺・        if self._value == value and not hasattr(self, '_force_update'):
            return
            
        # 迥ｶ諷区峩譁ｰ
        self._value = value
        
        # 閾ｪ蜍桧FF莠育ｴ・ｒ繧ｭ繝｣繝ｳ繧ｻ繝ｫ
        self.cancel_auto_off()
        
        # UI譖ｴ譁ｰ
        self._update_ui()
        
        # 繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ蜻ｼ縺ｳ蜃ｺ縺・        if trigger_callback and self._callback:
            try:
                if self._service_key:
                    self._callback(self._service_key, self._value)
                else:
                    self._callback(self._value)
            except Exception as e:
                logger.error(f"笶・繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ蜻ｼ縺ｳ蜃ｺ縺励お繝ｩ繝ｼ ({self._service_key}): {e}")
    
    def _update_ui(self):
        """UI譖ｴ譁ｰ・育憾諷九↓蝓ｺ縺･縺・※荳蜈・噪縺ｫ譖ｴ譁ｰ・・""
        try:
            if self._value:
                # ON迥ｶ諷・ 阮・ｷ・                bg_color = "#81c784"
                indicator_x1, indicator_x2 = 55, 75  # 蜿ｳ蟇・○
                text_content = self._text_on
            else:
                # OFF迥ｶ諷・ 襍､
                bg_color = "#e57373"
                indicator_x1, indicator_x2 = 5, 25   # 蟾ｦ蟇・○
                text_content = self._text_off
            
            # 繧ｭ繝｣繝ｳ繝舌せ閭梧勹譖ｴ譁ｰ
            self.canvas.config(bg=bg_color)
            self.canvas.itemconfig(self.bg_rect, fill=bg_color)
            
            # 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ菴咲ｽｮ譖ｴ譁ｰ
            self.canvas.coords(self.indicator, indicator_x1, 5, indicator_x2, 25)
            
            # 繝・く繧ｹ繝域峩譁ｰ
            self.canvas.itemconfig(self.text, text=text_content)
            
        except Exception as e:
            logger.error(f"笶・UI譖ｴ譁ｰ繧ｨ繝ｩ繝ｼ ({self._service_key}): {e}")
    
    def get(self) -> bool:
        """迴ｾ蝨ｨ縺ｮ迥ｶ諷句叙蠕・""
        return self._value
    
    def auto_off(self, delay_ms=3000):
        """
        閾ｪ蜍桧FF險ｭ螳・        
        Args:
            delay_ms: 驕・ｻｶ譎る俣・医Α繝ｪ遘抵ｼ・        """
        # 譌｢蟄倥・莠育ｴ・ｒ繧ｭ繝｣繝ｳ繧ｻ繝ｫ
        self.cancel_auto_off()
        
        logger.info(f"竢ｰ {self._service_key}: {delay_ms/1000}遘貞ｾ後↓閾ｪ蜍桧FF螳溯｡・)
        
        def execute_auto_off():
            logger.info(f"竢ｰ {self._service_key}: 閾ｪ蜍桧FF螳溯｡・)
            self.set(False)  # set()繧帝壹＠縺ｦ迥ｶ諷句､画峩
            self._after_id = None
        
        self._after_id = self.after(delay_ms, execute_auto_off)
    
    def cancel_auto_off(self):
        """閾ｪ蜍桧FF莠育ｴ・く繝｣繝ｳ繧ｻ繝ｫ"""
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
            logger.debug(f"竢ｰ {self._service_key}: 閾ｪ蜍桧FF莠育ｴ・く繝｣繝ｳ繧ｻ繝ｫ")
    
    def set_connecting_state(self, is_connecting=True):
        """
        謗･邯壻ｸｭ迥ｶ諷玖｡ｨ遉ｺ
        
        Args:
            is_connecting: 謗･邯壻ｸｭ繝輔Λ繧ｰ
        """
        try:
            if is_connecting:
                # 謗･邯壻ｸｭ: 繧ｪ繝ｬ繝ｳ繧ｸ縺ｧ轤ｹ貊・                self.canvas.config(bg="#ff9800")
                self.canvas.itemconfig(self.bg_rect, fill="#ff9800")
                self.canvas.itemconfig(self.text, text="謗･邯壻ｸｭ...")
                self._start_connecting_blink()
            else:
                # 騾壼ｸｸ迥ｶ諷九↓謌ｻ縺・                self._update_ui()
                
        except Exception as e:
            logger.error(f"笶・謗･邯夂憾諷玖｡ｨ遉ｺ繧ｨ繝ｩ繝ｼ ({self._service_key}): {e}")
    
    def _start_connecting_blink(self):
        """謗･邯壻ｸｭ縺ｮ轤ｹ貊・幕蟋・""
        if hasattr(self, '_connecting_blink') and self._connecting_blink:
            current_bg = self.canvas.cget("bg")
            if current_bg == "#ff9800":
                new_bg = "#ffcc80"  # 阮・＞繧ｪ繝ｬ繝ｳ繧ｸ
            else:
                new_bg = "#ff9800"
            
            self.canvas.config(bg=new_bg)
            self.canvas.itemconfig(self.bg_rect, fill=new_bg)
            self.after(500, self._start_connecting_blink)
    
    def start_connecting_animation(self):
        """謗･邯壻ｸｭ繧｢繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ髢句ｧ・""
        self._connecting_blink = True
        self.set_connecting_state(True)
    
    def stop_connecting_animation(self):
        """謗･邯壻ｸｭ繧｢繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ蛛懈ｭ｢"""
        self._connecting_blink = False
        self.set_connecting_state(False)


# ===== 邨ｱ蜷磯未謨ｰ: 螟夜Κ縺九ｉ縺ｮ迥ｶ諷句宛蠕｡ =====

def set_slide_switch_state(slide_switch, value: bool, log_widget=None, message: str = ""):
    """
    SlideSwitch迥ｶ諷玖ｨｭ螳夲ｼ育ｵｱ蜷育沿・・    
    Args:
        slide_switch: SlideSwitch 繧､繝ｳ繧ｹ繧ｿ繝ｳ繧ｹ
        value: 險ｭ螳壼､
        log_widget: 繝ｭ繧ｰ陦ｨ遉ｺ繧ｦ繧｣繧ｸ繧ｧ繝・ヨ
        message: 繝ｭ繧ｰ繝｡繝・そ繝ｼ繧ｸ
    """
    if slide_switch and hasattr(slide_switch, 'set'):
        # SlideSwitch.set()繧帝壹＠縺ｦ迥ｶ諷句､画峩・井ｸ蜈・ｮ｡逅・ｼ・        slide_switch.set(value)
    
    # 繝ｭ繧ｰ蜃ｺ蜉・    if log_widget and message and hasattr(log_widget, "insert"):
        log_widget.insert("end", f"{message}\n")
        log_widget.see("end")


def create_slide_switch(parent, service_key, toggle_var, callback):
    """
    SlideSwitch菴懈・・井ｺ呈鋤諤ｧ邯ｭ謖・ｼ・    
    Args:
        parent: 隕ｪ繝輔Ξ繝ｼ繝
        service_key: 繧ｵ繝ｼ繝薙せ繧ｭ繝ｼ
        toggle_var: BooleanVar・井ｽｿ逕ｨ縺輔ｌ縺ｪ縺・′莠呈鋤諤ｧ縺ｮ縺溘ａ菫晄戟・・        callback: 繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ髢｢謨ｰ
        
    Returns:
        SlideSwitch: 菴懈・縺輔ｌ縺欖lideSwitch
    """
    initial_value = toggle_var.get() if toggle_var else False
    
    slide_switch = SlideSwitch(
        parent,
        text_on="ON",
        text_off="OFF",
        initial_value=initial_value,
        callback=callback,
        service_key=service_key
    )
    
    return slide_switch


def update_slide_switch_appearance(slide_switch, is_on):
    """
    SlideSwitch螟冶ｦｳ譖ｴ譁ｰ・井ｺ呈鋤諤ｧ邯ｭ謖・ｼ・    
    Args:
        slide_switch: SlideSwitch 繧､繝ｳ繧ｹ繧ｿ繝ｳ繧ｹ
        is_on: ON/OFF迥ｶ諷・    """
    if slide_switch and hasattr(slide_switch, 'set'):
        slide_switch.set(is_on, trigger_callback=False)  # 繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺ｪ縺励〒迥ｶ諷区峩譁ｰ


def animate_slide_switch(slide_switch, to_on=True):
    """
    SlideSwitch 繧｢繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ・井ｺ呈鋤諤ｧ邯ｭ謖・ｼ・    
    Args:
        slide_switch: SlideSwitch 繧､繝ｳ繧ｹ繧ｿ繝ｳ繧ｹ  
        to_on: 繧｢繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ譁ｹ蜷・    """
    if slide_switch and hasattr(slide_switch, 'set'):
        slide_switch.set(to_on)


# ===== 閾ｪ蜍墓磁邯壽ｩ溯・邨ｱ蜷医け繝ｩ繧ｹ =====

class AutoConnectionManager:
    """閾ｪ蜍墓磁邯夂ｮ｡逅・け繝ｩ繧ｹ"""
    
    def __init__(self):
        self.connection_threads = {}
        self.is_connecting = {}
        self.connection_callback = None
    
    def set_connection_callback(self, callback):
        """謗･邯壼・逅・さ繝ｼ繝ｫ繝舌ャ繧ｯ險ｭ螳・""
        self.connection_callback = callback
    
    def start_auto_connection(self, slide_switch, service_key):
        """閾ｪ蜍墓磁邯夐幕蟋・""
        if self.is_connecting.get(service_key, False):
            return
            
        logger.info(f"迫 {service_key} 閾ｪ蜍墓磁邯夐幕蟋・)
        
        self.is_connecting[service_key] = True
        slide_switch.start_connecting_animation()
        
        # 謗･邯壼・逅・ｒ蛻･繧ｹ繝ｬ繝・ラ縺ｧ螳溯｡・        connection_thread = threading.Thread(
            target=self._connection_worker,
            args=(slide_switch, service_key),
            daemon=True
        )
        connection_thread.start()
        self.connection_threads[service_key] = connection_thread
    
    def _connection_worker(self, slide_switch, service_key):
        """謗･邯壼・逅・Ρ繝ｼ繧ｫ繝ｼ"""
        try:
            # 謗･邯壼・逅・ｮ溯｡・            if self.connection_callback:
                success = self.connection_callback(service_key)
            else:
                success = self._default_connection_test(service_key)
            
            # UI繧ｹ繝ｬ繝・ラ縺ｧ邨先棡蜃ｦ逅・            slide_switch.after(0, lambda: self._handle_connection_result(slide_switch, service_key, success))
            
        except Exception as e:
            logger.error(f"笶・{service_key} 謗･邯壹お繝ｩ繝ｼ: {e}")
            slide_switch.after(0, lambda: self._handle_connection_result(slide_switch, service_key, False))
    
    def _default_connection_test(self, service_key):
        """繝・ヵ繧ｩ繝ｫ繝域磁邯壹ユ繧ｹ繝・""
        import random
        
        # 謗･邯壽凾髢捺ｨ｡謫ｬ・・-3遘抵ｼ・        time.sleep(random.uniform(1.0, 3.0))
        
        # 70%縺ｮ遒ｺ邇・〒謌仙粥
        return random.random() < 0.7
    
    def _handle_connection_result(self, slide_switch, service_key, success):
        """謗･邯夂ｵ先棡蜃ｦ逅・""
        self.is_connecting[service_key] = False
        slide_switch.stop_connecting_animation()
        
        if success:
            logger.info(f"笨・{service_key} 謗･邯壽・蜉・)
            slide_switch.set(True)
        else:
            logger.warning(f"笶・{service_key} 謗･邯壼､ｱ謨・- 3遘貞ｾ後↓閾ｪ蜍桧FF")
            slide_switch.set(True)  # 荳譌ｦON縺ｫ縺励※縺九ｉ
            slide_switch.auto_off(3000)  # 3遘貞ｾ後↓閾ｪ蜍桧FF


# ===== 繝・せ繝育畑繝・Δ繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ =====

class SlideSwichDemoApp:
    """SlideSwitch 繝・Δ繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ"""
    
    def __init__(self):
        self.switches = {}
        self.connection_manager = AutoConnectionManager()
        self.connection_manager.set_connection_callback(self.test_connection)
        
        self._create_ui()
    
    def test_connection(self, service_key):
        """繝・せ繝育畑謗･邯壼・逅・""
        import random
        
        print(f"迫 {service_key} 謗･邯壹ユ繧ｹ繝亥ｮ溯｡御ｸｭ...")
        
        # 繧ｵ繝ｼ繝薙せ蛻･謌仙粥邇・        success_rates = {
            'service_1': 0.8,
            'service_2': 0.6,
            'service_3': 0.9,
            'service_4': 0.5,
            'service_5': 0.7
        }
        
        # 謗･邯壽凾髢捺ｨ｡謫ｬ
        time.sleep(random.uniform(1.0, 2.5))
        
        # 謌仙粥蛻､螳・        success_rate = success_rates.get(service_key, 0.7)
        success = random.random() < success_rate
        
        print(f"{'笨・ if success else '笶・} {service_key} 謗･邯嘴'謌仙粥' if success else '螟ｱ謨・}")
        return success
    
    def _create_ui(self):
        """UI菴懈・"""
        self.root = tk.Tk()
        self.root.title("式 邨ｱ蜷域ｧ謾ｹ蝟・沿 SlideSwitch 繝・Δ")
        self.root.geometry("600x500")
        self.root.configure(bg="#f0f0f0")
        
        # 繧ｿ繧､繝医Ν
        title_label = tk.Label(
            self.root,
            text="式 邨ｱ蜷域ｧ謾ｹ蝟・沿 SlideSwitch 繝・Δ",
            font=("Yu Gothic UI", 16, "bold"),
            bg="#f0f0f0"
        )
        title_label.pack(pady=10)
        
        # 謾ｹ蝟・せ隱ｬ譏・        improvements_text = """肌 謾ｹ蝟・・繧､繝ｳ繝・
窶｢ SlideSwitch.set() 縺ｫ繧医ｋ荳蜈・噪迥ｶ諷狗ｮ｡逅・窶｢ UI譖ｴ譁ｰ縺ｨ繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺ｮ螳悟・蜷梧悄
窶｢ 繧ｯ繝ｪ繝・け謫堺ｽ懊→迥ｶ諷句､画峩縺ｮ遒ｺ螳溘↑騾｣謳ｺ
窶｢ 閾ｪ蜍桧FF讖溯・縺ｨ縺ｮ邨ｱ蜷域ｧ蜷台ｸ・窶｢ set_slide_switch_state() 縺ｯ蜀・Κ縺ｧSlideSwitch.set()繧貞他縺ｳ蜃ｺ縺・""
        
        improvements_label = tk.Label(
            self.root,
            text=improvements_text,
            font=("Yu Gothic UI", 9),
            bg="#f0f0f0",
            justify=tk.LEFT
        )
        improvements_label.pack(pady=5)
        
        # 繧ｹ繧､繝・メ繧ｨ繝ｪ繧｢
        switches_frame = tk.LabelFrame(
            self.root, 
            text="SlideSwitch 繝・せ繝・, 
            font=("Yu Gothic UI", 12, "bold")
        )
        switches_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 繝・せ繝育畑繧ｹ繧､繝・メ菴懈・
        services = [
            ('service_1', '繧ｵ繝ｼ繝薙せ1'),
            ('service_2', '繧ｵ繝ｼ繝薙せ2'),
            ('service_3', '繧ｵ繝ｼ繝薙せ3'),
            ('service_4', '繧ｵ繝ｼ繝薙せ4'),
            ('service_5', '繧ｵ繝ｼ繝薙せ5')
        ]
        
        for service_key, service_name in services:
            self._create_service_row(switches_frame, service_key, service_name)
        
        # 繧ｳ繝ｳ繝医Ο繝ｼ繝ｫ繝代ロ繝ｫ
        self._create_control_panel()
        
        # 繝ｭ繧ｰ繧ｨ繝ｪ繧｢
        self._create_log_area()
    
    def _create_service_row(self, parent, service_key, service_name):
        """繧ｵ繝ｼ繝薙せ陦御ｽ懈・"""
        row_frame = tk.Frame(parent, bg="#f5f5f5", relief="solid", bd=1)
        row_frame.pack(fill=tk.X, padx=5, pady=3)
        
        # 繧ｵ繝ｼ繝薙せ蜷・        name_label = tk.Label(
            row_frame,
            text=f"伯 {service_name}:",
            font=("Yu Gothic UI", 11),
            bg="#f5f5f5",
            width=15
        )
        name_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # SlideSwitch
        def on_toggle(key, value):
            print(f"売 {key} 迥ｶ諷句､画峩: {value}")
            if value:
                # ON譎ゅ・閾ｪ蜍墓磁邯夐幕蟋・                self.connection_manager.start_auto_connection(self.switches[key], key)
        
        slide_switch = SlideSwitch(
            row_frame,
            text_on="ON",
            text_off="OFF",
            initial_value=False,
            callback=on_toggle,
            service_key=service_key
        )
        slide_switch.pack(side=tk.LEFT, padx=10, pady=5)
        self.switches[service_key] = slide_switch
        
        # 迥ｶ諷玖｡ｨ遉ｺ
        status_label = tk.Label(
            row_frame,
            text="笞ｪ 辟｡蜉ｹ",
            font=("Yu Gothic UI", 10),
            bg="#f5f5f5",
            fg="gray"
        )
        status_label.pack(side=tk.LEFT, padx=10, pady=5)
    
    def _create_control_panel(self):
        """繧ｳ繝ｳ繝医Ο繝ｼ繝ｫ繝代ロ繝ｫ菴懈・"""
        control_frame = tk.LabelFrame(
            self.root, 
            text="繧ｳ繝ｳ繝医Ο繝ｼ繝ｫ", 
            font=("Yu Gothic UI", 11, "bold")
        )
        control_frame.pack(fill=tk.X, padx=20, pady=5)
        
        button_frame = tk.Frame(control_frame)
        button_frame.pack(pady=5)
        
        def auto_connect_all():
            print("噫 蜈ｨ繧ｵ繝ｼ繝薙せ閾ｪ蜍墓磁邯夐幕蟋・)
            for service_key, switch in self.switches.items():
                switch.set(True)  # ON迥ｶ諷九↓縺励※繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺ｧ閾ｪ蜍墓磁邯・        
        def force_off_all():
            print("伯 蜈ｨ繧ｵ繝ｼ繝薙せ蠑ｷ蛻ｶOFF")
            for service_key, switch in self.switches.items():
                set_slide_switch_state(switch, False, self.log_text, f"笞ｪ {service_key} 蠑ｷ蛻ｶOFF")
        
        def test_auto_off():
            print("竢ｰ 蜈ｨ繧ｵ繝ｼ繝薙せ3遘貞ｾ瑚・蜍桧FF 繝・せ繝・)
            for service_key, switch in self.switches.items():
                switch.set(True)  # 荳譌ｦON
                switch.auto_off(3000)  # 3遘貞ｾ瑚・蜍桧FF
        
        # 繝懊ち繝ｳ驟咲ｽｮ
        tk.Button(button_frame, text="噫 蜈ｨ閾ｪ蜍墓磁邯・, command=auto_connect_all).pack(side=tk.LEFT, padx=3)
        tk.Button(button_frame, text="伯 蜈ｨ蠑ｷ蛻ｶOFF", command=force_off_all).pack(side=tk.LEFT, padx=3)
        tk.Button(button_frame, text="竢ｰ 閾ｪ蜍桧FF奛護侃繝・, command=test_auto_off).pack(side=tk.LEFT, padx=3)
    
    def _create_log_area(self):
        """繝ｭ繧ｰ繧ｨ繝ｪ繧｢菴懈・"""
        log_frame = tk.LabelFrame(
            self.root, 
            text="蜍穂ｽ懊Ο繧ｰ", 
            font=("Yu Gothic UI", 10, "bold")
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        # 繝ｭ繧ｰ繝・く繧ｹ繝医え繧｣繧ｸ繧ｧ繝・ヨ
        self.log_text = tk.Text(
            log_frame, 
            height=8, 
            font=("Consolas", 9), 
            bg="#f8f8f8",
            wrap=tk.WORD
        )
        log_scrollbar = tk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 蛻晄悄繝｡繝・そ繝ｼ繧ｸ
        self.log_text.insert("end", "式 邨ｱ蜷域ｧ謾ｹ蝟・沿 SlideSwitch 繝・Δ髢句ｧ欺n")
        self.log_text.insert("end", "庁 蜷・せ繧､繝・メ繧偵け繝ｪ繝・け縺励※蜍穂ｽ懃｢ｺ隱阪＠縺ｦ縺上□縺輔＞\n")
        self.log_text.insert("end", "肌 謾ｹ蝟・せ: 迥ｶ諷狗ｮ｡逅・・UI譖ｴ譁ｰ繝ｻ繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺悟ｮ悟・蜷梧悄\n\n")
    
    def run(self):
        """繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ螳溯｡・""
        print("噫 邨ｱ蜷域ｧ謾ｹ蝟・沿 SlideSwitch 繝・Δ髢句ｧ・)
        print("肌 謾ｹ蝟・・繧､繝ｳ繝・ SlideSwitch.set()縺ｫ繧医ｋ荳蜈・噪迥ｶ諷狗ｮ｡逅・)
        
        self.root.mainloop()
        
        print("笨・SlideSwitch 繝・Δ邨ゆｺ・)


# ===== 蜊倅ｽ薙ユ繧ｹ繝・=====

def test_slide_switch_improvements():
    """SlideSwitch謾ｹ蝟・せ繝・せ繝・""
    print("ｧｪ === SlideSwitch謾ｹ蝟・せ繝・せ繝・===")
    
    test_results = []
    
    try:
        # 繝・せ繝育畑UI菴懈・
        root = tk.Tk()
        root.withdraw()  # 繧ｦ繧｣繝ｳ繝峨え繧帝國縺・        
        callback_calls = []
        
        def test_callback(service_key, value):
            callback_calls.append((service_key, value))
        
        # 1. SlideSwitch菴懈・繝・せ繝・        slide_switch = SlideSwitch(
            root,
            initial_value=False,
            callback=test_callback,
            service_key="test_service"
        )
        
        assert slide_switch.get() == False, "蛻晄悄蛟､縺梧ｭ｣縺励￥險ｭ螳壹＆繧後ｋ縺薙→"
        test_results.append("笨・蛻晄悄蛟､險ｭ螳・ OK")
        
        # 2. set()繝｡繧ｽ繝・ラ繝・せ繝・        slide_switch.set(True)
        assert slide_switch.get() == True, "set()縺ｧ迥ｶ諷九′螟画峩縺輔ｌ繧九％縺ｨ"
        assert len(callback_calls) == 1, "繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺悟他縺ｳ蜃ｺ縺輔ｌ繧九％縺ｨ"
        assert callback_calls[0] == ("test_service", True), "繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ蠑墓焚縺梧ｭ｣縺励＞縺薙→"
        
        test_results.append("笨・set()繝｡繧ｽ繝・ラ: OK")
        
        # 3. toggle()繝｡繧ｽ繝・ラ繝・せ繝・        callback_calls.clear()
        slide_switch.toggle()
        assert slide_switch.get() == False, "toggle()縺ｧ迥ｶ諷九′蛻・ｊ譖ｿ繧上ｋ縺薙→"
        assert len(callback_calls) == 1, "toggle譎ゅ↓繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺悟他縺ｳ蜃ｺ縺輔ｌ繧九％縺ｨ"
        
        test_results.append("笨・toggle()繝｡繧ｽ繝・ラ: OK")
        
        # 4. 閾ｪ蜍桧FF讖溯・繝・せ繝・        slide_switch.set(True)
        slide_switch.auto_off(100)  # 0.1遘貞ｾ・        
        # 0.2遘貞ｾ・ｩ・        root.after(200, root.quit)
        root.mainloop()
        
        assert slide_switch.get() == False, "閾ｪ蜍桧FF縺悟ｮ溯｡後＆繧後ｋ縺薙→"
        test_results.append("笨・閾ｪ蜍桧FF讖溯・: OK")
        
        # 5. set_slide_switch_state()邨ｱ蜷医ユ繧ｹ繝・        callback_calls.clear()
        set_slide_switch_state(slide_switch, True)
        
        assert slide_switch.get() == True, "set_slide_switch_state()縺ｧ迥ｶ諷九′螟画峩縺輔ｌ繧九％縺ｨ"
        assert len(callback_calls) == 1, "邨ｱ蜷磯未謨ｰ縺ｧ繧ゅさ繝ｼ繝ｫ繝舌ャ繧ｯ縺悟他縺ｳ蜃ｺ縺輔ｌ繧九％縺ｨ"
        
        test_results.append("笨・邨ｱ蜷磯未謨ｰ: OK")
        
        root.destroy()
        
        print("脂 === SlideSwitch謾ｹ蝟・せ繝・せ繝亥ｮ御ｺ・===")
        for result in test_results:
            print(f"  {result}")
        
        return True
        
    except Exception as e:
        print(f"笶・繝・せ繝医お繝ｩ繝ｼ: {e}")
        import traceback
        traceback.print_exc()
        return False


# ===== 繝｡繧､繝ｳ螳溯｡・=====

if __name__ == "__main__":
    print("式 邨ｱ蜷域ｧ謾ｹ蝟・沿 SlideSwitch")
    print("=" * 40)
    
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # 繝・せ繝医Δ繝ｼ繝・        test_success = test_slide_switch_improvements()
        if test_success:
            print("\n脂 蜈ｨ縺ｦ縺ｮ繝・せ繝医′謌仙粥縺励∪縺励◆・・)
        else:
            print("\n笶・繝・せ繝医′螟ｱ謨励＠縺ｾ縺励◆縲・)
    else:
        # 繝・Δ繝｢繝ｼ繝・        try:
            demo_app = SlideSwichDemoApp()
            demo_app.run()
            
        except KeyboardInterrupt:
            print("\n尅 繝ｦ繝ｼ繧ｶ繝ｼ縺ｫ繧医ｋ荳ｭ譁ｭ")
        except Exception as e:
            print(f"笶・繝・Δ繧｢繝励Μ繧ｨ繝ｩ繝ｼ: {e}")
            import traceback
            traceback.print_exc()
    
    print("笨・繝励Ο繧ｰ繝ｩ繝邨ゆｺ・)
