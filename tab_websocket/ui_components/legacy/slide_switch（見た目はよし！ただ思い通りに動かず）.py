#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎮 統合性改喁E�� 自動接続SlideSwitch v3.0
Improved Auto Connection SlideSwitch with Unified State Management

改喁E�EインチE
- SlideSwitch.set() を中忁E��した一允E��状態管琁E- set_slide_switch_state() は SlideSwitch.set() を�E部呼び出ぁE- UI更新とコールバック呼び出し�E完�E同期
- クリチE��操作と状態変更の確実な連携
- 自動接続�E自動OFF機�Eとの完�E整合性
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import logging

# ログ設宁Elogging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


class SlideSwitch(tk.Frame):
    """
    改良牁ElideSwitch - 状態とUI完�E同期
    
    特徴:
    - set() メソチE��による一允E��状態管琁E    - UI更新とコールバックの完�E同期
    - 自動OFF機�E統吁E    """
    
    def __init__(self, master=None, text_on="ON", text_off="OFF", 
                 initial_value=False, callback=None, service_key=None, **kwargs):
        """
        初期匁E        
        Args:
            master: 親ウィジェチE��
            text_on: ON表示チE��スチE            text_off: OFF表示チE��スチE            initial_value: 初期値
            callback: 状態変更時�Eコールバック関数 callback(service_key, value)
            service_key: サービス識別キー
        """
        super().__init__(master, **kwargs)
        
        # 基本設宁E        self._value = initial_value
        self._text_on = text_on
        self._text_off = text_off
        self._callback = callback
        self._service_key = service_key
        self._after_id = None
        
        # UI作�E
        self._create_ui()
        
        # 初期状態反映
        self._update_ui()
    
    def _create_ui(self):
        """UI要素作�E"""
        self.configure(width=80, height=30, bg="#f5f5f5")
        
        # キャンバス作�E
        self.canvas = tk.Canvas(
            self, 
            width=80, 
            height=30, 
            bd=0, 
            highlightthickness=0,
            bg="#e57373"  # 初期: 赤�E�EFF状態！E        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # UI要素作�E
        self.bg_rect = self.canvas.create_rectangle(2, 2, 78, 28, outline="", fill="#e57373")
        self.indicator = self.canvas.create_oval(5, 5, 25, 25, outline="#cccccc", fill="white", width=2)
        self.text = self.canvas.create_text(40, 15, text=self._text_off, fill="white", font=("Yu Gothic UI", 8, "bold"))
        
        # イベントバインチE        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.bind("<Leave>", lambda e: self.canvas.config(cursor=""))
    
    def _on_canvas_click(self, event=None):
        """キャンバスクリチE��処琁E""
        # 自動OFF予紁E��はクリチE��をブロチE��
        if self._after_id:
            logger.debug(f"⚠�E�E{self._service_key}: 自動OFF予紁E��のためクリチE��無要E)
            return
            
        # トグル操作実衁E        self.toggle()
    
    def toggle(self):
        """状態トグル�E�Eet()を�E部呼び出し！E""
        self.set(not self._value)
    
    def set(self, value: bool, trigger_callback=True):
        """
        状態設定（一允E��状態管琁E��E        
        Args:
            value: 設定値
            trigger_callback: コールバック呼び出しフラグ
        """
        # 値が変わらなぁE��合�E何もしなぁE        if self._value == value and not hasattr(self, '_force_update'):
            return
            
        # 状態更新
        self._value = value
        
        # 自動OFF予紁E��キャンセル
        self.cancel_auto_off()
        
        # UI更新
        self._update_ui()
        
        # コールバック呼び出ぁE        if trigger_callback and self._callback:
            try:
                if self._service_key:
                    self._callback(self._service_key, self._value)
                else:
                    self._callback(self._value)
            except Exception as e:
                logger.error(f"❁Eコールバック呼び出しエラー ({self._service_key}): {e}")
    
    def _update_ui(self):
        """UI更新�E�状態に基づぁE��一允E��に更新�E�E""
        try:
            if self._value:
                # ON状慁E 薁E��E                bg_color = "#81c784"
                indicator_x1, indicator_x2 = 55, 75  # 右寁E��
                text_content = self._text_on
            else:
                # OFF状慁E 赤
                bg_color = "#e57373"
                indicator_x1, indicator_x2 = 5, 25   # 左寁E��
                text_content = self._text_off
            
            # キャンバス背景更新
            self.canvas.config(bg=bg_color)
            self.canvas.itemconfig(self.bg_rect, fill=bg_color)
            
            # インジケーター位置更新
            self.canvas.coords(self.indicator, indicator_x1, 5, indicator_x2, 25)
            
            # チE��スト更新
            self.canvas.itemconfig(self.text, text=text_content)
            
        except Exception as e:
            logger.error(f"❁EUI更新エラー ({self._service_key}): {e}")
    
    def get(self) -> bool:
        """現在の状態取征E""
        return self._value
    
    def auto_off(self, delay_ms=3000):
        """
        自動OFF設宁E        
        Args:
            delay_ms: 遁E��時間�E�ミリ秒！E        """
        # 既存�E予紁E��キャンセル
        self.cancel_auto_off()
        
        logger.info(f"⏰ {self._service_key}: {delay_ms/1000}秒後に自動OFF実衁E)
        
        def execute_auto_off():
            logger.info(f"⏰ {self._service_key}: 自動OFF実衁E)
            self.set(False)  # set()を通して状態変更
            self._after_id = None
        
        self._after_id = self.after(delay_ms, execute_auto_off)
    
    def cancel_auto_off(self):
        """自動OFF予紁E��ャンセル"""
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
            logger.debug(f"⏰ {self._service_key}: 自動OFF予紁E��ャンセル")
    
    def set_connecting_state(self, is_connecting=True):
        """
        接続中状態表示
        
        Args:
            is_connecting: 接続中フラグ
        """
        try:
            if is_connecting:
                # 接続中: オレンジで点滁E                self.canvas.config(bg="#ff9800")
                self.canvas.itemconfig(self.bg_rect, fill="#ff9800")
                self.canvas.itemconfig(self.text, text="接続中...")
                self._start_connecting_blink()
            else:
                # 通常状態に戻ぁE                self._update_ui()
                
        except Exception as e:
            logger.error(f"❁E接続状態表示エラー ({self._service_key}): {e}")
    
    def _start_connecting_blink(self):
        """接続中の点滁E��姁E""
        if hasattr(self, '_connecting_blink') and self._connecting_blink:
            current_bg = self.canvas.cget("bg")
            if current_bg == "#ff9800":
                new_bg = "#ffcc80"  # 薁E��オレンジ
            else:
                new_bg = "#ff9800"
            
            self.canvas.config(bg=new_bg)
            self.canvas.itemconfig(self.bg_rect, fill=new_bg)
            self.after(500, self._start_connecting_blink)
    
    def start_connecting_animation(self):
        """接続中アニメーション開姁E""
        self._connecting_blink = True
        self.set_connecting_state(True)
    
    def stop_connecting_animation(self):
        """接続中アニメーション停止"""
        self._connecting_blink = False
        self.set_connecting_state(False)


# ===== 統合関数: 外部からの状態制御 =====

def set_slide_switch_state(slide_switch, value: bool, log_widget=None, message: str = ""):
    """
    SlideSwitch状態設定（統合版�E�E    
    Args:
        slide_switch: SlideSwitch インスタンス
        value: 設定値
        log_widget: ログ表示ウィジェチE��
        message: ログメチE��ージ
    """
    if slide_switch and hasattr(slide_switch, 'set'):
        # SlideSwitch.set()を通して状態変更�E�一允E��琁E��E        slide_switch.set(value)
    
    # ログ出劁E    if log_widget and message and hasattr(log_widget, "insert"):
        log_widget.insert("end", f"{message}\n")
        log_widget.see("end")


def create_slide_switch(parent, service_key, toggle_var, callback):
    """
    SlideSwitch作�E�E�互換性維持E��E    
    Args:
        parent: 親フレーム
        service_key: サービスキー
        toggle_var: BooleanVar�E�使用されなぁE��互換性のため保持�E�E        callback: コールバック関数
        
    Returns:
        SlideSwitch: 作�EされたSlideSwitch
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
    SlideSwitch外観更新�E�互換性維持E��E    
    Args:
        slide_switch: SlideSwitch インスタンス
        is_on: ON/OFF状慁E    """
    if slide_switch and hasattr(slide_switch, 'set'):
        slide_switch.set(is_on, trigger_callback=False)  # コールバックなしで状態更新


def animate_slide_switch(slide_switch, to_on=True):
    """
    SlideSwitch アニメーション�E�互換性維持E��E    
    Args:
        slide_switch: SlideSwitch インスタンス  
        to_on: アニメーション方吁E    """
    if slide_switch and hasattr(slide_switch, 'set'):
        slide_switch.set(to_on)


# ===== 自動接続機�E統合クラス =====

class AutoConnectionManager:
    """自動接続管琁E��ラス"""
    
    def __init__(self):
        self.connection_threads = {}
        self.is_connecting = {}
        self.connection_callback = None
    
    def set_connection_callback(self, callback):
        """接続�E琁E��ールバック設宁E""
        self.connection_callback = callback
    
    def start_auto_connection(self, slide_switch, service_key):
        """自動接続開姁E""
        if self.is_connecting.get(service_key, False):
            return
            
        logger.info(f"🔗 {service_key} 自動接続開姁E)
        
        self.is_connecting[service_key] = True
        slide_switch.start_connecting_animation()
        
        # 接続�E琁E��別スレチE��で実衁E        connection_thread = threading.Thread(
            target=self._connection_worker,
            args=(slide_switch, service_key),
            daemon=True
        )
        connection_thread.start()
        self.connection_threads[service_key] = connection_thread
    
    def _connection_worker(self, slide_switch, service_key):
        """接続�E琁E��ーカー"""
        try:
            # 接続�E琁E��衁E            if self.connection_callback:
                success = self.connection_callback(service_key)
            else:
                success = self._default_connection_test(service_key)
            
            # UIスレチE��で結果処琁E            slide_switch.after(0, lambda: self._handle_connection_result(slide_switch, service_key, success))
            
        except Exception as e:
            logger.error(f"❁E{service_key} 接続エラー: {e}")
            slide_switch.after(0, lambda: self._handle_connection_result(slide_switch, service_key, False))
    
    def _default_connection_test(self, service_key):
        """チE��ォルト接続テスチE""
        import random
        
        # 接続時間模擬�E�E-3秒！E        time.sleep(random.uniform(1.0, 3.0))
        
        # 70%の確玁E��成功
        return random.random() < 0.7
    
    def _handle_connection_result(self, slide_switch, service_key, success):
        """接続結果処琁E""
        self.is_connecting[service_key] = False
        slide_switch.stop_connecting_animation()
        
        if success:
            logger.info(f"✁E{service_key} 接続�E劁E)
            slide_switch.set(True)
        else:
            logger.warning(f"❁E{service_key} 接続失敁E- 3秒後に自動OFF")
            slide_switch.set(True)  # 一旦ONにしてから
            slide_switch.auto_off(3000)  # 3秒後に自動OFF


# ===== チE��ト用チE��アプリケーション =====

class SlideSwichDemoApp:
    """SlideSwitch チE��アプリケーション"""
    
    def __init__(self):
        self.switches = {}
        self.connection_manager = AutoConnectionManager()
        self.connection_manager.set_connection_callback(self.test_connection)
        
        self._create_ui()
    
    def test_connection(self, service_key):
        """WebSocketタブ仕様準拠 接続�E琁E""
        import random
        
        print(f"🔗 {service_key} 接続テスト実行中...")
        
        # WebSocketタブ仕様準拠 サービス別設宁E        service_configs = {
            'onecomme': {
                'success_rate': 0.7,
                'connection_time': (1.5, 3.0),
                'description': 'わんコメ WebSocket接綁E
            },
            'messagebus': {
                'success_rate': 0.9,
                'connection_time': (0.5, 1.2),
                'description': 'MessageBus 冁E��通信'
            },
            'bouyomi': {
                'success_rate': 0.8,
                'connection_time': (0.8, 2.0),
                'description': '棒読みちめE�� TCP接綁E
            },
            'voicevox': {
                'success_rate': 0.6,
                'connection_time': (2.0, 4.0),
                'description': 'VOICEVOX API接綁E
            },
            'obs': {
                'success_rate': 0.75,
                'connection_time': (1.0, 2.5),
                'description': 'OBS WebSocket接綁E
            }
        }
        
        config = service_configs.get(service_key, {
            'success_rate': 0.7,
            'connection_time': (1.0, 2.0),
            'description': f'{service_key} 接綁E
        })
        
        print(f"   {config['description']} 試行中...")
        
        # 接続時間模擬
        connection_time = random.uniform(*config['connection_time'])
        time.sleep(connection_time)
        
        # 成功判宁E        success = random.random() < config['success_rate']
        
        if success:
            print(f"   ✁E{config['description']} 成功 ({connection_time:.1f}私E")
        else:
            print(f"   ❁E{config['description']} 失敁E({connection_time:.1f}私E")
        
        return success
    
    def _create_ui(self):
        """UI作�E"""
        self.root = tk.Tk()
        self.root.title("🌐 WebSocketタブ準拠 自動接続SlideSwitch")
        self.root.geometry("650x550")
        self.root.configure(bg="#f0f0f0")
        
        # タイトル
        title_label = tk.Label(
            self.root,
            text="🌐 WebSocketタブ準拠 自動接続SlideSwitch",
            font=("Yu Gothic UI", 16, "bold"),
            bg="#f0f0f0"
        )
        title_label.pack(pady=10)
        
        # 改喁E��説昁E        improvements_text = """🔧 WebSocketタチEPhase4 仕様準拠:
• 5つのサービス対忁E わんコメ、MessageBus、棒読みちめE��、VOICEVOX、OBS
• SlideSwitch.set() による一允E��状態管琁E• 起動時自動接綁E+ 接続失敗時3秒後�E動OFF
• 状態別カラー表示: 赤(未接綁E ↁEオレンジ(接続中) ↁE緁E接続済み)
• UI更新とコールバックの完�E同期"""
        
        improvements_label = tk.Label(
            self.root,
            text=improvements_text,
            font=("Yu Gothic UI", 9),
            bg="#f0f0f0",
            justify=tk.LEFT
        )
        improvements_label.pack(pady=5)
        
        # スイチE��エリア
        switches_frame = tk.LabelFrame(
            self.root, 
            text="🌐 WebSocketタチEサービス接綁E, 
            font=("Yu Gothic UI", 12, "bold")
        )
        switches_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # WebSocketタブ仕様準拠 サービス一覧
        services = [
            ('onecomme', '📡 わんコメ　　　'),
            ('messagebus', '🚌 MessageBus　'),
            ('bouyomi', '🎵 棒読みちめE��　'),
            ('voicevox', '🎤 VOICEVOX　　'),
            ('obs', '📺 OBS　　　　　')
        ]
        
        for service_key, service_name in services:
            self._create_service_row(switches_frame, service_key, service_name)
        
        # コントロールパネル
        self._create_control_panel()
        
        # ログエリア
        self._create_log_area()
    
    def _create_service_row(self, parent, service_key, service_name):
        """サービス行作�E"""
        row_frame = tk.Frame(parent, bg="#f5f5f5", relief="solid", bd=1)
        row_frame.pack(fill=tk.X, padx=5, pady=3)
        
        # サービス名！EebSocketタブ仕様準拠の固定幁E��E        name_label = tk.Label(
            row_frame,
            text=service_name,  # アイコン付きサービス吁E            font=("MS Gothic", 11),  # Phase4仕槁E MS Gothic
            bg="#f5f5f5",
            width=18,  # 固定幁E            anchor="w"
        )
        name_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # SlideSwitch
        def on_toggle(key, value):
            print(f"🔄 {key} 状態変更: {value}")
            if value:
                # ON時�E自動接続開姁E                self.connection_manager.start_auto_connection(self.switches[key], key)
        
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
        
        # 状態表示
        status_label = tk.Label(
            row_frame,
            text="⚪ 無効",
            font=("Yu Gothic UI", 10),
            bg="#f5f5f5",
            fg="gray"
        )
        status_label.pack(side=tk.LEFT, padx=10, pady=5)
    
    def _create_control_panel(self):
        """コントロールパネル作�E"""
        control_frame = tk.LabelFrame(
            self.root, 
            text="コントロール", 
            font=("Yu Gothic UI", 11, "bold")
        )
        control_frame.pack(fill=tk.X, padx=20, pady=5)
        
        button_frame = tk.Frame(control_frame)
        button_frame.pack(pady=5)
        
        def auto_connect_all():
            print("🚀 WebSocketタチE全サービス自動接続開姁E)
            for service_key, switch in self.switches.items():
                switch.set(True)  # ON状態にしてコールバックで自動接綁E        
        def force_off_all():
            print("🔌 WebSocketタチE全サービス強制刁E��")
            for service_key, switch in self.switches.items():
                set_slide_switch_state(switch, False, self.log_text, f"❁E{service_key} 強制刁E��")
        
        def test_auto_off():
            print("⏰ WebSocketタチE全サービス自動OFF チE��チE)
            for service_key, switch in self.switches.items():
                switch.set(True)  # 一旦ON
                switch.auto_off(3000)  # 3秒後�E動OFF
        
        # ボタン配置
        tk.Button(button_frame, text="🚀 全自動接綁E, command=auto_connect_all).pack(side=tk.LEFT, padx=3)
        tk.Button(button_frame, text="🔌 全強制OFF", command=force_off_all).pack(side=tk.LEFT, padx=3)
        tk.Button(button_frame, text="⏰ 自動OFF���스チE, command=test_auto_off).pack(side=tk.LEFT, padx=3)
    
    def _create_log_area(self):
        """ログエリア作�E"""
        log_frame = tk.LabelFrame(
            self.root, 
            text="動作ログ", 
            font=("Yu Gothic UI", 10, "bold")
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        # ログチE��ストウィジェチE��
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
        
        # 初期メチE��ージ
        self.log_text.insert("end", "🌐 WebSocketタブ準拠 自動接続SlideSwitch 開始\n")
        self.log_text.insert("end", "📡 わんコメ、🚁EMessageBus、🎵 棒読みちめE��、🎤 VOICEVOX、📺 OBS\n")
        self.log_text.insert("end", "💡 吁E��イチE��をクリチE��して動作確認してください\n")
        self.log_text.insert("end", "🔧 Phase4仕槁E 起動時自動接綁E+ 接続失敗時3秒後�E動OFF\n\n")
    
    def run(self):
        """アプリケーション実衁E""
        print("🌐 WebSocketタブ準拠 自動接続SlideSwitch 開姁E)
        print("📡 わんコメ、🚁EMessageBus、🎵 棒読みちめE��、🎤 VOICEVOX、📺 OBS")
        print("🔧 Phase4仕槁E SlideSwitch.set()による一允E��状態管琁E)
        
        self.root.mainloop()
        
        print("✁EWebSocketタチESlideSwitch チE��終亁E)


# ===== 単体テスチE=====

def test_slide_switch_improvements():
    """SlideSwitch改喁E��チE��チE""
    print("🧪 === SlideSwitch改喁E��チE��チE===")
    
    test_results = []
    
    try:
        # チE��ト用UI作�E
        root = tk.Tk()
        root.withdraw()  # ウィンドウを隠ぁE        
        callback_calls = []
        
        def test_callback(service_key, value):
            callback_calls.append((service_key, value))
        
        # 1. SlideSwitch作�EチE��チE        slide_switch = SlideSwitch(
            root,
            initial_value=False,
            callback=test_callback,
            service_key="test_service"
        )
        
        assert slide_switch.get() == False, "初期値が正しく設定されること"
        test_results.append("✁E初期値設宁E OK")
        
        # 2. set()メソチE��チE��チE        slide_switch.set(True)
        assert slide_switch.get() == True, "set()で状態が変更されること"
        assert len(callback_calls) == 1, "コールバックが呼び出されること"
        assert callback_calls[0] == ("test_service", True), "コールバック引数が正しいこと"
        
        test_results.append("✁Eset()メソチE��: OK")
        
        # 3. toggle()メソチE��チE��チE        callback_calls.clear()
        slide_switch.toggle()
        assert slide_switch.get() == False, "toggle()で状態が刁E��替わること"
        assert len(callback_calls) == 1, "toggle時にコールバックが呼び出されること"
        
        test_results.append("✁Etoggle()メソチE��: OK")
        
        # 4. 自動OFF機�EチE��チE        slide_switch.set(True)
        slide_switch.auto_off(100)  # 0.1秒征E        
        # 0.2秒征E��E        root.after(200, root.quit)
        root.mainloop()
        
        assert slide_switch.get() == False, "自動OFFが実行されること"
        test_results.append("✁E自動OFF機�E: OK")
        
        # 5. set_slide_switch_state()統合テスチE        callback_calls.clear()
        set_slide_switch_state(slide_switch, True)
        
        assert slide_switch.get() == True, "set_slide_switch_state()で状態が変更されること"
        assert len(callback_calls) == 1, "統合関数でもコールバックが呼び出されること"
        
        test_results.append("✁E統合関数: OK")
        
        root.destroy()
        
        print("🎉 === SlideSwitch改喁E��チE��ト完亁E===")
        for result in test_results:
            print(f"  {result}")
        
        return True
        
    except Exception as e:
        print(f"❁EチE��トエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


# ===== メイン実衁E=====

if __name__ == "__main__":
    print("🌐 WebSocketタブ準拠 自動接続SlideSwitch")
    print("📡 わんコメ 🚌 MessageBus 🎵 棒読みちめE�� 🎤 VOICEVOX 📺 OBS")
    print("=" * 60)
    
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # チE��トモーチE        test_success = test_slide_switch_improvements()
        if test_success:
            print("\n🎉 全てのチE��トが成功しました�E�E)
        else:
            print("\n❁EチE��トが失敗しました、E)
    else:
        # チE��モーチE        try:
            demo_app = SlideSwichDemoApp()
            demo_app.run()
            
        except KeyboardInterrupt:
            print("\n🛑 ユーザーによる中断")
        except Exception as e:
            print(f"❁EチE��アプリエラー: {e}")
            import traceback
            traceback.print_exc()
    
    print("✁Eプログラム終亁E)
