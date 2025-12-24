# 📱 SlideSwitch実装仕様書 - 引き継ぎ用詳細データ

## 🎯 概要
WebSocketタブのPhase4 Step1で実装されたSlideSwitch UI仕様の完全継承データ。他チャット・開発者が同じ品質で実装できるよう、全ての技術詳細を記録。

---

## 📋 実装対象メソッド

### **`_create_service_row_with_slide_switch(self, parent, config, row)`**

**目的**: 5つのサービス（onecomme, messagebus, bouyomi, voicevox, obs）それぞれに対して、SlideSwitch付きの制御行UIを作成

**引数**:
- `parent`: 親Tkinterフレーム
- `config`: サービス設定辞書 `{'key': 'onecomme', 'icon': '📡', 'name': 'わんコメ　　　'}`
- `row`: 行番号（0-4）

---

## 🏗️ UI構造詳細

### **レイアウト構成**
```
行フレーム (ttk.Frame)
├── [列0] SlideSwitch エリア (80px固定)
├── [列1] サービス名 (150px固定) 
├── [列2] 状態表示 (100px固定)
└── [列3] 詳細情報 (可変幅・expand)
```

### **グリッド設定**
```python
row_frame.columnconfigure(0, minsize=80)   # スイッチ列
row_frame.columnconfigure(1, minsize=150)  # サービス名列  
row_frame.columnconfigure(2, minsize=100)  # 状態列
row_frame.columnconfigure(3, weight=1)     # 詳細列
```

---

## 🔧 列別実装詳細

### **列0: SlideSwitch エリア**

#### **正常実装 (slide_switch.py利用可能時)**
```python
# トグル変数作成
toggle_var = tk.BooleanVar()
toggle_var.set(self.settings.get(f'auto_start_{service_key}', True))
self.toggle_switches[service_key] = toggle_var

# SlideSwitch作成
slide_switch = create_slide_switch(
    switch_frame,                        # 親フレーム
    service_key,                         # サービスキー
    toggle_var,                          # BooleanVar
    self._on_slide_switch_toggle         # コールバック関数
)
self.slide_switches[service_key] = slide_switch
```

#### **フォールバック実装 (slide_switch.py利用不可時)**
```python
# Checkbutton代替
switch_button = ttk.Checkbutton(
    parent,
    variable=toggle_var,
    command=lambda: self._on_toggle_changed(service_key, toggle_var.get())
)
switch_button.pack()

# ログ記録
self._add_log(f"⚠️ {service_key}: SlideSwitch利用不可、Checkbuttonで代用", "warning")
```

#### **最終フォールバック (エラー時)**
```python
# エラーラベル表示
fallback_label = ttk.Label(parent, text="❌スイッチ作成失敗", foreground="red")
fallback_label.pack()
```

### **列1: サービス名**
```python
name_label = ttk.Label(
    name_frame,
    text=f"{config['icon']} {config['name']}",  # アイコン + 名前
    font=("MS Gothic", 11)                      # 固定フォント
)
name_label.pack()
```

### **列2: 状態表示**
```python
status_label = ttk.Label(
    status_frame,
    text="❌未接続",                    # 初期状態
    font=("MS Gothic", 11),
    foreground="red"                    # 初期色: 赤
)
status_label.pack()
self.status_labels[service_key] = status_label  # 管理辞書に登録
```

### **列3: 詳細情報**
```python
detail_label = ttk.Label(
    detail_frame,
    text="(初期化中...)",               # 初期メッセージ
    font=("Yu Gothic UI", 9),
    foreground="gray"                   # 初期色: グレー
)
detail_label.pack(fill=tk.X, side=tk.LEFT)      # 幅いっぱいに展開
self.detail_labels[service_key] = detail_label  # 管理辞書に登録
```

---

## 📊 サービス設定データ

### **service_configs 配列**
```python
service_configs = [
    {'key': 'onecomme',   'icon': '📡', 'name': 'わんコメ　　　'},
    {'key': 'messagebus', 'icon': '🚌', 'name': 'MessageBus　'},
    {'key': 'bouyomi',    'icon': '🎵', 'name': '棒読みちゃん　'},
    {'key': 'voicevox',   'icon': '🎤', 'name': 'VOICEVOX　　'},
    {'key': 'obs',        'icon': '📺', 'name': 'OBS　　　　　'}
]
```

**名前フィールドの文字数調整理由**: 
- 全角スペースで文字数を調整し、列幅を統一
- `MS Gothic`フォントでの見た目バランスを最適化

---

## 🔄 状態管理システム

### **管理辞書の構造**
```python
# UI要素管理
self.toggle_switches = {}    # BooleanVar格納
self.status_labels = {}      # 状態ラベル格納  
self.detail_labels = {}      # 詳細ラベル格納
self.slide_switches = {}     # SlideSwitch格納
```

### **設定値との連携**
```python
# 設定読み込み
toggle_var.set(self.settings.get(f'auto_start_{service_key}', True))

# 設定保存 (_on_toggle_changed内で実行)
self.settings[f'auto_start_{service_key}'] = enabled
self._save_settings()
```

---

## ⚡ イベントハンドリング仕様

### **SlideSwitch変更時のフロー**
```
1. ユーザーがSlideSwitch操作
     ↓
2. _on_slide_switch_toggle(service_key, enabled) 呼び出し
     ↓
3. update_slide_switch_appearance() でUI更新
     ↓  
4. _on_toggle_changed(service_key, enabled) 実行
     ↓
5. サービス状態更新 + 設定保存
     ↓
6. MessageBridge経由 or 直接制御でサービス操作
```

### **コールバック関数仕様**
```python
def _on_slide_switch_toggle(self, service_key, enabled):
    """SlideSwitch変更時のコールバック"""
    logger.info(f"🔄 SlideSwitch変更: {service_key} = {enabled}")
    self._on_toggle_changed(service_key, enabled)
    
    # 外観更新
    if SLIDE_SWITCH_AVAILABLE and service_key in self.slide_switches:
        update_slide_switch_appearance(self.slide_switches[service_key], enabled)
```

---

## 🎨 状態表示仕様

### **状態とUI表示の対応**
| 状態 | テキスト | 色 | 条件 |
|------|----------|-----|------|
| 自動復旧中 | 🔄確認中 | orange | `auto_recovery_in_progress = True` |
| 接続中 | ✅接続中 | green | `connected = True & enabled = True` |
| 未接続 | ❌未接続 | red | `enabled = True & connected = False` |
| 無効 | ⚪無効 | gray | `enabled = False` |

### **詳細情報の表示内容**
| サービス | 接続時の詳細表示例 |
|----------|-------------------|
| onecomme | `WebSocket接続中 (45.2ms)` |
| messagebus | `MessageBridge 連携中` |
| bouyomi | `TCP接続確認: localhost:50001` |
| voicevox | `API確認: v0.14.0` |
| obs | `WebSocket確認: localhost:4455` |

---

## 🧪 エラーハンドリング仕様

### **3段階フォールバック構造**
```
1段階: SlideSwitch正常作成
   ↓ (slide_switch.py利用不可)
2段階: Checkbutton代替作成  
   ↓ (Checkbutton作成失敗)
3段階: エラーラベル表示
```

### **エラー時のログ出力**
```python
# SlideSwitch作成エラー
logger.error(f"❌ SlideSwitch作成エラー ({service_key}): {e}")

# フォールバック使用ログ
logger.debug(f"⚠️ フォールバックスイッチ作成: {service_key}")
self._add_log(f"⚠️ {service_key}: SlideSwitch利用不可、Checkbuttonで代用", "warning")

# 最終エラー
logger.error(f"❌ フォールバックスイッチ作成エラー ({service_key}): {e}")
```

---

## 📦 依存関係

### **必須import**
```python
import tkinter as tk
from tkinter import ttk
from slide_switch import create_slide_switch, update_slide_switch_appearance, animate_slide_switch
```

### **依存モジュール確認**
```python
try:
    from slide_switch import create_slide_switch, update_slide_switch_appearance, animate_slide_switch
    SLIDE_SWITCH_AVAILABLE = True
except ImportError as e:
    SLIDE_SWITCH_AVAILABLE = False
```

---

## 🔧 外部関数仕様

### **slide_switch.py の必要関数**

#### **create_slide_switch(parent, service_key, toggle_var, callback)**
- **戻り値**: SlideSwitch オブジェクト
- **動作**: 指定フレーム内にSlideSwitch UI作成

#### **update_slide_switch_appearance(slide_switch, is_on)**  
- **動作**: SlideSwitch の ON/OFF 外観を更新
- **is_on**: True=ON状態, False=OFF状態

#### **animate_slide_switch(slide_switch, to_on)**
- **動作**: SlideSwitch の状態変更をアニメーション付きで実行
- **to_on**: True=ONへ, False=OFFへ

---

## 🧪 テスト確認項目

### **基本動作確認**
- [ ] 5つのSlideSwitch が表示される
- [ ] ON/OFF 切り替えが動作する
- [ ] 各サービスのアイコンとラベルが正しく表示される
- [ ] スイッチの状態が設定に保存される

### **フォールバック確認**
- [ ] slide_switch.py 無し時にCheckbutton表示
- [ ] エラー時にエラーラベル表示
- [ ] 警告ログが適切に出力される

### **状態連携確認**  
- [ ] スイッチ操作でサービス状態が変化
- [ ] 状態ラベルの色・テキストが正しく更新
- [ ] 詳細情報が適切に表示される

---

## 📝 実装時の注意点

### **重要ポイント**
1. **グリッド設定**: `columnconfigure()` で列幅を必ず固定
2. **例外処理**: 各段階で try-except を実装
3. **ログ出力**: 成功/失敗/警告を適切に記録
4. **管理辞書**: UI要素を必ず辞書で管理
5. **設定連携**: toggle_var と settings の双方向同期

### **よくある実装ミス**
- ❌ グリッド設定忘れ → レイアウト崩れ
- ❌ 例外処理不備 → エラー時に画面真っ白
- ❌ 管理辞書登録忘れ → 状態更新できない
- ❌ 設定保存忘れ → 再起動時に設定リセット

---

## 🔄 他チャット引き継ぎ用コマンド

### **引き継ぎ時の指示文**
```
「WebSocketタブのSlideSwitch実装を行います。
SlideSwitch実装仕様書の通りに、
_create_service_row_with_slide_switch() メソッドを
完全実装してください。

5つのサービス対応、3段階フォールバック、
グリッド4列レイアウトで実装してください。」
```

### **確認用テストコマンド**
```bash
# 基本動作確認
python app_phase4_step2.py test

# SlideSwitch単体確認  
python -c "from slide_switch import create_slide_switch; print('SlideSwitch OK')"
```

---

## 📈 実装完了時の期待状態

### **UI表示**
```
🌐 サービス接続状態 (Phase4 Step2 - Mock分離)
┌─────────────────────────────────────────────────────┐
│ [●─] 📡 わんコメ　　　   ❌未接続  (初期化中...)    │
│ [○─] 🚌 MessageBus　    ⚪無効    (停止中)        │  
│ [●─] 🎵 棒読みちゃん　   ✅接続中  TCP接続確認...  │
│ [○─] 🎤 VOICEVOX　　    ❌未接続  接続失敗...     │
│ [●─] 📺 OBS　　　　　   ✅接続中  WebSocket確認.. │
└─────────────────────────────────────────────────────┘
```

### **ログ出力例**
```
[12:43:37] ✅ SlideSwitch作成: onecomme
[12:43:37] ✅ SlideSwitch作成: messagebus  
[12:43:37] ⚠️ bouyomi: SlideSwitch利用不可、Checkbuttonで代用
[12:43:37] ✅ サービス行作成完了: onecomme
[12:43:37] 🔄 SlideSwitch変更: onecomme = True
```

---

## 🎯 この仕様書の使用方法

1. **他チャットでの引き継ぎ**: 全文をコピーして新チャットで共有
2. **開発者への委託**: 技術詳細として提供
3. **品質確認**: テスト確認項目でレビュー実施
4. **トラブルシューティング**: エラーハンドリング仕様を参照

**この仕様書により、誰でも同じ品質のSlideSwitch UIを実装できます！** 🚀